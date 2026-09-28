import asyncio
from uuid import uuid4

import psycopg
import pytest

from etheria.auth.service import AuthService, ClientMeta, IssuedTokens
from etheria.core.errors import Conflict, NotAuthenticated
from etheria.core.settings import Settings
from etheria.db.session import Database

META = ClientMeta(ip="127.0.0.1", user_agent="pytest")
PW = "correct horse battery"


def new_email() -> str:
    return f"u{uuid4().hex[:12]}@example.com"


@pytest.fixture
def svc(db: Database, settings: Settings) -> AuthService:
    return AuthService(db, settings)


def _audit_count(conn: psycopg.Connection, action: str, user_ref: str) -> int:
    row = conn.execute(
        "select count(*) from audit_log where action = %s and user_ref = %s", (action, user_ref)
    ).fetchone()
    assert row is not None
    return row[0]


async def test_register_then_login(svc: AuthService) -> None:
    email = new_email()
    issued = await svc.register(email, PW, "Asha", META)
    assert issued.user.email == email
    assert issued.expires_in == 900
    again = await svc.login(email, PW, META)
    assert again.user.id == issued.user.id


async def test_email_is_normalised(svc: AuthService) -> None:
    local = uuid4().hex[:10]
    issued = await svc.register(f"  {local}@Example.COM ", PW, None, META)
    assert issued.user.email == f"{local}@example.com"
    assert (await svc.login(f"{local.upper()}@EXAMPLE.com", PW, META)).user.id == issued.user.id


async def test_duplicate_email_is_a_conflict(svc: AuthService) -> None:
    email = new_email()
    await svc.register(email, PW, None, META)
    with pytest.raises(Conflict) as err:
        await svc.register(email.upper(), "another password!", None, META)
    assert err.value.code == "email_taken"


async def test_wrong_password_and_unknown_email_look_identical(svc: AuthService) -> None:
    email = new_email()
    await svc.register(email, PW, None, META)
    with pytest.raises(NotAuthenticated) as wrong:
        await svc.login(email, "wrong password!!", META)
    with pytest.raises(NotAuthenticated) as unknown:
        await svc.login(new_email(), "wrong password!!", META)
    assert (wrong.value.code, wrong.value.message) == (unknown.value.code, unknown.value.message)
    assert wrong.value.code == "invalid_credentials"


async def test_refresh_rotates_the_token(svc: AuthService) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    rotated = await svc.refresh(issued.refresh_token, META)
    assert rotated.refresh_token != issued.refresh_token
    assert rotated.user.id == issued.user.id


async def test_reusing_a_rotated_token_revokes_the_family(
    svc: AuthService, owner_conn: psycopg.Connection
) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    rotated = await svc.refresh(issued.refresh_token, META)
    with pytest.raises(NotAuthenticated) as err:
        await svc.refresh(issued.refresh_token, META)
    assert err.value.code == "refresh_reused"
    with pytest.raises(NotAuthenticated):
        await svc.refresh(rotated.refresh_token, META)  # the whole family is dead
    assert _audit_count(owner_conn, "refresh_token_reuse", str(issued.user.id)) == 1


async def test_concurrent_refresh_never_issues_two_successors(svc: AuthService) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    results = await asyncio.gather(
        svc.refresh(issued.refresh_token, META),
        svc.refresh(issued.refresh_token, META),
        return_exceptions=True,
    )
    successes = [r for r in results if isinstance(r, IssuedTokens)]
    failures = [r for r in results if isinstance(r, NotAuthenticated)]
    assert len(successes) == 1
    assert len(failures) == 1 and failures[0].code == "refresh_reused"


async def test_expired_refresh_token_is_rejected(svc: AuthService, owner_conn: psycopg.Connection) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    owner_conn.execute(
        "update refresh_tokens set expires_at = now() - interval '1 second' where user_id = %s",
        (issued.user.id,),
    )
    with pytest.raises(NotAuthenticated) as err:
        await svc.refresh(issued.refresh_token, META)
    assert err.value.code == "invalid_refresh"


async def test_logout_revokes_without_flagging_reuse(
    svc: AuthService, owner_conn: psycopg.Connection
) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    await svc.logout(issued.refresh_token, META)
    with pytest.raises(NotAuthenticated) as err:
        await svc.refresh(issued.refresh_token, META)
    assert err.value.code == "invalid_refresh"
    assert _audit_count(owner_conn, "refresh_token_reuse", str(issued.user.id)) == 0


async def test_auth_events_are_audited(svc: AuthService, owner_conn: psycopg.Connection) -> None:
    email = new_email()
    issued = await svc.register(email, PW, None, META)
    await svc.login(email, PW, META)
    with pytest.raises(NotAuthenticated):
        await svc.login(email, "wrong password!!", META)
    uid = str(issued.user.id)
    assert _audit_count(owner_conn, "register", uid) == 1
    assert _audit_count(owner_conn, "login", uid) == 1
    assert _audit_count(owner_conn, "login_failed", uid) == 1


async def test_get_user_for_a_deleted_account_is_not_authenticated(
    svc: AuthService, owner_conn: psycopg.Connection
) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    owner_conn.execute("delete from users where id = %s", (issued.user.id,))
    with pytest.raises(NotAuthenticated):
        await svc.get_user(issued.user.id)
