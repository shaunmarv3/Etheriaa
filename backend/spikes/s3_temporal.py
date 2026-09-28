"""Spike 3 (spec D4, 5.3): a durable multi-step job that survives a worker restart.

Temporal concepts: a workflow is deterministic orchestration code whose history
is persisted by the server; activities do the I/O and are retried per policy.
If the worker dies mid-activity, the server re-dispatches that activity (after
its start_to_close timeout or heartbeat timeout) to whichever worker comes back.

Usage (three terminals, from backend/):
  1) uv run python spikes/s3_temporal.py worker      # start the worker
  2) uv run python spikes/s3_temporal.py start       # prints the workflow id
     ... when terminal 1 prints "step2 started", press Ctrl+C in terminal 1 ...
  3) uv run python spikes/s3_temporal.py status      # expect RUNNING
  1) uv run python spikes/s3_temporal.py worker      # restart the worker
  3) uv run python spikes/s3_temporal.py verify      # waits for the result, checks
"""

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

from temporalio import activity, workflow

# The workflow sandbox re-imports this module to check determinism. Pass our
# helpers (which touch the filesystem at import time) straight through.
with workflow.unsafe.imports_passed_through():
    from _common import BACKEND, check, load_env, run, summary
    from temporalio.client import Client, WorkflowExecutionStatus
    from temporalio.common import RetryPolicy
    from temporalio.worker import Worker

QUEUE = "m0-spike"
WF_ID = "m0-spike-restart"
LOG = BACKEND / "data" / "spike_s3_step1.log"


@activity.defn
async def step1(doc_id: str) -> str:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"step1 {doc_id}\n")  # side effect: must happen exactly once
    return "parsed"


@activity.defn
async def step2(prev: str) -> str:
    print("step2 started (kill the worker now)", flush=True)
    for _ in range(20):
        activity.heartbeat()
        await asyncio.sleep(1)
    return prev + "+classified"


@activity.defn
async def step3(prev: str) -> str:
    return prev + "+stored"


@workflow.defn
class SpikeIngest:
    @workflow.run
    async def run(self, doc_id: str) -> str:
        retry = RetryPolicy(maximum_attempts=3)
        a = await workflow.execute_activity(step1, doc_id, start_to_close_timeout=timedelta(seconds=30),
                                            retry_policy=retry)
        b = await workflow.execute_activity(step2, a, start_to_close_timeout=timedelta(seconds=60),
                                            heartbeat_timeout=timedelta(seconds=5), retry_policy=retry)
        return await workflow.execute_activity(step3, b, start_to_close_timeout=timedelta(seconds=30),
                                               retry_policy=retry)


async def client() -> Client:
    return await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))


async def main() -> int:
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    c = await client()
    if cmd == "worker":
        print("worker running; Ctrl+C to kill", flush=True)
        async with Worker(c, task_queue=QUEUE, workflows=[SpikeIngest], activities=[step1, step2, step3]):
            await asyncio.Event().wait()
    elif cmd == "start":
        LOG.unlink(missing_ok=True)
        h = await c.start_workflow(SpikeIngest.run, "doc-1", id=WF_ID, task_queue=QUEUE)
        print(f"started {h.id}")
    elif cmd == "status":
        d = await c.get_workflow_handle(WF_ID).describe()
        check("workflow still RUNNING with worker down", d.status == WorkflowExecutionStatus.RUNNING, str(d.status))
        return summary()
    elif cmd == "verify":
        result = await c.get_workflow_handle(WF_ID).result()
        check("workflow completed after restart", result == "parsed+classified+stored", result)
        lines = Path(LOG).read_text().splitlines()
        check("step1 ran exactly once", len(lines) == 1, f"{len(lines)} lines")
        return summary()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    run(main)
