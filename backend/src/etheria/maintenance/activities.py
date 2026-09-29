"""Maintenance activities: thin wrappers so Temporal retries and records each job."""

from typing import Any

from temporalio import activity

from etheria.db.session import Database
from etheria.maintenance import jobs


class MaintenanceActivities:
    def __init__(self, db: Database) -> None:
        self.db = db

    def all(self) -> list[Any]:
        return [self.ensure_partitions, self.drop_expired_audit, self.prune_checkpoints]

    @activity.defn
    async def ensure_partitions(self) -> int:
        return await jobs.ensure_partitions(self.db)

    @activity.defn
    async def drop_expired_audit(self) -> list[str]:
        return await jobs.drop_expired_audit(self.db)

    @activity.defn
    async def prune_checkpoints(self) -> int:
        return await jobs.prune_checkpoints(self.db)
