"""Shared fixtures. Tests under tests/integration and tests/security need the
docker infra (infra/docker-compose.yml) and are marked `integration`."""

import asyncio
import base64
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from support import running_app

from etheria.core.settings import Settings

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
