"""Password change and self-service reset — TD-15. Layer 2 (Application).

Repays the debt recorded as TD-15, which was classified **Critical** for a
reason worth restating: at enrolment the collector types the client's first
password, and therefore knows it. A collector who can sign in as their own
client makes the client's record dependent on the collector — which is the
precise property (BR-02) the system exists to provide. The independence was
nominal until this module existed.

Two halves, of different severity:

* **Forced change on first login** removes the collector's knowledge of the
  working password. This is the half that restores BR-02.
* **Self-service reset** stops a forgotten password becoming permanent
  lockout. It became possible only once CR-002 delivered an SMS channel; the
  debt register named that as the blocker, and it is now gone.

**On the provider's OTP endpoint.** Arkesel offers a dedicated OTP API that
generates, stores and verifies codes on their side, which would delete most of
this module. It was considered and not used, for reasons specific to what this
system claims about itself:

* **The audit trail is the product.** SusuBook exists to make a record that can
  answer a dispute. Every request, failed attempt, throttle and completion here
  is written to our own audit log with an actor and a timestamp. Delegating
  verification would move that evidence to a third party's logs, which we cannot
  produce on demand.
* **The policy becomes theirs, not ours.** Expiry, attempt caps and request
  throttling are stated here in constants that a reader can check and a test can
  assert. As provider configuration they would be opaque and untestable.
* **Verification would need the network.** A provider-side check means a client
  cannot reset while the gateway is unreachable. Here only *delivery* depends on
  the network; verification is a local comparison.
* **Swapping providers stays cheap.** SMS is behind `SmsGateway`; the reset
  logic does not know who delivers the message. Using a provider-specific OTP
  API would put Arkesel into the reset flow itself.

The trade is real: this is roughly a hundred lines of security-sensitive code we
maintain rather than consume. It is covered by 30 unit tests, and the codes are
stored only as Argon2 hashes, so the exposure is bounded. If deliverability or
cost later favours the provider's endpoint, it belongs behind a new
`OtpProvider` protocol rather than inline — the same seam pattern used
throughout.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.domain.entities import User
from app.domain.errors import DomainError

from .notifications import NotificationService
from .protocols import AuditRepository, PasswordResetRepository, UnitOfWork, UserRepository
from .security import hash_password, verify_password

MIN_PASSWORD_LENGTH = 6
CODE_TTL_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5
MAX_REQUESTS_PER_HOUR = 3


class WeakPassword(DomainError):
    pass


class ResetCodeInvalid(DomainError):
    pass


class TooManyRequests(DomainError):
    pass


def validate_password(candidate: str) -> None:
    """Minimum viable policy, stated in one place.

    Deliberately modest: the users are market traders entering a password on a
    low-end handset, and a rule demanding symbols and mixed case would push them
    towards writing it on the susu card — which would defeat the purpose more
    thoroughly than a short password does.
    """
    if len(candidate) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters."
        )
    if candidate.isdigit() and len(set(candidate)) <= 2:
        raise WeakPassword("That password is too easy to guess. Choose another.")


def generate_code() -> str:
    """Six digits, from a cryptographically secure source."""
    return f"{secrets.randbelow(1_000_000):06d}"


class PasswordService:
    def __init__(
        self,
        *,
        users: UserRepository,
        resets: PasswordResetRepository,
        audit: AuditRepository,
        uow: UnitOfWork,
        notifications: NotificationService,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = users
        self._resets = resets
        self._audit = audit
        self._uow = uow
        self._notifications = notifications
        self._now = now

    # -- forced / voluntary change ---------------------------------------

    def change_password(
        self, *, user: User, current_password: str | None, new_password: str
    ) -> None:
        """Set a new password.

        `current_password` is required for a voluntary change and skipped on a
        forced first change — the user is already authenticated, and demanding
        the password their collector chose would be pointless friction.
        """
        validate_password(new_password)

        if current_password is not None:
            found = self._users.find_credentials(user.phone)
            if found is None or not verify_password(found[1], current_password):
                raise DomainError("Your current password is not correct.")

        self._users.set_password(user.id, hash_password(new_password))
        self._users.clear_password_change_flag(user.id)
        self._audit.append(
            actor_id=user.id,
            action="PASSWORD_CHANGED",
            target_type="USER",
            target_id=str(user.id),
            detail={"forced": current_password is None},
        )
        self._uow.commit()

    # -- self-service reset ----------------------------------------------

    def request_reset(self, *, phone: str) -> None:
        """Issue a one-time code by SMS.

        Returns nothing and raises nothing on an unknown number. Telling the
        caller whether an account exists would let anyone enumerate registered
        phone numbers — the same reasoning as the login message in AuthService.
        """
        found = self._users.find_credentials(phone.strip())
        if found is None:
            self._audit.append(
                actor_id=None,
                action="PASSWORD_RESET_REQUESTED",
                target_type="USER",
                detail={"outcome": "unknown_account"},
            )
            self._uow.commit()
            return

        user, _ = found
        now = self._now()

        if self._resets.recent_request_count(user.id, since=now - timedelta(hours=1)) >= MAX_REQUESTS_PER_HOUR:
            self._audit.append(
                actor_id=user.id,
                action="PASSWORD_RESET_THROTTLED",
                target_type="USER",
                target_id=str(user.id),
            )
            self._uow.commit()
            raise TooManyRequests(
                "Too many reset requests. Please wait an hour and try again."
            )

        # Any outstanding code is void once a new one is issued.
        self._resets.invalidate_outstanding(user.id, at=now)

        code = generate_code()
        self._resets.add(
            user_id=user.id,
            code_hash=hash_password(code),
            expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
        )
        self._audit.append(
            actor_id=user.id,
            action="PASSWORD_RESET_REQUESTED",
            target_type="USER",
            target_id=str(user.id),
            detail={"outcome": "code_issued"},
        )
        self._uow.commit()

        self._notifications.notify(
            phone=user.phone,
            message=(
                f"SusuBook: your password reset code is {code}. "
                f"It expires in {CODE_TTL_MINUTES} minutes. "
                f"If you did not ask for this, ignore this message."
            ),
        )

    def complete_reset(self, *, phone: str, code: str, new_password: str) -> None:
        validate_password(new_password)

        found = self._users.find_credentials(phone.strip())
        if found is None:
            raise ResetCodeInvalid("That code is not valid.")
        user, _ = found

        now = self._now()
        record = self._resets.outstanding_for(user.id, at=now)
        if record is None:
            raise ResetCodeInvalid("That code has expired or has already been used.")

        if record.attempts >= MAX_VERIFY_ATTEMPTS:
            self._resets.mark_used(record.id, at=now)
            self._uow.commit()
            raise ResetCodeInvalid(
                "Too many incorrect attempts. Request a new code."
            )

        if not verify_password(record.code_hash, code.strip()):
            self._resets.record_attempt(record.id)
            self._audit.append(
                actor_id=user.id,
                action="PASSWORD_RESET_FAILED",
                target_type="USER",
                target_id=str(user.id),
            )
            self._uow.commit()
            raise ResetCodeInvalid("That code is not correct.")

        self._resets.mark_used(record.id, at=now)
        self._users.set_password(user.id, hash_password(new_password))
        self._users.clear_password_change_flag(user.id)
        self._audit.append(
            actor_id=user.id,
            action="PASSWORD_RESET_COMPLETED",
            target_type="USER",
            target_id=str(user.id),
        )
        self._uow.commit()
