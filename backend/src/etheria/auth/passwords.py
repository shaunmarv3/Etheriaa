"""argon2id password hashing (spec 9) with argon2-cffi's default parameters."""

from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


@cache
def dummy_hash() -> str:
    """Verified against when the email is unknown, so login timing does not reveal accounts."""
    return _hasher.hash("timing-equaliser-not-a-real-password")
