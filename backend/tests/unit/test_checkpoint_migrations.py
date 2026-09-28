"""Migration 0003 freezes the checkpointer's own schema (plan Decision 4). If a
library upgrade adds a checkpoint migration, this fails: add a new Alembic
migration with the new statements, because the app role cannot run DDL."""

import importlib.util
import re

from langgraph.checkpoint.postgres.base import BasePostgresSaver

from etheria.core.settings import BACKEND_DIR


def _migration():
    path = BACKEND_DIR / "migrations" / "versions" / "0003_checkpoints.py"
    spec = importlib.util.spec_from_file_location("m0003", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _norm(sql: str) -> str:
    sql = re.sub(r"\s+", " ", sql.replace("CONCURRENTLY ", "")).strip()
    return re.sub(r"\s*([(),;])\s*", r"\1", sql)


def test_migration_matches_the_installed_checkpointer() -> None:
    frozen = _migration().CHECKPOINT_MIGRATIONS
    assert [_norm(s) for s in frozen] == [_norm(s) for s in BasePostgresSaver.MIGRATIONS]


def test_no_concurrent_index_inside_the_transaction() -> None:
    assert all("CONCURRENTLY" not in s for s in _migration().CHECKPOINT_MIGRATIONS)
