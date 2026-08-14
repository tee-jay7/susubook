"""Password hashing and authentication — layer 2 (Application).

Argon2id via argon2-cffi (NFR-03). The domain layer knows nothing about
credentials; hashes never appear on a domain entity.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.domain.entities import User

from .protocols import AuditRepository, UserRepository

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(password_hash: str, plaintext: str) -> bool:
    try:
        return _hasher.verify(password_hash, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


class AuthService:
    def __init__(self, users: UserRepository, audit: AuditRepository) -> None:
        self._users = users
        self._audit = audit

    def authenticate(self, phone: str, password: str) -> User | None:
        """Return the user on success, None otherwise (FR-01).

        A failed attempt is audited (NFR-09) but the caller is told only that
        authentication failed — never whether the phone number exists, which
        would let an attacker enumerate accounts.
        """
        found = self._users.find_credentials(phone.strip())

        if found is None:
            # Hash a dummy value so a missing account takes the same time as a
            # wrong password; otherwise response timing leaks which phone
            # numbers are registered.
            _hasher.hash("timing-equalisation-placeholder")
            self._audit.append(
                actor_id=None,
                action="LOGIN_FAILED",
                target_type="USER",
                target_id=None,
                detail={"reason": "unknown_account"},
            )
            return None

        user, password_hash = found
        if not verify_password(password_hash, password):
            self._audit.append(
                actor_id=user.id,
                action="LOGIN_FAILED",
                target_type="USER",
                target_id=str(user.id),
                detail={"reason": "bad_password"},
            )
            return None

        self._audit.append(
            actor_id=user.id, action="LOGIN", target_type="USER", target_id=str(user.id)
        )
        return user
