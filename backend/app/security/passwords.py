"""Argon2id password hashing.

Argon2id is memory-hard, which is what makes an offline attack on a stolen hash
expensive. Parameters below are the argon2-cffi defaults, which target roughly
the OWASP recommendation; they are stated explicitly so a future change is a
deliberate act rather than a library-default drift.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Argon2 verification of a wrong password still costs the full work factor, so
# an unknown username must burn the same time as a known one or the difference
# is a username oracle. This is a hash of a fixed dummy value, verified against
# whenever no user is found.
_DUMMY_HASH = _hasher.hash("account-does-not-exist")

MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time verification.

    Passing None (no such user) still performs a real Argon2 verification so
    the response time does not reveal whether the username exists.
    """
    if password_hash is None:
        try:
            _hasher.verify(_DUMMY_HASH, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            pass
        return False
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash used weaker parameters than we now require."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def validate_password_strength(password: str) -> None:
    """Raise ValueError if the password is unacceptable.

    Length is the dominant factor for a hashed secret, so this enforces a
    minimum length rather than composition rules that mostly push people toward
    predictable substitutions.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if password.strip() == "":
        raise ValueError("Password must not be blank")
