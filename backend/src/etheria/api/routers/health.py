"""Liveness and readiness (spec 10)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from etheria.db.session import Database
from etheria.ingestion.temporal import connect

router = APIRouter(tags=["health"])
CHECK_TIMEOUT_S = 3.0


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness: every dependency answers, and no row has fallen into a default partition."""
    state = request.app.state
    probes: dict[str, Callable[[], Awaitable[Any]]] = {
        "postgres": lambda: _postgres(state.db),
        "redis": lambda: state.redis.ping(),
        "neo4j": lambda: state.neo4j.verify_connectivity(),
        "temporal": lambda: _temporal(state),
    }
    results = await asyncio.gather(*(_probe(fn) for fn in probes.values()))
    checks = dict(zip(probes, results, strict=True))
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ready" if ok else "not_ready", "checks": checks},
        status_code=200 if ok else 503,
    )


async def _probe(fn: Callable[[], Awaitable[Any]]) -> str:
    try:
        await asyncio.wait_for(fn(), CHECK_TIMEOUT_S)
        return "ok"
    except Exception as e:  # a readiness probe reports failures, it never raises
        return f"error: {type(e).__name__}: {e}"[:200]


async def _postgres(db: Database) -> None:
    async with db.system() as s:
        if not (await s.execute(text("select default_partitions_empty()"))).scalar_one():
            raise RuntimeError("rows in a default partition (a monthly partition is missing)")


async def _temporal(state: Any) -> None:
    if state.temporal is None:
        state.temporal = await connect(state.settings)
    if not await state.temporal.service_client.check_health():
        raise RuntimeError("temporal reports unhealthy")
