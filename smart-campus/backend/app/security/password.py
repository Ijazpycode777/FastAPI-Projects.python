"""Password hashing using Argon2id (argon2-cffi).

Argon2id is the recommended PHC winner for password hashing. We use the
Type.ID variant with configurable time/memory/parallelism parameters.
"""
from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import HashingError, InvalidHash, VerificationError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
    type=Type.ID,  # Argon2id
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Password must not be empty.")
    if len(plain) > settings.password_max_length:
        raise ValueError("Password exceeds maximum allowed length.")
    try:
        return _hasher.hash(plain)
    except HashingError as exc:  # pragma: no cover - defensive
        raise RuntimeError("Failed to hash password.") from exc


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if `plain` matches `hashed`. Constant time on the verify path."""
    if not plain or not hashed:
        return False
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHash):
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the hash was produced with parameters weaker than current."""
    try:
        return _hasher.check_needs_rehash(hashed)
    except (InvalidHash, Exception):  # noqa: BLE001
        return False


def is_strong_password(plain: str) -> tuple[bool, str | None]:
    """Enforce a sensible minimum complexity (length, upper/lower/digit/symbol)."""
    if len(plain) < settings.password_min_length:
        return False, f"Password must be at least {settings.password_min_length} characters."
    if len(plain) > settings.password_max_length:
        return False, f"Password must be at most {settings.password_max_length} characters."
    if not any(c.islower() for c in plain):
        return False, "Password must include a lowercase letter."
    if not any(c.isupper() for c in plain):
        return False, "Password must include an uppercase letter."
    if not any(c.isdigit() for c in plain):
        return False, "Password must include a digit."
    if not any(c in "!@#$%^&*()-_=+[]{};:,.<>?/" for c in plain):
        return False, "Password must include a symbol."
    return True, None
