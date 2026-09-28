from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest

from etheria.auth.tokens import (
    InvalidToken,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
    new_refresh_token,
)

SECRET = "k" * 40


def test_access_token_round_trips() -> None:
    uid = uuid4()
    claims = decode_access_token(create_access_token(uid, SECRET, 900), SECRET)
    assert claims.user_id == uid
    assert len(claims.jti) == 32
    assert claims.expires_at > datetime.now(UTC)


def test_expired_token_is_rejected() -> None:
    with pytest.raises(InvalidToken):
        decode_access_token(create_access_token(uuid4(), SECRET, -10), SECRET)


def test_token_signed_with_another_secret_is_rejected() -> None:
    with pytest.raises(InvalidToken):
        decode_access_token(create_access_token(uuid4(), "z" * 40, 900), SECRET)


def test_unsigned_token_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": str(uuid4()), "iat": 0, "exp": 9_999_999_999, "jti": "x"}, None, algorithm="none"
    )
    with pytest.raises(InvalidToken):
        decode_access_token(forged, SECRET)


def test_token_without_jti_is_rejected() -> None:
    now = int(datetime.now(UTC).timestamp())
    token = jwt.encode({"sub": str(uuid4()), "iat": now, "exp": now + 60}, SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_access_token(token, SECRET)


def test_token_with_a_non_uuid_subject_is_rejected() -> None:
    now = int(datetime.now(UTC).timestamp())
    token = jwt.encode({"sub": "admin", "iat": now, "exp": now + 60, "jti": "j"}, SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_access_token(token, SECRET)


def test_refresh_tokens_are_random_and_stored_hashed() -> None:
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b
    assert len(a) >= 43  # 32 random bytes, base64url
    assert hash_refresh_token(a) == hash_refresh_token(a)
    assert len(hash_refresh_token(a)) == 64
    assert hash_refresh_token(a) != a
