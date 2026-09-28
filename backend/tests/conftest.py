"""Shared fixtures. Tests under tests/integration and tests/security need the
docker infra (infra/docker-compose.yml) and are marked `integration`."""

import asyncio
import base64
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import psycopg
import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from redis.asyncio import Redis
from support import running_app

from etheria.core.settings import Settings
from etheria.db.session import Database

if sys.platform == "win32":
    # psycopg async cannot use the ProactorEventLoop (see CLAUDE.md).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BACKEND = Path(__file__).resolve().parent.parent
_ENV = dotenv_values(BACKEND / ".env")
TEST_DB = "etheria_test"


def _env(name: str, default: str) -> str:
    return os.getenv(name) or _ENV.get(name) or default


OWNER_URL = _env("DATABASE_OWNER_URL", "postgresql://etheria:etheria_dev@localhost:5433/etheria")
APP_URL = _env("DATABASE_URL", "postgresql://etheria_app:etheria_app_dev@localhost:5433/etheria")


def with_db(url: str, name: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + name


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if {"integration", "security"} & set(item.path.parts):
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        database_url=with_db(APP_URL, TEST_DB),
        database_owner_url=with_db(OWNER_URL, TEST_DB),
        redis_url=_env("REDIS_URL", "redis://localhost:6380/0").rsplit("/", 1)[0] + "/15",
        neo4j_uri=_env("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=_env("NEO4J_USER", "neo4j"),
        neo4j_password=_env("NEO4J_PASSWORD", "etheria_dev_pw"),
        temporal_address=_env("TEMPORAL_ADDRESS", "localhost:7233"),
        jwt_secret="test-secret-" + "x" * 32,
        data_encryption_key=base64.b64encode(bytes(32)).decode(),
        cors_origins=["http://localhost:3000"],
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    from etheria.api.app import create_app

    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with running_app(app) as c:
        yield c


def _recreate_database(name: str) -> None:
    with psycopg.connect(OWNER_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {name}")
        conn.execute(f"GRANT CONNECT ON DATABASE {name} TO etheria_app")


@pytest.fixture(scope="session")
def migrated_db() -> str:
    """Recreate etheria_test and migrate it to head, once per test session."""
    from etheria.db.migrate import upgrade

    _recreate_database(TEST_DB)
    upgrade(with_db(OWNER_URL, TEST_DB))
    return TEST_DB


@pytest.fixture
def owner_conn(migrated_db: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(with_db(OWNER_URL, TEST_DB), autocommit=True) as conn:
        yield conn


@pytest.fixture
def app_conn(migrated_db: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(with_db(APP_URL, TEST_DB), autocommit=True) as conn:
        yield conn


@pytest.fixture
async def db(settings: Settings, migrated_db: str) -> AsyncIterator[Database]:
    database = Database(settings.sqlalchemy_url)
    yield database
    await database.dispose()


@pytest.fixture
def scratch_database() -> Iterator[str]:
    name = "etheria_scratch"
    _recreate_database(name)
    yield with_db(OWNER_URL, name)
    with psycopg.connect(OWNER_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


@pytest.fixture
async def clean_redis(settings: Settings) -> AsyncIterator[None]:
    redis = Redis.from_url(settings.redis_url)
    await redis.flushdb()
    yield
    await redis.aclose()


@pytest.fixture
async def api_client(
    app: FastAPI, migrated_db: str, clean_redis: None
) -> AsyncIterator[httpx.AsyncClient]:
    async with running_app(app) as c:
        yield c
