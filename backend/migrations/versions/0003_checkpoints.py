"""LangGraph checkpoint tables (spec 4.8, 8.2), created by the owner role.

`AsyncPostgresSaver.setup()` would run this DDL at app start, but the app
connects as etheria_app, which cannot run DDL. So the library's own schema
(langgraph-checkpoint-postgres 3.1, `BasePostgresSaver.MIGRATIONS`) is frozen
here with its version rows, and `setup()` is never called. `CONCURRENTLY` is
dropped because it cannot run inside a transaction and the tables are empty.
tests/unit/test_checkpoint_migrations.py fails if an installed library version
adds a migration: add a new Alembic migration then.

Checkpoint tables have no RLS: they are keyed by thread_id (text). The chat
service checks conversation ownership through the RLS-protected conversations
table before it touches a thread.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CHECKPOINT_MIGRATIONS = [
    "CREATE TABLE IF NOT EXISTS checkpoint_migrations (v INTEGER PRIMARY KEY);",
    """CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);""",
    """CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);""",
    """CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);""",
    "ALTER TABLE checkpoint_blobs ALTER COLUMN blob DROP not null;",
    "SELECT 1;",
    "CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);",
    "CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);",
    "CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);",
    "ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT '';",
]

TABLES = "checkpoint_migrations, checkpoints, checkpoint_blobs, checkpoint_writes"


def upgrade() -> None:
    bind = op.get_bind()
    for v, statement in enumerate(CHECKPOINT_MIGRATIONS):
        bind.exec_driver_sql(statement)
        # ON CONFLICT: a database where setup() already ran (the M0 spike) keeps its rows.
        bind.exec_driver_sql(
            f"INSERT INTO checkpoint_migrations (v) VALUES ({v}) ON CONFLICT (v) DO NOTHING"
        )
    bind.exec_driver_sql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLES} TO etheria_app")


def downgrade() -> None:
    op.get_bind().exec_driver_sql(f"DROP TABLE IF EXISTS {TABLES}")
