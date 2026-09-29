"""Forged and malformed access tokens (spec 9): only an HS256 token signed with
our secret, carrying every required claim, for a user that exists, is accepted."""

import time
from uuid import uuid4

import httpx
import jwt
import pytest

from etheria.core.settings import Settings


async def _user(client: httpx.AsyncClient) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": f"u{uuid4().hex[:12]}@example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 201, r.text
    return r.json()["user"]["id"]


def _claims(sub: str, **over) -> dict:
    now = int(time.time())
    return {"sub": sub, "iat": now, "exp": now + 600, "jti": uuid4().hex} | over


# The HS512 forgery uses our (HS256-sized) secret on purpose.
@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
async def test_forged_tokens_are_refused(api_client: httpx.AsyncClient, settings: Settings) -> None:
    sub = await _user(api_client)
    secret = settings.jwt_secret.get_secret_value()
    good = jwt.encode(_claims(sub), secret, algorithm="HS256")
    no_exp = _claims(sub)
    del no_exp["exp"]
    forged = {
        "alg none": jwt.encode(_claims(sub), None, algorithm="none"),
        "wrong secret": jwt.encode(_claims(sub), "not-the-secret-" + "y" * 32, algorithm="HS256"),
        "other algorithm": jwt.encode(_claims(sub), secret, algorithm="HS512"),
        "no exp": jwt.encode(no_exp, secret, algorithm="HS256"),
        "expired": jwt.encode(_claims(sub, exp=int(time.time()) - 5), secret, algorithm="HS256"),
        "sub not a uuid": jwt.encode(_claims("admin"), secret, algorithm="HS256"),
        "unknown user": jwt.encode(_claims(str(uuid4())), secret, algorithm="HS256"),
        "tampered payload": good[: good.index(".") + 1] + "e30" + good[good.rindex(".") :],
    }
    for name, token in forged.items():
        r = await api_client.get("/history/", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, name
        assert r.json()["error"]["code"] == "token_invalid", name
    ok = await api_client.get("/history/", headers={"Authorization": f"Bearer {good}"})
    assert ok.status_code == 200
