"""Row-level security is the second line of defence (spec 7). These tests talk to
Postgres as the app role and prove isolation holds even when a query forgets its
user filter."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from etheria.core.settings import Settings
from etheria.db.session import Database

USER_TABLES = [
    "conversations", "messages", "documents", "document_chunks", "lab_results", "medications",
]


@dataclass(frozen=True)
class Tenant:
    user_id: UUID
    conversation_id: UUID
    document_id: UUID


def _one(conn: psycopg.Connection, sql: str, params: tuple) -> UUID:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def _seed(conn: psycopg.Connection) -> Tenant:
    uid = _one(conn, "insert into users (email, password_hash) values (%s, 'x') returning id",
               (f"{uuid4().hex[:12]}@example.com",))
    conv = _one(conn, "insert into conversations (user_id, title) values (%s, 'chat') returning id",
                (uid,))
    conn.execute("insert into messages (conversation_id, user_id, role, content) "
                 "values (%s, %s, 'user', 'hi')", (conv, uid))
    doc = _one(conn, "insert into documents (user_id, filename, mime_type, storage_key, sha256, "
                     "size_bytes) values (%s, 'r.pdf', 'application/pdf', %s, %s, 10) returning id",
               (uid, uuid4().hex, uuid4().hex))
    conn.execute("insert into document_chunks (document_id, user_id, chunk_index, source_kind, "
                 "content, embedding) values (%s, %s, 0, 'text_layer', 'Hb 10.9', "
                 "array_fill(0.1::real, ARRAY[1024])::vector)", (doc, uid))
    conn.execute("insert into lab_results (user_id, document_id, test_name, value_text, flag) "
                 "values (%s, %s, 'Haemoglobin', '10.9', 'low')", (uid, doc))
    conn.execute("insert into medications (user_id, document_id, name_raw, source) "
                 "values (%s, %s, 'Dolo 650', 'prescription')", (uid, doc))
    return Tenant(uid, conv, doc)


@pytest.fixture
def tenants(owner_conn: psycopg.Connection) -> tuple[Tenant, Tenant]:
    return _seed(owner_conn), _seed(owner_conn)


@pytest.mark.parametrize("table", USER_TABLES)
async def test_user_sees_only_own_rows(db: Database, tenants: tuple[Tenant, Tenant], table: str) -> None:
    a, _ = tenants
    async with db.for_user(a.user_id) as s:
        owners = set((await s.execute(text(f"select user_id from {table}"))).scalars())
    assert owners == {a.user_id}


@pytest.mark.parametrize("table", USER_TABLES)
async def test_no_user_context_sees_nothing(db: Database, tenants: tuple[Tenant, Tenant], table: str) -> None:
    async with db.system() as s:
        count = (await s.execute(text(f"select count(*) from {table}"))).scalar_one()
    assert count == 0


async def test_cannot_insert_a_row_for_another_user(db: Database, tenants: tuple[Tenant, Tenant]) -> None:
    a, b = tenants
    with pytest.raises(DBAPIError, match="row-level security"):
        async with db.for_user(a.user_id) as s:
            await s.execute(text("insert into conversations (user_id, title) values (:u, 'x')"),
                            {"u": b.user_id})


async def test_cannot_update_or_delete_another_users_rows(db: Database, tenants: tuple[Tenant, Tenant]) -> None:
    a, b = tenants
    async with db.for_user(a.user_id) as s:
        updated = await s.execute(text("update conversations set title = 'pwned' where id = :c"),
                                  {"c": b.conversation_id})
        deleted = await s.execute(text("delete from lab_results where user_id = :u"), {"u": b.user_id})
    assert (updated.rowcount, deleted.rowcount) == (0, 0)


async def test_cannot_attach_a_message_to_another_users_conversation(
    db: Database, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    with pytest.raises(IntegrityError):
        async with db.for_user(a.user_id) as s:
            await s.execute(
                text("insert into messages (conversation_id, user_id, role, content) "
                     "values (:c, :u, 'user', 'x')"),
                {"c": b.conversation_id, "u": a.user_id},
            )


async def test_user_context_does_not_leak_through_the_pool(
    settings: Settings, migrated_db: str, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    single = Database(settings.sqlalchemy_url, pool_size=1, max_overflow=0)
    try:
        async with single.for_user(a.user_id) as s:
            assert (await s.execute(text("select count(*) from conversations"))).scalar_one() == 1
        async with single.system() as s:
            leaked = (await s.execute(text("select count(*) from conversations"))).scalar_one()
    finally:
        await single.dispose()
    assert leaked == 0


def test_app_role_cannot_read_a_messages_partition_directly(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("select count(*) from messages_default")


def test_app_role_cannot_write_reference_data(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("insert into drug_synonyms (alias, canonical) values ('x', 'y')")


def test_default_partitions_start_empty(app_conn: psycopg.Connection) -> None:
    assert app_conn.execute("select default_partitions_empty()").fetchone() == (True,)
