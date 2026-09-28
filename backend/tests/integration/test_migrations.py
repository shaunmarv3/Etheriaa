from uuid import uuid4

import psycopg
import pytest

from etheria.db.migrate import downgrade, upgrade


def _partitions(conn: psycopg.Connection, parent: str) -> list[str]:
    rows = conn.execute(
        "select c.relname from pg_inherits i join pg_class c on c.oid = i.inhrelid "
        "where i.inhparent = %s::regclass order by 1",
        (parent,),
    ).fetchall()
    return [r[0] for r in rows]


def test_extensions_are_installed(owner_conn: psycopg.Connection) -> None:
    ext = dict(owner_conn.execute("select extname, extversion from pg_extension").fetchall())
    assert ext["vector"].startswith("0.8")
    assert {"pg_trgm", "citext"} <= set(ext)


def test_audit_log_has_four_monthly_partitions_and_a_default(owner_conn: psycopg.Connection) -> None:
    parts = _partitions(owner_conn, "audit_log")
    assert "audit_log_default" in parts
    assert len(parts) == 5


def test_ensure_partitions_is_idempotent(owner_conn: psycopg.Connection) -> None:
    created = owner_conn.execute("select ensure_monthly_partitions('audit_log', 3)").fetchone()
    assert created == (0,)


def test_ensure_partitions_refuses_other_tables(owner_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.RaiseException):
        owner_conn.execute("select ensure_monthly_partitions('users', 1)")


def test_app_role_can_write_users(app_conn: psycopg.Connection) -> None:
    app_conn.execute(
        "insert into users (email, password_hash) values (%s, 'x')", (f"{uuid4().hex}@example.com",)
    )


def test_app_role_cannot_delete_audit_rows(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("delete from audit_log")


def test_app_role_cannot_read_a_partition_directly(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("select count(*) from audit_log_default")


def test_downgrade_then_upgrade_round_trips(scratch_database: str) -> None:
    upgrade(scratch_database)
    downgrade(scratch_database, "base")
    upgrade(scratch_database)
    with psycopg.connect(scratch_database) as conn:
        assert conn.execute("select to_regclass('users')").fetchone() == ("users",)
