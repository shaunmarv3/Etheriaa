from uuid import uuid4

import httpx

from etheria.auth.tokens import create_access_token
from etheria.core.settings import Settings

ORIGIN = "http://localhost:3000"
CSRF = {"Origin": ORIGIN, "X-Requested-With": "fetch"}
PW = "correct horse battery"


def new_email() -> str:
    return f"u{uuid4().hex[:12]}@example.com"


async def register(client: httpx.AsyncClient, email: str | None = None, password: str = PW) -> httpx.Response:
    return await client.post("/auth/register", json={"email": email or new_email(), "password": password})


async def call_refresh(
    client: httpx.AsyncClient, token: str, headers: dict[str, str] = CSRF
) -> httpx.Response:
    client.cookies.clear()
    return await client.post("/auth/refresh", headers={**headers, "Cookie": f"etheria_refresh={token}"})


async def test_register_returns_a_token_and_sets_the_refresh_cookie(api_client: httpx.AsyncClient) -> None:
    email = new_email()
    r = await register(api_client, email)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900 and body["access_token"]
    assert body["user"]["email"] == email
    cookie = r.headers["set-cookie"].lower()
    for part in ("etheria_refresh=", "httponly", "path=/auth", "samesite=lax", "max-age=1209600"):
        assert part in cookie


async def test_email_is_normalised_and_case_insensitive(api_client: httpx.AsyncClient) -> None:
    local = uuid4().hex[:10]
    r = await register(api_client, f"  {local}@Example.COM ")
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == f"{local}@example.com"
    login = await api_client.post("/auth/login", json={"email": f"{local}@EXAMPLE.com", "password": PW})
    assert login.status_code == 200
    again = await register(api_client, f"{local.upper()}@example.com")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_taken"


async def test_short_password_is_rejected_without_echoing_it(api_client: httpx.AsyncClient) -> None:
    r = await register(api_client, password="tiny-pw-9")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert "tiny-pw-9" not in r.text


async def test_login_failures_are_uniform(api_client: httpx.AsyncClient) -> None:
    email = new_email()
    await register(api_client, email)
    wrong = await api_client.post("/auth/login", json={"email": email, "password": "wrong password!!"})
    unknown = await api_client.post("/auth/login", json={"email": new_email(), "password": "wrong password!!"})
    assert wrong.status_code == unknown.status_code == 401
    strip = lambda r: {k: v for k, v in r.json()["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(wrong) == strip(unknown)


async def test_me_requires_a_valid_access_token(api_client: httpx.AsyncClient, settings: Settings) -> None:
    r = await register(api_client)
    token, user_id = r.json()["access_token"], r.json()["user"]["id"]

    missing = await api_client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "not_authenticated"
    assert missing.headers["www-authenticate"] == "Bearer"

    garbage = await api_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert garbage.json()["error"]["code"] == "token_invalid"

    expired = create_access_token(uuid4(), settings.jwt_secret.get_secret_value(), -10)
    stale = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert stale.status_code == 401

    ok = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["id"] == user_id


async def test_refresh_rotates_and_detects_reuse(api_client: httpx.AsyncClient) -> None:
    first = (await register(api_client)).cookies["etheria_refresh"]
    rotated = await call_refresh(api_client, first)
    assert rotated.status_code == 200, rotated.text
    second = rotated.cookies["etheria_refresh"]
    assert second != first

    reused = await call_refresh(api_client, first)
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_reused"
    assert (await call_refresh(api_client, second)).status_code == 401


async def test_refresh_requires_same_origin_headers(api_client: httpx.AsyncClient) -> None:
    token = (await register(api_client)).cookies["etheria_refresh"]
    no_header = await call_refresh(api_client, token, headers={"Origin": ORIGIN})
    evil = await call_refresh(api_client, token, headers={"Origin": "https://evil.example", "X-Requested-With": "fetch"})
    assert no_header.status_code == evil.status_code == 403
    assert no_header.json()["error"]["code"] == "csrf_failed"
    assert (await call_refresh(api_client, token)).status_code == 200  # still valid after the blocked attempts


async def test_refresh_without_a_cookie_is_401(api_client: httpx.AsyncClient) -> None:
    api_client.cookies.clear()
    r = await api_client.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_refresh"


async def test_logout_revokes_and_clears_the_cookie(api_client: httpx.AsyncClient) -> None:
    token = (await register(api_client)).cookies["etheria_refresh"]
    api_client.cookies.clear()
    out = await api_client.post("/auth/logout", headers={**CSRF, "Cookie": f"etheria_refresh={token}"})
    assert out.status_code == 204
    assert "max-age=0" in out.headers["set-cookie"].lower()
    after = await call_refresh(api_client, token)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "invalid_refresh"


async def test_login_is_rate_limited(api_client: httpx.AsyncClient) -> None:
    email = new_email()
    body = {"email": email, "password": "wrong password!!"}
    codes = [(await api_client.post("/auth/login", json=body)).status_code for _ in range(5)]
    assert codes == [401] * 5
    blocked = await api_client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1


async def test_register_is_rate_limited_per_ip(api_client: httpx.AsyncClient) -> None:
    codes = [(await register(api_client)).status_code for _ in range(6)]
    assert codes == [201] * 5 + [429]


async def test_cors_allows_only_the_frontend_origin(api_client: httpx.AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = await api_client.options("/auth/login", headers={"Origin": ORIGIN, **preflight})
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    assert ok.headers["access-control-allow-credentials"] == "true"
    evil = await api_client.options("/auth/login", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in evil.headers
