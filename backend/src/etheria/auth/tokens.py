"""Access tokens (HS256 JWT, 15 minutes) and opaque refresh tokens (spec 9)."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt

from etheria.core.clock import utcnow


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    jti: str
    expires_at: datetime


def create_access_token(user_id: UUID, secret: str, ttl_seconds: int) -> str:
    now = int(utcnow().timestamp())
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl_seconds, "jti": uuid4().hex}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token, secret, algorithms=["HS256"], options={"require": ["exp", "iat", "sub", "jti"]}
        )
        return AccessClaims(
            user_id=UUID(payload["sub"]),
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError) as e:
        raise InvalidToken(str(e)) from e


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
