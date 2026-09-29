"""MaintenanceWorkflow (spec 4.8): the three daily jobs as activities, in order.
Deterministic orchestration only; the I/O is in activities.py."""

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from etheria.maintenance.activities import MaintenanceActivities as A
    from etheria.maintenance.jobs import MaintenanceReport

OPTS: dict[str, Any] = {
    "start_to_close_timeout": timedelta(minutes=5),
    "retry_policy": RetryPolicy(maximum_attempts=3),
}


@workflow.defn
class MaintenanceWorkflow:
    @workflow.run
    async def run(self) -> MaintenanceReport:
        return MaintenanceReport(
            partitions_created=await workflow.execute_activity_method(A.ensure_partitions, **OPTS),
            partitions_dropped=await workflow.execute_activity_method(A.drop_expired_audit, **OPTS),
            threads_pruned=await workflow.execute_activity_method(A.prune_checkpoints, **OPTS),
        )
