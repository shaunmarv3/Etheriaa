"""Account erasure, DELETE /user (spec 7, 10, 11.2): every user row, file and
checkpoint thread goes; the audit log stays, pseudonymised."""

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from graph_fakes import FakeModels, streaming
from ingestion_fakes import REPORTS
from support import running_app

from etheria.core.settings import Settings
from etheria.graph.schemas import TriageAssessment, Understanding

PDF = (REPORTS / "lab_cbc.pdf").read_bytes()
USER_TABLES = (
    "conversations",
    "messages",
    "documents",
    "document_chunks",
    "lab_results",
    "medications",
    "refresh_tokens",
)


class FakeTemporal:
    async def start_workflow(self, *args, **kwargs):
        return None


def _models() -> FakeModels:
    return FakeModels(
        structured={
            "understand": [Understanding(intent="general_health")] * 4,
            "triage": [TriageAssessment(level="GREEN", reasons=["general"])] * 4,
        },
        chat={"generate": streaming("Rest and fluids help.")},
    )


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    return settings.model_copy(update={"upload_dir": tmp_path / "uploads"})


@pytest.fixture
async def client(settings, migrated_db, clean_redis) -> AsyncIterator[httpx.AsyncClient]:
    from etheria.api.app import create_app

    app = create_app(settings, chat_overrides={"models": _models(), "reranker": None})
    async with running_app(app) as c:
        app.state.temporal = FakeTemporal()
        yield c


async def _register(client: httpx.AsyncClient) -> tuple[dict[str, str], str]:
    email = f"{uuid4().hex[:10]}@example.com"
    r = await client.post("/auth/register", json={"email": email, "password": "correct horse 1"})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


async def _chat(client, headers) -> str:
    r = await client.post(
        "/chat/stream", json={"message": "How do I sleep better?"}, headers=headers
    )
    assert r.status_code == 200, r.text
    events = [json.loads(x[6:]) for x in r.text.splitlines() if x.startswith("data: ")]
    return events[-2]["session_id"]


def _count(conn: psycopg.Connection, table: str, user_id: str) -> int:
    return conn.execute(f"select count(*) from {table} where user_id = %s", (user_id,)).fetchone()[
        0
    ]


def _files(settings: Settings) -> list[Path]:
    root = settings.upload_dir
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


async def test_delete_user_erases_everything_and_pseudonymises_the_audit_log(
    client: httpx.AsyncClient, settings: Settings, owner_conn: psycopg.Connection
) -> None:
    headers, user_id = await _register(client)
    other_headers, other_id = await _register(client)
    session = await _chat(client, headers)
    other_session = await _chat(client, other_headers)
    for h in (headers, other_headers):
        r = await client.post("/upload/", headers=h, files={"file": ("cbc.pdf", PDF, "x/y")})
        assert r.status_code == 201, r.text
    assert len(_files(settings)) == 2
    assert owner_conn.execute(
        "select count(*) from audit_log where user_ref = %s", (user_id,)
    ).fetchone()[0]

    r = await client.delete("/user", headers=headers)
    assert r.status_code == 204, r.text
    assert "etheria_refresh" in r.headers.get("set-cookie", "")  # the cookie is cleared

    assert (
        owner_conn.execute("select count(*) from users where id = %s", (user_id,)).fetchone()[0]
        == 0
    )
    for table in USER_TABLES:
        assert _count(owner_conn, table, user_id) == 0, table
    assert len(_files(settings)) == 1  # only the other user's file is left
    app = client._transport.app  # type: ignore[attr-defined]
    graph = app.state.chat.graph
    assert (await graph.aget_state({"configurable": {"thread_id": session}})).values == {}
    kept = await graph.aget_state({"configurable": {"thread_id": other_session}})
    assert kept.values != {}

    key = settings.data_encryption_key.get_secret_value().encode()
    ref = (
        "erased:" + hmac.new(key, f"audit-user-ref:{user_id}".encode(), hashlib.sha256).hexdigest()
    )
    rows = owner_conn.execute(
        "select action from audit_log where user_ref = %s", (user_id,)
    ).fetchall()
    assert rows == []  # no audit row still names the user
    actions = {
        a
        for (a,) in owner_conn.execute(
            "select action from audit_log where user_ref = %s", (ref,)
        ).fetchall()
    }
    assert {"register", "upload", "erasure"} <= actions

    for table in ("conversations", "documents"):
        assert _count(owner_conn, table, other_id) == 1, table
    assert (await client.get("/auth/me", headers=headers)).status_code == 401
    assert (await client.get("/auth/me", headers=other_headers)).status_code == 200


async def test_delete_user_requires_auth(client: httpx.AsyncClient) -> None:
    assert (await client.delete("/user")).status_code == 401
