import httpx
import psycopg
from support import running_app

from etheria.api.app import create_app
from etheria.core.settings import Settings


async def test_ready_when_every_dependency_is_up(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/health/ready")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "status": "ready",
        "checks": {"postgres": "ok", "redis": "ok", "neo4j": "ok", "temporal": "ok"},
    }


async def test_not_ready_when_redis_is_down(settings: Settings, migrated_db: str) -> None:
    broken = settings.model_copy(update={"redis_url": "redis://localhost:6399/0"})
    async with running_app(create_app(broken)) as client:
        r = await client.get("/health/ready")
    assert r.status_code == 503
    checks = r.json()["checks"]
    assert checks["redis"].startswith("error")
    assert checks["postgres"] == "ok"


async def test_not_ready_when_a_default_partition_has_rows(
    api_client: httpx.AsyncClient, owner_conn: psycopg.Connection
) -> None:
    owner_conn.execute("insert into audit_log (created_at, action) values ('2000-01-01', 'stray')")
    try:
        r = await api_client.get("/health/ready")
    finally:
        owner_conn.execute("delete from audit_log where action = 'stray'")
    assert r.status_code == 503
    assert "default partition" in r.json()["checks"]["postgres"]
