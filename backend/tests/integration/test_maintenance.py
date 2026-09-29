"""The daily maintenance jobs (spec 4.8, 7, 11.2) against the real test database,
plus the workflow and its schedule against the Temporal dev server."""

from datetime import date
from uuid import uuid4

import psycopg
import pytest
from temporalio.worker import Worker

from etheria.core.settings import Settings
from etheria.db.session import Database
from etheria.ingestion.temporal import connect
from etheria.maintenance import jobs
from etheria.maintenance.activities import MaintenanceActivities
from etheria.maintenance.schedule import ensure_schedule
from etheria.maintenance.workflow import MaintenanceWorkflow


def _partitions(conn: psycopg.Connection, parent: str) -> set[str]:
    rows = conn.execute(
        "select c.relname from pg_inherits i join pg_class c on c.oid = i.inhrelid "
        "where i.inhparent = %s::regclass",
        (parent,),
    ).fetchall()
    return {r[0] for r in rows}


def _month_partition(conn: psycopg.Connection, parent: str, year: int, month: int) -> str:
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    name = f"{parent}_{year}_{month:02d}"
    conn.execute(
        f"create table if not exists {name} partition of {parent} "
        f"for values from ('{start}') to ('{end}')"
    )
    return name


def _thread(conn: psycopg.Connection, thread_id: str) -> None:
    conn.execute(
        "insert into checkpoints (thread_id, checkpoint_id, checkpoint) values (%s, %s, '{}')",
        (thread_id, uuid4().hex),
    )
    conn.execute(
        "insert into checkpoint_blobs (thread_id, channel, version, type) "
        "values (%s, 'messages', '1', 'empty')",
        (thread_id,),
    )


def _conversation(conn: psycopg.Connection, *, idle_days: int, deleted: bool = False) -> str:
    uid = conn.execute(
        "insert into users (email, password_hash) values (%s, 'x') returning id",
        (f"{uuid4().hex[:12]}@example.com",),
    ).fetchone()[0]
    return str(
        conn.execute(
            "insert into conversations (user_id, last_message_at, deleted_at) values "
            "(%s, now() - make_interval(days => %s), case when %s then now() end) returning id",
            (uid, idle_days, deleted),
        ).fetchone()[0]
    )


def _threads(conn: psycopg.Connection) -> set[str]:
    return {r[0] for r in conn.execute("select distinct thread_id from checkpoints").fetchall()}


def _month(offset: int) -> str:
    today = date.today()
    y, m = divmod(today.month - 1 + offset, 12)
    return f"{today.year + y}_{m + 1:02d}"


async def test_partitions_are_kept_three_months_ahead(db: Database, owner_conn) -> None:
    assert await jobs.ensure_partitions(db) == 0  # the migration already made them
    for parent in jobs.PARTITIONED:
        parts = _partitions(owner_conn, parent)
        assert {f"{parent}_{_month(i)}" for i in range(jobs.MONTHS_AHEAD + 1)} <= parts
        assert f"{parent}_{_month(jobs.MONTHS_AHEAD + 1)}" not in parts


async def test_only_audit_months_past_retention_are_dropped(db: Database, owner_conn) -> None:
    old = _month_partition(owner_conn, "audit_log", date.today().year - 2, 1)
    try:
        dropped = await jobs.drop_expired_audit(db)
    finally:
        owner_conn.execute(f"drop table if exists {old}")
    assert dropped == [old]
    this_month = f"audit_log_{date.today():%Y_%m}"
    assert this_month in _partitions(owner_conn, "audit_log")


def test_retention_cannot_go_below_a_year_or_touch_messages(app_conn) -> None:
    with pytest.raises(psycopg.errors.RaiseException):
        app_conn.execute("select drop_expired_partitions('audit_log', 1)")
    with pytest.raises(psycopg.errors.RaiseException):
        app_conn.execute("select drop_expired_partitions('messages', 12)")


def test_app_role_cannot_drop_a_partition_directly(app_conn) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute(f"drop table audit_log_{date.today():%Y_%m}")


async def test_idle_deleted_and_orphan_threads_are_pruned(db: Database, owner_conn) -> None:
    active = _conversation(owner_conn, idle_days=1)
    idle = _conversation(owner_conn, idle_days=jobs.IDLE_THREAD_DAYS + 1)
    deleted = _conversation(owner_conn, idle_days=0, deleted=True)
    orphan = str(uuid4())
    for t in (active, idle, deleted, orphan):
        _thread(owner_conn, t)

    pruned = await jobs.prune_checkpoints(db)

    left = _threads(owner_conn)
    assert active in left
    assert not {idle, deleted, orphan} & left
    assert pruned >= 3
    blobs = owner_conn.execute(
        "select count(*) from checkpoint_blobs where thread_id = any(%s)", ([idle, deleted],)
    ).fetchone()
    assert blobs == (0,)


async def test_workflow_runs_all_three_jobs(settings: Settings, db: Database, owner_conn) -> None:
    idle = _conversation(owner_conn, idle_days=30)
    _thread(owner_conn, idle)
    client = await connect(settings)
    queue = f"test-maint-{uuid4().hex}"
    async with Worker(
        client,
        task_queue=queue,
        workflows=[MaintenanceWorkflow],
        activities=MaintenanceActivities(db).all(),
    ):
        report = await client.execute_workflow(
            MaintenanceWorkflow.run, id=f"maint-{uuid4().hex}", task_queue=queue
        )
    assert report.partitions_created == 0
    assert report.partitions_dropped == []
    assert report.threads_pruned >= 1
    assert idle not in _threads(owner_conn)


async def test_schedule_is_created_once(settings: Settings) -> None:
    client = await connect(settings)
    sid = f"test-maint-{uuid4().hex}"
    try:
        assert await ensure_schedule(client, "unused-queue", sid) is True
        assert await ensure_schedule(client, "unused-queue", sid) is False
        desc = await client.get_schedule_handle(sid).describe()
        assert desc.schedule.spec.intervals[0].every.days == 1
    finally:
        await client.get_schedule_handle(sid).delete()
