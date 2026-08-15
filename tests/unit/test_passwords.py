"""Password change and reset — TD-15 repayment.

TD-15 was Critical because the collector types a client's first password and
therefore knows it, making the client's record dependent on the collector and
contradicting BR-02. These tests exist to keep that closed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities import User, UserRole
from app.domain.errors import DomainError
from app.services.notifications import NotificationService, NullSmsGateway
from app.services.passwords import (
    CODE_TTL_MINUTES,
    MAX_REQUESTS_PER_HOUR,
    MAX_VERIFY_ATTEMPTS,
    PasswordService,
    ResetCodeInvalid,
    TooManyRequests,
    WeakPassword,
    generate_code,
    validate_password,
)
from app.services.security import hash_password, verify_password

from .fakes import (
    FakeAuditRepository,
    FakePasswordResetRepository,
    FakeUnitOfWork,
    FakeUserRepository,
)
from uuid import uuid4

NOW = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)


class Harness:
    def __init__(self):
        self.now = NOW
        self.users = FakeUserRepository()
        self.resets = FakePasswordResetRepository()
        self.audit = FakeAuditRepository()
        self.uow = FakeUnitOfWork()
        self.gateway = NullSmsGateway()
        self.notifications = NotificationService(
            self.gateway, allow_all=True, synchronous=True
        )
        self.service = PasswordService(
            users=self.users,
            resets=self.resets,
            audit=self.audit,
            uow=self.uow,
            notifications=self.notifications,
            now=lambda: self.now,
        )
        self.user = self.users.add(
            User(
                id=None,
                public_ref=uuid4(),
                full_name="Mavis Quaye",
                phone="0201000209",
                role=UserRole.CLIENT,
            ),
            hash_password("collector-chose-this"),
        )

    def last_code(self) -> str:
        """The code as the client would read it off their phone."""
        return self.gateway.sent[-1][1].split("code is ")[1].split(".")[0]


@pytest.fixture
def h() -> Harness:
    return Harness()


class TestPasswordPolicy:
    def test_rejects_short(self):
        with pytest.raises(WeakPassword, match="at least 6"):
            validate_password("abc")

    def test_accepts_six_characters(self):
        validate_password("susu12")

    def test_rejects_repeated_digits(self):
        with pytest.raises(WeakPassword, match="too easy"):
            validate_password("111111")

    def test_policy_is_deliberately_modest(self):
        """No symbol or mixed-case demand.

        The users are market traders typing on a low-end handset; a rule that
        strict pushes them to write the password on the susu card, which defeats
        the purpose more thoroughly than a short password does.
        """
        validate_password("mypassword")


class TestForcedChange:
    def test_change_clears_the_flag(self, h):
        h.users.require_password_change(h.user.id)
        assert h.users.must_change_password(h.user.id) is True

        h.service.change_password(
            user=h.user, current_password=None, new_password="mynewpass"
        )
        assert h.users.must_change_password(h.user.id) is False

    def test_the_collectors_password_stops_working(self, h):
        """The point of TD-15: the collector must not retain access."""
        h.service.change_password(
            user=h.user, current_password=None, new_password="mynewpass"
        )
        _, stored = h.users.find_credentials("0201000209")
        assert verify_password(stored, "collector-chose-this") is False
        assert verify_password(stored, "mynewpass") is True

    def test_forced_change_does_not_require_the_old_password(self, h):
        """Demanding the password the collector chose would be pointless
        friction — the user is already authenticated."""
        h.service.change_password(
            user=h.user, current_password=None, new_password="mynewpass"
        )

    def test_voluntary_change_requires_the_current_password(self, h):
        with pytest.raises(DomainError, match="not correct"):
            h.service.change_password(
                user=h.user, current_password="wrong", new_password="mynewpass"
            )

    def test_voluntary_change_accepts_the_correct_current_password(self, h):
        h.service.change_password(
            user=h.user,
            current_password="collector-chose-this",
            new_password="mynewpass",
        )

    def test_weak_new_password_is_refused(self, h):
        with pytest.raises(WeakPassword):
            h.service.change_password(
                user=h.user, current_password=None, new_password="abc"
            )

    def test_change_is_audited(self, h):
        h.service.change_password(
            user=h.user, current_password=None, new_password="mynewpass"
        )
        entry = next(e for e in h.audit.entries if e["action"] == "PASSWORD_CHANGED")
        assert entry["detail"]["forced"] is True


class TestResetRequest:
    def test_code_is_sent_by_sms(self, h):
        h.service.request_reset(phone="0201000209")
        assert len(h.gateway.sent) == 1
        assert "reset code is" in h.gateway.sent[0][1]

    def test_code_is_six_digits(self, h):
        h.service.request_reset(phone="0201000209")
        assert h.last_code().isdigit() and len(h.last_code()) == 6

    def test_code_is_stored_only_as_a_hash(self, h):
        """A database leak must not hand an attacker a working token."""
        h.service.request_reset(phone="0201000209")
        record = h.resets.outstanding_for(h.user.id, at=h.now)
        assert h.last_code() not in record.code_hash
        assert record.code_hash.startswith("$argon2")

    def test_unknown_number_is_silent_and_sends_nothing(self, h):
        """Confirming whether an account exists would allow enumeration."""
        h.service.request_reset(phone="0209999999")
        assert h.gateway.sent == []

    def test_unknown_number_is_still_audited(self, h):
        h.service.request_reset(phone="0209999999")
        entry = next(
            e for e in h.audit.entries if e["action"] == "PASSWORD_RESET_REQUESTED"
        )
        assert entry["detail"]["outcome"] == "unknown_account"

    def test_a_new_request_voids_the_previous_code(self, h):
        h.service.request_reset(phone="0201000209")
        first = h.last_code()
        h.service.request_reset(phone="0201000209")

        with pytest.raises(ResetCodeInvalid):
            h.service.complete_reset(
                phone="0201000209", code=first, new_password="mynewpass"
            )

    def test_requests_are_rate_limited(self, h):
        for _ in range(MAX_REQUESTS_PER_HOUR):
            h.service.request_reset(phone="0201000209")
        with pytest.raises(TooManyRequests):
            h.service.request_reset(phone="0201000209")

    def test_throttling_is_audited(self, h):
        for _ in range(MAX_REQUESTS_PER_HOUR):
            h.service.request_reset(phone="0201000209")
        with pytest.raises(TooManyRequests):
            h.service.request_reset(phone="0201000209")
        assert "PASSWORD_RESET_THROTTLED" in h.audit.actions()


class TestResetCompletion:
    def test_correct_code_sets_the_new_password(self, h):
        h.service.request_reset(phone="0201000209")
        h.service.complete_reset(
            phone="0201000209", code=h.last_code(), new_password="mynewpass"
        )
        _, stored = h.users.find_credentials("0201000209")
        assert verify_password(stored, "mynewpass") is True

    def test_reset_also_clears_a_pending_forced_change(self, h):
        h.users.require_password_change(h.user.id)
        h.service.request_reset(phone="0201000209")
        h.service.complete_reset(
            phone="0201000209", code=h.last_code(), new_password="mynewpass"
        )
        assert h.users.must_change_password(h.user.id) is False

    def test_wrong_code_is_refused(self, h):
        h.service.request_reset(phone="0201000209")
        with pytest.raises(ResetCodeInvalid, match="not correct"):
            h.service.complete_reset(
                phone="0201000209", code="000000", new_password="mynewpass"
            )

    def test_a_code_cannot_be_used_twice(self, h):
        h.service.request_reset(phone="0201000209")
        code = h.last_code()
        h.service.complete_reset(
            phone="0201000209", code=code, new_password="mynewpass"
        )
        with pytest.raises(ResetCodeInvalid):
            h.service.complete_reset(
                phone="0201000209", code=code, new_password="another1"
            )

    def test_an_expired_code_is_refused(self, h):
        h.service.request_reset(phone="0201000209")
        code = h.last_code()
        h.now = NOW + timedelta(minutes=CODE_TTL_MINUTES + 1)
        with pytest.raises(ResetCodeInvalid, match="expired"):
            h.service.complete_reset(
                phone="0201000209", code=code, new_password="mynewpass"
            )

    def test_guessing_is_bounded(self, h):
        """Six digits is a million possibilities; without a cap this endpoint
        would be a brute-force surface of its own."""
        h.service.request_reset(phone="0201000209")
        for _ in range(MAX_VERIFY_ATTEMPTS):
            with pytest.raises(ResetCodeInvalid):
                h.service.complete_reset(
                    phone="0201000209", code="000000", new_password="mynewpass"
                )
        with pytest.raises(ResetCodeInvalid, match="Too many"):
            h.service.complete_reset(
                phone="0201000209", code=h.last_code(), new_password="mynewpass"
            )

    def test_weak_new_password_is_refused(self, h):
        h.service.request_reset(phone="0201000209")
        with pytest.raises(WeakPassword):
            h.service.complete_reset(
                phone="0201000209", code=h.last_code(), new_password="abc"
            )

    def test_completion_is_audited(self, h):
        h.service.request_reset(phone="0201000209")
        h.service.complete_reset(
            phone="0201000209", code=h.last_code(), new_password="mynewpass"
        )
        assert "PASSWORD_RESET_COMPLETED" in h.audit.actions()

    def test_failed_attempt_is_audited(self, h):
        h.service.request_reset(phone="0201000209")
        with pytest.raises(ResetCodeInvalid):
            h.service.complete_reset(
                phone="0201000209", code="000000", new_password="mynewpass"
            )
        assert "PASSWORD_RESET_FAILED" in h.audit.actions()


class TestCodeGeneration:
    def test_always_six_digits(self):
        for _ in range(500):
            code = generate_code()
            assert len(code) == 6 and code.isdigit()

    def test_codes_are_not_obviously_predictable(self):
        assert len({generate_code() for _ in range(500)}) > 400
