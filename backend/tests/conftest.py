"""Shared fixtures. Tests under tests/integration and tests/security need the
docker infra (infra/docker-compose.yml) and are marked `integration`."""

import asyncio
import sys

import pytest

if sys.platform == "win32":
    # psycopg async cannot use the ProactorEventLoop (see CLAUDE.md).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if {"integration", "security"} & set(item.path.parts):
            item.add_marker(pytest.mark.integration)
