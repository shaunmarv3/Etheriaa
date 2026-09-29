"""The daily Temporal Schedule for MaintenanceWorkflow (spec 3).

A Temporal Schedule is a server-side cron: the server starts the workflow
every day and records each run in its history (UI on :8233). The worker
creates it at start when it does not exist yet."""

from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleSpec,
)

from etheria.maintenance.workflow import MaintenanceWorkflow

SCHEDULE_ID = "maintenance-daily"
EVERY = timedelta(days=1)


async def ensure_schedule(client: Client, task_queue: str, schedule_id: str = SCHEDULE_ID) -> bool:
    """Create the daily schedule; False when it already exists (the server keeps it)."""
    try:
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    MaintenanceWorkflow.run, id=schedule_id, task_queue=task_queue
                ),
                spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=EVERY)]),
            ),
        )
    except ScheduleAlreadyRunningError:
        return False
    return True
