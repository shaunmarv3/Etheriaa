"""LangGraph checkpoint threads, deleted in SQL (spec 4.8).

The same three tables AsyncPostgresSaver.adelete_thread clears. Erasure and
the daily prune delete here, inside their own transaction, instead of through
the checkpointer (which the worker does not run)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")


async def delete_threads(session: AsyncSession, thread_ids: list[str]) -> None:
    if not thread_ids:
        return
    for table in TABLES:
        await session.execute(
            text(f"delete from {table} where thread_id = any(:ids)"), {"ids": thread_ids}
        )


async def prunable_threads(session: AsyncSession, idle_days: int) -> list[str]:
    """Threads whose conversation is deleted, gone, or idle `idle_days` (migration 0004)."""
    rows = await session.execute(
        text("select prunable_checkpoint_threads(:days)"), {"days": idle_days}
    )
    return sorted(rows.scalars())
