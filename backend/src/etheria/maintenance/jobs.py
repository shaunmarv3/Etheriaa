"""The daily maintenance jobs (spec 4.8, 7, 11.2). Each is safe to run again.

1. Monthly partitions for messages and audit_log exist three months ahead, so
   no row falls into a default partition (readiness checks that).
2. audit_log months older than 12 months are dropped (DPDP log retention).
3. Checkpoint threads idle for 7 days, or whose conversation is deleted, are
   deleted; a pruned thread is rebuilt from `messages` on its next turn."""

import structlog
from pydantic import BaseModel
from sqlalchemy import text

from etheria.db.repositories import checkpoints
from etheria.db.session import Database

PARTITIONED = ("messages", "audit_log")
MONTHS_AHEAD = 3
AUDIT_KEEP_MONTHS = 12
IDLE_THREAD_DAYS = 7

log = structlog.get_logger("etheria.maintenance")


class MaintenanceReport(BaseModel):
    partitions_created: int
    partitions_dropped: list[str]
    threads_pruned: int


async def ensure_partitions(db: Database) -> int:
    made = 0
    async with db.system() as s:
        for parent in PARTITIONED:
            made += (
                await s.execute(
                    text("select ensure_monthly_partitions(:p, :n)"),
                    {"p": parent, "n": MONTHS_AHEAD},
                )
            ).scalar_one()
    return made


async def drop_expired_audit(db: Database) -> list[str]:
    async with db.system() as s:
        rows = await s.execute(
            text("select drop_expired_partitions('audit_log', :keep)"),
            {"keep": AUDIT_KEEP_MONTHS},
        )
        return list(rows.scalars())


async def prune_checkpoints(db: Database) -> int:
    async with db.system() as s:
        threads = await checkpoints.prunable_threads(s, IDLE_THREAD_DAYS)
        await checkpoints.delete_threads(s, threads)
    return len(threads)


async def run_all(db: Database) -> MaintenanceReport:
    report = MaintenanceReport(
        partitions_created=await ensure_partitions(db),
        partitions_dropped=await drop_expired_audit(db),
        threads_pruned=await prune_checkpoints(db),
    )
    log.info("maintenance.done", **report.model_dump())
    return report
