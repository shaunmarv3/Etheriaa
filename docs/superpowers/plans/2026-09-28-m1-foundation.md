# M1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running FastAPI foundation: settings, JSON logging with request ids, a single error shape, the full Postgres schema (row-level security, monthly partitions), our own auth (argon2id, 15-minute JWT, rotating refresh cookie with reuse detection), health and readiness endpoints, import-linter contracts, and a test harness against the real infrastructure.

**Architecture:** `backend/src/etheria/` is a modular monolith. `core` (settings, errors, logging, clock) imports nothing from etheria. `db` owns the engine and the two ways to open a transaction (`system()` with no user context, `for_user()` with `app.user_id` set locally for RLS). `auth` holds the use cases and its router; `cache` holds the Redis rate limiter; `api` assembles the app. Migrations are hand-written SQL run by Alembic as the owner role; the app connects as `etheria_app`, which RLS applies to.

**Tech Stack:** FastAPI 0.141, uvicorn 0.54, SQLAlchemy 2.1 (async, psycopg 3 driver), Alembic 1.20, pydantic-settings 2.15, argon2-cffi 25.1, PyJWT 2.15, structlog 26.1, typer 0.27, redis-py 8.1, neo4j driver 6.3, temporalio 1.33, pytest 9 + pytest-asyncio 1.4, ruff 0.16, import-linter 2.15.

**Spec:** `docs/superpowers/specs/2026-09-28-etheria-v2-design.md` (sections 3.2, 3.3, 7, 9, 10, 11, 14, 15, 17). M0 facts: `docs/spikes/m0-results.md`.

## Global Constraints

- Never modify anything under `D:\Etheria\`.
- Python 3.12 via uv; run everything from `backend/` with `uv run`.
- psycopg async needs the selector event loop on Windows: entry points use `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)`; pytest sets `WindowsSelectorEventLoopPolicy` in `tests/conftest.py`.
- Infra host ports: Postgres 5433, Redis 6380, Neo4j 7687, Temporal 7233.
- The app connects as `etheria_app` (`DATABASE_URL`); migrations and test seeding use the owner `etheria` (`DATABASE_OWNER_URL`).
- Error body everywhere: `{"error": {"code", "message", "request_id"}}` (spec 10).
- Never log or echo request bodies, passwords, tokens or health content (spec 14).
- Access token: HS256 JWT, 15 minutes, claims `sub`, `iat`, `exp`, `jti`. Refresh token: 256-bit opaque, stored as SHA-256, 14 days, cookie `etheria_refresh`, httpOnly, `SameSite=Lax`, `Path=/auth`, rotated on every refresh, reuse revokes the family (spec 9).
- Rate limits: login 5/min per IP + email; register 5/min per IP.
- Migration SQL contains no `%` characters and runs through `exec_driver_sql` (no driver-side parameter parsing).
- Console output ASCII only.

## Review Focus

1. **Two tabs refreshing at once** with the same cookie: exactly one succeeds and the other is treated as reuse; never two valid successors, never a 500. (Task 7 test `test_concurrent_refresh_never_issues_two_successors`; the frontend must single-flight refresh, recorded in spec 13 in Task 10.)
2. **Email case and whitespace:** `" Asha@Example.COM "` registers as `asha@example.com`, logs in with any case, and a second registration in another case is a 409. (Task 8 `test_email_is_normalised_and_case_insensitive`.)
3. **Validation errors echoing secrets:** a rejected password must not appear in the 422 body. (Task 8 `test_short_password_is_rejected_without_echoing_it`.)
4. **RLS context leaking through the connection pool** from one user's transaction to the next caller. (Task 5 `test_user_context_does_not_leak_through_the_pool`.)
5. **A row that points at another user's parent** (a message in someone else's conversation) passes plain FKs because RI checks bypass RLS. Composite FKs `(parent_id, user_id)` reject it. (Task 5 `test_cannot_attach_a_message_to_another_users_conversation`.)

---

## File structure

```text
backend/
  pyproject.toml                      # deps, scripts, ruff, pytest, import-linter contracts
  alembic.ini
  migrations/env.py  script.py.mako
  migrations/versions/0001_foundation.py      # extensions, grants, users, refresh_tokens, audit_log
  migrations/versions/0002_user_data_rls.py   # user data tables, RLS, reference tables
  src/etheria/
    cli.py                            # typer: api | migrate
    core/{settings,errors,logging,clock}.py
    db/{session,migrate,models}.py  db/repositories/{users,refresh_tokens,audit}.py
    auth/{passwords,tokens,schemas,service,dependencies,router}.py
    cache/rate_limit.py
    api/{app,middleware,errors}.py  api/routers/health.py
    llm/ graph/ retrieval/ knowledge/ medical_apis/ ingestion/ safety/ voice/ seed/   # empty packages (contracts)
  tests/
    conftest.py  support.py
    unit/test_import_contracts.py  unit/test_settings.py  unit/test_app_basics.py
    unit/test_passwords.py  unit/test_tokens.py
    integration/test_migrations.py  integration/test_auth_service.py
    integration/test_auth_api.py  integration/test_rate_limit.py  integration/test_health.py
    security/test_rls.py
```

Code blocks below are introduced by `File: \`path\`` (create or replace the whole file) or `Append to: \`path\``. Paths are relative to the repo root.

---

### Task 1: Tooling, package skeleton and import contracts

**Files:**
- Modify: `backend/pyproject.toml` (whole file)
- Create: the empty packages listed in the file structure, `backend/tests/conftest.py`, `backend/tests/unit/test_import_contracts.py`

**Interfaces:**
- Produces: the `etheria` console script (`etheria.cli:app`, written in Task 3), pytest config (`asyncio_mode = "auto"`, marker `integration`), import-linter contracts for spec 3.3.

- [ ] **Step 1: Replace `backend/pyproject.toml`**

File: `backend/pyproject.toml`
```toml
[project]
name = "etheria"
version = "0.1.0"
description = "Etheria v2: India-aware AI health assistant (portfolio project, synthetic data only)"
requires-python = ">=3.12,<3.13"
dependencies = [
    "langchain>=1.4,<2",
    "langchain-core>=1.6,<2",
    "langgraph>=1.2.11,<2",
    "langchain-deepseek>=1.1,<2",
    "langgraph-checkpoint-postgres>=3.1,<4",
    "psycopg[binary,pool]>=3.3,<4",
    "temporalio>=1.33,<2",
    "httpx>=0.28,<1",
    "pydantic[email]>=2.13,<3",
    "python-dotenv>=1.2,<2",
    "fastapi>=0.141,<1",
    "uvicorn>=0.54,<1",
    "sqlalchemy[asyncio]>=2.1,<3",
    "alembic>=1.20,<2",
    "pydantic-settings>=2.15,<3",
    "argon2-cffi>=25.1,<26",
    "pyjwt>=2.15,<3",
    "structlog>=26.1,<27",
    "typer>=0.27,<1",
    "redis>=8.1,<9",
    "neo4j>=6.3,<7",
]

[project.scripts]
etheria = "etheria.cli:app"

[dependency-groups]
dev = [
    "pytest>=9.1,<10",
    "pytest-asyncio>=1.4,<2",
    "ruff>=0.16,<0.17",
    "import-linter>=2.15,<3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/etheria"]

[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = ["spikes"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-ra --strict-markers"
markers = ["integration: needs the docker infra (postgres, redis, neo4j, temporal)"]

# Spec 3.3 dependency rules.
[tool.importlinter]
root_package = "etheria"

[[tool.importlinter.contracts]]
name = "Nothing imports api"
type = "forbidden"
source_modules = [
    "etheria.core", "etheria.db", "etheria.auth", "etheria.cache", "etheria.llm",
    "etheria.graph", "etheria.retrieval", "etheria.knowledge", "etheria.medical_apis",
    "etheria.ingestion", "etheria.safety", "etheria.voice", "etheria.seed",
]
forbidden_modules = ["etheria.api"]

[[tool.importlinter.contracts]]
name = "core imports nothing from etheria"
type = "forbidden"
source_modules = ["etheria.core"]
forbidden_modules = [
    "etheria.db", "etheria.auth", "etheria.cache", "etheria.llm", "etheria.graph",
    "etheria.retrieval", "etheria.knowledge", "etheria.medical_apis", "etheria.ingestion",
    "etheria.safety", "etheria.voice", "etheria.seed", "etheria.api", "etheria.cli",
]

[[tool.importlinter.contracts]]
name = "ingestion never imports graph"
type = "forbidden"
source_modules = ["etheria.ingestion"]
forbidden_modules = [
    "etheria.graph", "etheria.auth", "etheria.knowledge", "etheria.medical_apis",
    "etheria.voice", "etheria.seed",
]

[[tool.importlinter.contracts]]
name = "Leaf services never import graph or ingestion"
type = "forbidden"
source_modules = [
    "etheria.knowledge", "etheria.retrieval", "etheria.medical_apis", "etheria.safety",
    "etheria.voice",
]
forbidden_modules = ["etheria.graph", "etheria.ingestion"]

[[tool.importlinter.contracts]]
name = "graph imports only its allowed layers"
type = "forbidden"
source_modules = ["etheria.graph"]
forbidden_modules = ["etheria.ingestion", "etheria.auth", "etheria.voice", "etheria.seed"]
```

Run: `cd backend && uv sync`
Expected: resolves and installs the new packages; `uv.lock` updated.

- [ ] **Step 2: Write the conftest and the failing contract test**

File: `backend/tests/conftest.py`
```python
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
```

File: `backend/tests/unit/test_import_contracts.py`
```python
"""Spec 3.3 dependency rules, enforced by import-linter."""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def test_import_contracts_hold() -> None:
    exe = Path(sys.executable).with_name("lint-imports.exe" if sys.platform == "win32" else "lint-imports")
    result = subprocess.run([str(exe)], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 3: Run it to see it fail**

Run: `cd backend && uv run pytest tests/unit/test_import_contracts.py -q`
Expected: FAIL; the output names a missing module such as `etheria.core`.

- [ ] **Step 4: Create the package skeleton**

Create an empty `__init__.py` in each of: `core`, `db`, `db/repositories`, `auth`, `cache`, `api`, `api/routers`, `llm`, `graph`, `retrieval`, `knowledge`, `medical_apis`, `ingestion`, `safety`, `voice`, `seed` under `backend/src/etheria/`.

Run:
```bash
cd backend/src/etheria && for p in core db db/repositories auth cache api api/routers llm graph retrieval knowledge medical_apis ingestion safety voice seed; do mkdir -p $p && touch $p/__init__.py; done
```

- [ ] **Step 5: Run the test to see it pass, then prove it catches a violation**

Run: `cd backend && uv run pytest tests/unit/test_import_contracts.py -q`
Expected: `1 passed`.

Then temporarily put `import etheria.api  # noqa: F401` in `backend/src/etheria/core/__init__.py` and re-run.
Expected: FAIL naming "core imports nothing from etheria" and "Nothing imports api". Empty the file again and re-run: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/etheria backend/tests
git commit -m "build: M1 dependencies, package skeleton and import-linter contracts"
```

---

### Task 2: Settings, errors, logging, clock

**Files:**
- Create: `backend/src/etheria/core/settings.py`, `core/errors.py`, `core/logging.py`, `core/clock.py`, `backend/tests/unit/test_settings.py`
- Modify: `backend/.env.example`, `backend/.env` (generated secrets), `backend/tests/conftest.py` (append `settings` fixture)

**Interfaces:**
- Produces: `Settings` (fields below), `get_settings() -> Settings` (cached), `to_psycopg_url(url: str) -> str`, `BACKEND_DIR: Path`; `Settings.sqlalchemy_url`, `Settings.sqlalchemy_owner_url` properties.
- Produces: `AppError(message, *, code=None, headers=None)` with `.status_code`, `.code`, `.message`, `.headers`; subclasses `NotAuthenticated` (401), `Forbidden` (403), `NotFound` (404), `Conflict` (409), `RateLimited(retry_after: int)` (429, `Retry-After` header).
- Produces: `configure_logging(level: str = "INFO") -> None`; `utcnow() -> datetime` (aware, UTC).
- Produces: pytest fixture `settings` (test database `etheria_test`, Redis DB 15).

- [ ] **Step 1: Write the failing test**

File: `backend/tests/unit/test_settings.py`
```python
import base64

import pytest
from pydantic import ValidationError

from etheria.core.settings import Settings, to_psycopg_url

KEY = base64.b64encode(bytes(32)).decode()
BASE = {
    "_env_file": None,
    "database_url": "postgresql://a:b@h:1/d",
    "database_owner_url": "postgresql://o:p@h:1/d",
    "neo4j_password": "pw",
    "jwt_secret": "s" * 32,
    "data_encryption_key": KEY,
}


def test_defaults_match_spec() -> None:
    s = Settings(**BASE)
    assert s.access_token_ttl_seconds == 900
    assert s.refresh_token_ttl_days == 14
    assert s.cookie_secure is False


def test_missing_jwt_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(**{k: v for k, v in BASE.items() if k != "jwt_secret"})


def test_short_jwt_secret_fails() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(**{**BASE, "jwt_secret": "short"})


@pytest.mark.parametrize("key", ["not-base64!!", base64.b64encode(bytes(16)).decode()])
def test_bad_encryption_key_fails(key: str) -> None:
    with pytest.raises(ValidationError, match="data_encryption_key"):
        Settings(**{**BASE, "data_encryption_key": key})


def test_secrets_do_not_appear_in_repr() -> None:
    assert "s" * 32 not in repr(Settings(**BASE))


def test_psycopg_url() -> None:
    assert to_psycopg_url("postgresql://u:p@h:5433/d") == "postgresql+psycopg://u:p@h:5433/d"
    assert Settings(**BASE).sqlalchemy_url == "postgresql+psycopg://a:b@h:1/d"
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd backend && uv run pytest tests/unit/test_settings.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'etheria.core.settings'`.

- [ ] **Step 3: Implement the core modules**

File: `backend/src/etheria/core/settings.py`
```python
"""Configuration from the environment (backend/.env). Startup fails when a
required secret is missing or malformed (spec 11.1, secret leakage row)."""

import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]


def to_psycopg_url(url: str) -> str:
    """postgresql://... -> postgresql+psycopg://... (SQLAlchemy's psycopg 3 driver)."""
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    env: Literal["dev", "test"] = "dev"
    log_level: str = "INFO"

    database_url: str
    database_owner_url: str
    redis_url: str = "redis://localhost:6380/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    temporal_address: str = "localhost:7233"

    jwt_secret: SecretStr
    data_encryption_key: SecretStr
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 14
    cors_origins: list[str] = ["http://localhost:3000"]
    cookie_secure: bool = False

    deepseek_api_key: SecretStr | None = None
    ncbi_api_key: SecretStr | None = None
    bioportal_api_key: SecretStr | None = None

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_is_long(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @field_validator("data_encryption_key")
    @classmethod
    def _encryption_key_is_32_bytes(cls, v: SecretStr) -> SecretStr:
        try:
            raw = base64.b64decode(v.get_secret_value(), validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError("DATA_ENCRYPTION_KEY must be base64") from e
        if len(raw) != 32:
            raise ValueError("DATA_ENCRYPTION_KEY must decode to 32 bytes (AES-256)")
        return v

    @property
    def sqlalchemy_url(self) -> str:
        return to_psycopg_url(self.database_url)

    @property
    def sqlalchemy_owner_url(self) -> str:
        return to_psycopg_url(self.database_owner_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
```

File: `backend/src/etheria/core/errors.py`
```python
"""Application errors. The api layer renders every one of them as
{"error": {"code", "message", "request_id"}} (spec 10)."""


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self, message: str, *, code: str | None = None, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.headers = headers or {}


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "Too many attempts, try again shortly", headers={"Retry-After": str(retry_after)}
        )
```

File: `backend/src/etheria/core/logging.py`
```python
"""Structured JSON logs (spec 14). Request ids are bound per request by the api
middleware through structlog's contextvars. Never log bodies or health content."""

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
```

File: `backend/src/etheria/core/clock.py`
```python
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
```

- [ ] **Step 4: Run the test to see it pass**

Run: `cd backend && uv run pytest tests/unit/test_settings.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Add the `settings` fixture**

Append to: `backend/tests/conftest.py`
```python


import base64  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

from dotenv import dotenv_values  # noqa: E402

from etheria.core.settings import Settings  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
_ENV = dotenv_values(BACKEND / ".env")
TEST_DB = "etheria_test"


def _env(name: str, default: str) -> str:
    return os.getenv(name) or _ENV.get(name) or default


OWNER_URL = _env("DATABASE_OWNER_URL", "postgresql://etheria:etheria_dev@localhost:5433/etheria")
APP_URL = _env("DATABASE_URL", "postgresql://etheria_app:etheria_app_dev@localhost:5433/etheria")


def with_db(url: str, name: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + name


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
```
Then move those imports to the top of the file so ruff's `E402` markers are unnecessary (the final conftest has one import block).

- [ ] **Step 6: Update `.env.example` and generate local secrets**

File: `backend/.env.example`
```dotenv
# Copy to backend/.env and fill in. backend/.env is gitignored.
# The owner uses DeepSeek only (spec D3). NCBI and BioPortal are needed from M2.
DEEPSEEK_API_KEY=
NCBI_API_KEY=
BIOPORTAL_API_KEY=

# Generate fresh, never reuse: JWT_SECRET >= 32 chars; DATA_ENCRYPTION_KEY = base64 of 32 bytes.
#   uv run python -c "import secrets,base64;print(secrets.token_urlsafe(48));print(base64.b64encode(secrets.token_bytes(32)).decode())"
JWT_SECRET=
DATA_ENCRYPTION_KEY=

# JSON list. COOKIE_SECURE=true whenever served over HTTPS.
CORS_ORIGINS=["http://localhost:3000"]
COOKIE_SECURE=false

# App role (RLS applies) and owner role (migrations, seeding).
# Host ports 5433 / 6380: 5432 and 6379 are taken by native services on the owner's machine.
DATABASE_URL=postgresql://etheria_app:etheria_app_dev@localhost:5433/etheria
DATABASE_OWNER_URL=postgresql://etheria:etheria_dev@localhost:5433/etheria
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=etheria_dev_pw
REDIS_URL=redis://localhost:6380/0
TEMPORAL_ADDRESS=localhost:7233
```

Add `JWT_SECRET`, `DATA_ENCRYPTION_KEY`, `CORS_ORIGINS` and `COOKIE_SECURE` to the local `backend/.env` without printing the values, and drop the unused `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` lines:
```bash
cd backend && uv run python -c "
import base64, secrets, pathlib
p = pathlib.Path('.env')
keep = [l for l in p.read_text().splitlines() if l.split('=')[0] not in ('ANTHROPIC_API_KEY','OPENAI_API_KEY','JWT_SECRET','DATA_ENCRYPTION_KEY','CORS_ORIGINS','COOKIE_SECURE')]
keep += ['JWT_SECRET=' + secrets.token_urlsafe(48), 'DATA_ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode(), 'CORS_ORIGINS=[\"http://localhost:3000\"]', 'COOKIE_SECURE=false']
p.write_text('\n'.join(keep) + '\n')
print('secrets generated')"
uv run python -c "from etheria.core.settings import get_settings; s = get_settings(); print('settings OK', s.access_token_ttl_seconds)"
```
Expected: `secrets generated`, then `settings OK 900`.

- [ ] **Step 7: Run the unit suite and commit**

Run: `cd backend && uv run pytest tests/unit -q`
Expected: all pass.

```bash
git add backend/src/etheria/core backend/tests backend/.env.example
git commit -m "feat(core): settings with secret validation, error types, JSON logging"
```

---

### Task 3: App factory, request ids, error shape, `/health`, CLI

**Files:**
- Create: `backend/src/etheria/api/app.py`, `api/middleware.py`, `api/errors.py`, `api/routers/health.py`, `backend/src/etheria/cli.py`, `backend/src/etheria/db/session.py`, `backend/tests/support.py`, `backend/tests/unit/test_app_basics.py`
- Modify: `backend/tests/conftest.py` (append `app`, `client` fixtures)

**Interfaces:**
- Consumes: `Settings`, `get_settings`, `configure_logging`, `AppError` (Task 2).
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`. App state: `settings`, `db: Database`, `redis: redis.asyncio.Redis`, `neo4j: neo4j.AsyncDriver`, `temporal: temporalio.client.Client | None`.
- Produces: `Database(url, *, pool_size=5, max_overflow=5)` with `system()` and `for_user(user_id)` async context managers yielding `AsyncSession` inside a transaction, and `dispose()`.
- Produces: `tests/support.py::running_app(app) -> AsyncContextManager[httpx.AsyncClient]`; fixtures `app` and `client` (no database needed).
- Produces: `error_response(request, status, code, message, headers=None) -> JSONResponse`.

- [ ] **Step 1: Write the failing tests**

File: `backend/tests/support.py`
```python
"""Test helpers importable from any test module (tests/ is on sys.path)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI


@asynccontextmanager
async def running_app(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Run the app's lifespan and give an in-process HTTP client."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
```

Append to: `backend/tests/conftest.py`
```python


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    from etheria.api.app import create_app

    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with running_app(app) as c:
        yield c
```
(Add `from collections.abc import AsyncIterator`, `import httpx`, `from fastapi import FastAPI`, `from support import running_app` to the conftest import block.)

File: `backend/tests/unit/test_app_basics.py`
```python
import json

import httpx
import pytest
from fastapi import FastAPI
from typer.testing import CliRunner

from etheria.cli import app as cli_app
from etheria.core.errors import Conflict


async def test_health_is_ok_and_carries_a_request_id(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert len(r.headers["x-request-id"]) == 32


async def test_a_safe_incoming_request_id_is_kept(client: httpx.AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


async def test_an_unsafe_incoming_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "bad id <script>"})
    assert r.headers["x-request-id"] != "bad id <script>"
    assert len(r.headers["x-request-id"]) == 32


async def test_not_found_uses_the_error_shape(client: httpx.AsyncClient) -> None:
    r = await client.get("/nope")
    assert r.status_code == 404
    assert r.json() == {
        "error": {"code": "not_found", "message": "Not Found", "request_id": r.headers["x-request-id"]}
    }


async def test_app_errors_map_to_status_and_code(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def taken() -> None:
        raise Conflict("That name is taken", code="email_taken")

    app.add_api_route("/test/conflict", taken)
    r = await client.get("/test/conflict")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"
    assert r.json()["error"]["message"] == "That name is taken"


async def test_unhandled_errors_are_500_without_internals(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def crash() -> None:
        raise RuntimeError("secret internals")

    app.add_api_route("/test/crash", crash)
    r = await client.get("/test/crash")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.json()["error"]["request_id"]
    assert "secret internals" not in r.text


async def test_each_request_is_logged_as_json(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    r = await client.get("/health")
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    entry = next(e for e in lines if e.get("event") == "request")
    assert entry["request_id"] == r.headers["x-request-id"]
    assert (entry["path"], entry["status"]) == ("/health", 200)


def test_cli_lists_its_commands() -> None:
    result = CliRunner().invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "api" in result.output and "migrate" in result.output
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/unit/test_app_basics.py -q`
Expected: FAIL (collection error: no module `etheria.api.app` / `etheria.cli`).

- [ ] **Step 3: Implement**

File: `backend/src/etheria/db/session.py`
```python
"""The engine and the two ways to open a transaction (spec 7, row-level security).

The app connects as etheria_app, which does not own the tables, so RLS applies.
`for_user` sets app.user_id with set_config(..., is_local => true): the value
lives only until the transaction ends and never leaks to the next borrower of a
pooled connection."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str, *, pool_size: int = 5, max_overflow: int = 5) -> None:
        self.engine = create_async_engine(
            url, pool_pre_ping=True, pool_size=pool_size, max_overflow=max_overflow
        )
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def system(self) -> AsyncIterator[AsyncSession]:
        """A transaction with no user context: RLS tables return no rows. For the
        auth tables, public reference data and health checks."""
        async with self._sessions() as session, session.begin():
            yield session

    @asynccontextmanager
    async def for_user(self, user_id: UUID) -> AsyncIterator[AsyncSession]:
        """A transaction that sees only this user's rows."""
        async with self._sessions() as session, session.begin():
            await session.execute(
                text("select set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
            )
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
```

File: `backend/src/etheria/api/middleware.py`
```python
"""Per-request context: a request id on every log line and response (spec 14).

Pure ASGI (not BaseHTTPMiddleware) so SSE streams in M4 pass through untouched."""

import re
import time
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
log = structlog.get_logger("etheria.request")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        status = 500
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            log.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
```

File: `backend/src/etheria/api/errors.py`
```python
"""One error shape for every failure: {"error": {"code", "message", "request_id"}} (spec 10)."""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from etheria.core.errors import AppError

log = structlog.get_logger("etheria.errors")

_HTTP_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


def error_response(
    request: Request, status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        {"error": {"code": code, "message": message, "request_id": request_id}},
        status_code=status,
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return error_response(request, exc.status_code, code, str(exc.detail), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo the submitted input: it may be a password.
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body", "query", "path"))
        detail = first.get("msg", "Invalid input")
        return error_response(
            request, 422, "validation_error", f"{field}: {detail}" if field else detail
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return error_response(request, 500, "internal_error", "Something went wrong")
```

File: `backend/src/etheria/api/routers/health.py`
```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}
```

File: `backend/src/etheria/api/app.py`
```python
"""FastAPI application factory (spec 3.1). The api package sits on top: it may
import anything, and nothing imports it (import-linter enforces this)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis

from etheria.api.errors import install_error_handlers
from etheria.api.middleware import RequestContextMiddleware
from etheria.api.routers import health
from etheria.core.logging import configure_logging
from etheria.core.settings import Settings, get_settings
from etheria.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Clients connect lazily: the app starts even when a dependency is down,
        # and /health/ready reports which one.
        app.state.db = Database(settings.sqlalchemy_url)
        app.state.redis = Redis.from_url(settings.redis_url)
        app.state.neo4j = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        )
        app.state.temporal = None
        try:
            yield
        finally:
            await app.state.neo4j.close()
            await app.state.redis.aclose()
            await app.state.db.dispose()

    app = FastAPI(title="Etheria v2", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)  # outermost: every response gets X-Request-ID
    install_error_handlers(app)
    app.include_router(health.router)
    return app
```

File: `backend/src/etheria/cli.py`
```python
"""Command-line entry point: `uv run etheria <command>`."""

import asyncio
import sys

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _loop_factory() -> type[asyncio.AbstractEventLoop] | None:
    # psycopg async cannot use Windows' default ProactorEventLoop.
    return asyncio.SelectorEventLoop if sys.platform == "win32" else None


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the FastAPI app."""
    import uvicorn

    from etheria.api.app import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), host=host, port=port, log_config=None))
    asyncio.run(server.serve(), loop_factory=_loop_factory())


@app.command()
def migrate() -> None:
    """Apply database migrations as the owner role."""
    from etheria.core.settings import get_settings
    from etheria.db.migrate import upgrade

    upgrade(get_settings().database_owner_url)
    typer.echo("database migrated to head")
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/unit -q`
Expected: all pass (the app tests need no running services: clients connect lazily).

- [ ] **Step 5: Smoke-run the server**

Run (background), then probe:
```bash
cd backend && (uv run etheria api --port 8011 > ../.superpowers/api-smoke.log 2>&1 &) ; sleep 6; curl -s localhost:8011/health; echo; curl -s -i localhost:8011/nope | head -1
```
Expected: `{"status":"ok"}` and `HTTP/1.1 404 Not Found`. Stop the server afterwards (`taskkill //F //IM etheria.exe` or close the process).

- [ ] **Step 6: Commit**

```bash
git add backend/src/etheria backend/tests
git commit -m "feat(api): app factory, request-id middleware, error shape, /health, CLI"
```

---

### Task 4: Migrations 0001 and the database test harness

**Files:**
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_foundation.py`, `backend/src/etheria/db/migrate.py`, `backend/tests/integration/test_migrations.py`
- Modify: `backend/tests/conftest.py` (append database fixtures)

**Interfaces:**
- Consumes: `BACKEND_DIR`, `to_psycopg_url`, `get_settings` (Task 2); `Database` (Task 3).
- Produces: `etheria.db.migrate.upgrade(owner_url: str, revision: str = "head")`, `downgrade(owner_url: str, revision: str)`.
- Produces SQL objects: `app_current_user() -> uuid`; `ensure_monthly_partitions(parent text, months_ahead int) -> int` (only `messages` and `audit_log`; SECURITY DEFINER; revokes `etheria_app` on each new partition); tables `users`, `refresh_tokens`, `audit_log` (partitioned, `audit_log_default`).
- Produces fixtures: `migrated_db` (session), `owner_conn`, `app_conn` (sync psycopg, autocommit), `db` (async `Database` as the app role), `scratch_database` (owner URL of a throwaway database).

- [ ] **Step 1: Write the failing tests and fixtures**

Append to: `backend/tests/conftest.py`
```python


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
```
(Add `from collections.abc import Iterator`, `import psycopg`, `from etheria.db.session import Database` to the import block.)

File: `backend/tests/integration/test_migrations.py`
```python
from uuid import uuid4

import psycopg
import pytest

from etheria.db.migrate import downgrade, upgrade


def _partitions(conn: psycopg.Connection, parent: str) -> list[str]:
    rows = conn.execute(
        "select c.relname from pg_inherits i join pg_class c on c.oid = i.inhrelid "
        "where i.inhparent = %s::regclass order by 1",
        (parent,),
    ).fetchall()
    return [r[0] for r in rows]


def test_extensions_are_installed(owner_conn: psycopg.Connection) -> None:
    ext = dict(owner_conn.execute("select extname, extversion from pg_extension").fetchall())
    assert ext["vector"].startswith("0.8")
    assert {"pg_trgm", "citext"} <= set(ext)


def test_audit_log_has_four_monthly_partitions_and_a_default(owner_conn: psycopg.Connection) -> None:
    parts = _partitions(owner_conn, "audit_log")
    assert "audit_log_default" in parts
    assert len(parts) == 5


def test_ensure_partitions_is_idempotent(owner_conn: psycopg.Connection) -> None:
    created = owner_conn.execute("select ensure_monthly_partitions('audit_log', 3)").fetchone()
    assert created == (0,)


def test_ensure_partitions_refuses_other_tables(owner_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.RaiseException):
        owner_conn.execute("select ensure_monthly_partitions('users', 1)")


def test_app_role_can_write_users(app_conn: psycopg.Connection) -> None:
    app_conn.execute(
        "insert into users (email, password_hash) values (%s, 'x')", (f"{uuid4().hex}@example.com",)
    )


def test_app_role_cannot_delete_audit_rows(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("delete from audit_log")


def test_app_role_cannot_read_a_partition_directly(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("select count(*) from audit_log_default")


def test_downgrade_then_upgrade_round_trips(scratch_database: str) -> None:
    upgrade(scratch_database)
    downgrade(scratch_database, "base")
    upgrade(scratch_database)
    with psycopg.connect(scratch_database) as conn:
        assert conn.execute("select to_regclass('users')").fetchone() == ("users",)
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/integration/test_migrations.py -q`
Expected: FAIL (`No module named 'etheria.db.migrate'`).

- [ ] **Step 3: Implement Alembic and migration 0001**

File: `backend/alembic.ini`
```ini
# Migrations are hand-written SQL; run them with `uv run etheria migrate`.
[alembic]
script_location = migrations
sqlalchemy.url =
```

File: `backend/migrations/env.py`
```python
"""Alembic environment. Migrations are hand-written SQL (RLS, partitions,
SECURITY DEFINER functions) and always run as the owner role."""

from alembic import context
from sqlalchemy import create_engine, pool

from etheria.core.settings import to_psycopg_url


def _owner_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    if not url:
        from etheria.core.settings import get_settings

        url = get_settings().database_owner_url
    return to_psycopg_url(url)


def run() -> None:
    engine = create_engine(_owner_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


run()
```

File: `backend/migrations/script.py.mako`
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None

UPGRADE = """
"""

DOWNGRADE = """
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE)
```

File: `backend/migrations/versions/0001_foundation.py`
```python
"""Foundation: extensions, app-role grants, auth tables, partitioned audit log.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'etheria_app') THEN
    RAISE EXCEPTION 'role etheria_app is missing: infra/postgres/init/01-app-role.sh creates it';
  END IF;
END
$$;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

-- Every table the owner creates from here on is usable by the app role.
GRANT USAGE ON SCHEMA public TO etheria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO etheria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO etheria_app;

-- The user a request runs as (spec 7). NULL when unset, so RLS returns no rows.
CREATE FUNCTION app_current_user() RETURNS uuid
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext NOT NULL UNIQUE,
  password_hash text NOT NULL,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  family_id uuid NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  replaced_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  user_agent text
);
CREATE INDEX refresh_tokens_family_idx ON refresh_tokens (family_id);
CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);

CREATE TABLE audit_log (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  user_ref text,
  action text NOT NULL,
  resource_type text,
  resource_id text,
  ip inet,
  user_agent text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX audit_log_user_ref_idx ON audit_log (user_ref, created_at);
CREATE TABLE audit_log_default PARTITION OF audit_log DEFAULT;
REVOKE ALL ON audit_log_default FROM etheria_app;
-- Kept for a year (spec 11.2): the app may add and pseudonymise rows, never delete them.
REVOKE DELETE ON audit_log FROM etheria_app;

CREATE FUNCTION ensure_monthly_partitions(parent text, months_ahead int) RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  first_month date := date_trunc('month', now())::date;
  month_start date;
  part text;
  made int := 0;
BEGIN
  IF parent NOT IN ('messages', 'audit_log') THEN
    RAISE EXCEPTION USING MESSAGE = 'ensure_monthly_partitions: ' || parent || ' is not managed';
  END IF;
  FOR i IN 0..months_ahead LOOP
    month_start := (first_month + make_interval(months => i))::date;
    part := parent || '_' || to_char(month_start, 'YYYY_MM');
    IF to_regclass(part) IS NULL THEN
      EXECUTE 'CREATE TABLE ' || quote_ident(part) || ' PARTITION OF ' || quote_ident(parent)
           || ' FOR VALUES FROM (' || quote_literal(month_start) || ') TO ('
           || quote_literal((month_start + interval '1 month')::date) || ')';
      -- Reading a partition directly would bypass the parent's RLS policy.
      EXECUTE 'REVOKE ALL ON ' || quote_ident(part) || ' FROM etheria_app';
      made := made + 1;
    END IF;
  END LOOP;
  RETURN made;
END
$$;
REVOKE ALL ON FUNCTION ensure_monthly_partitions(text, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ensure_monthly_partitions(text, int) TO etheria_app;

SELECT ensure_monthly_partitions('audit_log', 3);
"""

DOWNGRADE = """
DROP FUNCTION IF EXISTS ensure_monthly_partitions(text, int);
DROP TABLE IF EXISTS audit_log, refresh_tokens, users CASCADE;
DROP FUNCTION IF EXISTS app_current_user();
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM etheria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM etheria_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE)
```

File: `backend/src/etheria/db/migrate.py`
```python
"""Programmatic Alembic, used by `etheria migrate` and the test harness."""

from alembic import command
from alembic.config import Config

from etheria.core.settings import BACKEND_DIR


def _config(owner_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", owner_url.replace("%", "%%"))  # configparser escaping
    return cfg


def upgrade(owner_url: str, revision: str = "head") -> None:
    command.upgrade(_config(owner_url), revision)


def downgrade(owner_url: str, revision: str) -> None:
    command.downgrade(_config(owner_url), revision)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/integration/test_migrations.py -q`
Expected: `8 passed`.

- [ ] **Step 5: Migrate the dev database**

Run: `cd backend && uv run etheria migrate`
Expected: `database migrated to head`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/migrations backend/src/etheria/db/migrate.py backend/tests
git commit -m "feat(db): alembic with migration 0001 (grants, auth tables, partitioned audit log)"
```

---

### Task 5: Migration 0002: user data, RLS, reference tables

**Files:**
- Create: `backend/migrations/versions/0002_user_data_rls.py`, `backend/tests/security/test_rls.py`

**Interfaces:**
- Consumes: `app_current_user()`, `ensure_monthly_partitions` (Task 4); `Database.system()`, `Database.for_user()` (Task 3); fixtures `db`, `owner_conn`, `app_conn`, `settings`, `migrated_db`.
- Produces tables (spec 7): `conversations`, `messages` (partitioned; `messages_default`), `documents`, `document_chunks`, `lab_results`, `medications` (all with RLS policy `<table>_owner`), `medicine_brands`, `drug_synonyms` (read-only to the app). Composite FKs `(conversation_id, user_id)` and `(document_id, user_id)`. Function `default_partitions_empty() -> boolean` (SECURITY DEFINER, executable by the app role).

- [ ] **Step 1: Write the failing tests**

File: `backend/tests/security/test_rls.py`
```python
"""Row-level security is the second line of defence (spec 7). These tests talk to
Postgres as the app role and prove isolation holds even when a query forgets its
user filter."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from etheria.core.settings import Settings
from etheria.db.session import Database

USER_TABLES = [
    "conversations", "messages", "documents", "document_chunks", "lab_results", "medications",
]


@dataclass(frozen=True)
class Tenant:
    user_id: UUID
    conversation_id: UUID
    document_id: UUID


def _one(conn: psycopg.Connection, sql: str, params: tuple) -> UUID:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def _seed(conn: psycopg.Connection) -> Tenant:
    uid = _one(conn, "insert into users (email, password_hash) values (%s, 'x') returning id",
               (f"{uuid4().hex[:12]}@example.com",))
    conv = _one(conn, "insert into conversations (user_id, title) values (%s, 'chat') returning id",
                (uid,))
    conn.execute("insert into messages (conversation_id, user_id, role, content) "
                 "values (%s, %s, 'user', 'hi')", (conv, uid))
    doc = _one(conn, "insert into documents (user_id, filename, mime_type, storage_key, sha256, "
                     "size_bytes) values (%s, 'r.pdf', 'application/pdf', %s, %s, 10) returning id",
               (uid, uuid4().hex, uuid4().hex))
    conn.execute("insert into document_chunks (document_id, user_id, chunk_index, source_kind, "
                 "content, embedding) values (%s, %s, 0, 'text_layer', 'Hb 10.9', "
                 "array_fill(0.1::real, ARRAY[1024])::vector)", (doc, uid))
    conn.execute("insert into lab_results (user_id, document_id, test_name, value_text, flag) "
                 "values (%s, %s, 'Haemoglobin', '10.9', 'low')", (uid, doc))
    conn.execute("insert into medications (user_id, document_id, name_raw, source) "
                 "values (%s, %s, 'Dolo 650', 'prescription')", (uid, doc))
    return Tenant(uid, conv, doc)


@pytest.fixture
def tenants(owner_conn: psycopg.Connection) -> tuple[Tenant, Tenant]:
    return _seed(owner_conn), _seed(owner_conn)


@pytest.mark.parametrize("table", USER_TABLES)
async def test_user_sees_only_own_rows(db: Database, tenants: tuple[Tenant, Tenant], table: str) -> None:
    a, _ = tenants
    async with db.for_user(a.user_id) as s:
        owners = set((await s.execute(text(f"select user_id from {table}"))).scalars())
    assert owners == {a.user_id}


@pytest.mark.parametrize("table", USER_TABLES)
async def test_no_user_context_sees_nothing(db: Database, tenants: tuple[Tenant, Tenant], table: str) -> None:
    async with db.system() as s:
        count = (await s.execute(text(f"select count(*) from {table}"))).scalar_one()
    assert count == 0


async def test_cannot_insert_a_row_for_another_user(db: Database, tenants: tuple[Tenant, Tenant]) -> None:
    a, b = tenants
    with pytest.raises(DBAPIError, match="row-level security"):
        async with db.for_user(a.user_id) as s:
            await s.execute(text("insert into conversations (user_id, title) values (:u, 'x')"),
                            {"u": b.user_id})


async def test_cannot_update_or_delete_another_users_rows(db: Database, tenants: tuple[Tenant, Tenant]) -> None:
    a, b = tenants
    async with db.for_user(a.user_id) as s:
        updated = await s.execute(text("update conversations set title = 'pwned' where id = :c"),
                                  {"c": b.conversation_id})
        deleted = await s.execute(text("delete from lab_results where user_id = :u"), {"u": b.user_id})
    assert (updated.rowcount, deleted.rowcount) == (0, 0)


async def test_cannot_attach_a_message_to_another_users_conversation(
    db: Database, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    with pytest.raises(IntegrityError):
        async with db.for_user(a.user_id) as s:
            await s.execute(
                text("insert into messages (conversation_id, user_id, role, content) "
                     "values (:c, :u, 'user', 'x')"),
                {"c": b.conversation_id, "u": a.user_id},
            )


async def test_user_context_does_not_leak_through_the_pool(
    settings: Settings, migrated_db: str, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    single = Database(settings.sqlalchemy_url, pool_size=1, max_overflow=0)
    try:
        async with single.for_user(a.user_id) as s:
            assert (await s.execute(text("select count(*) from conversations"))).scalar_one() == 1
        async with single.system() as s:
            leaked = (await s.execute(text("select count(*) from conversations"))).scalar_one()
    finally:
        await single.dispose()
    assert leaked == 0


def test_app_role_cannot_read_a_messages_partition_directly(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("select count(*) from messages_default")


def test_app_role_cannot_write_reference_data(app_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("insert into drug_synonyms (alias, canonical) values ('x', 'y')")


def test_default_partitions_start_empty(app_conn: psycopg.Connection) -> None:
    assert app_conn.execute("select default_partitions_empty()").fetchone() == (True,)
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/security/test_rls.py -q`
Expected: FAIL (errors: `relation "conversations" does not exist`).

- [ ] **Step 3: Implement migration 0002**

File: `backend/migrations/versions/0002_user_data_rls.py`
```python
"""User data tables with row-level security, and public reference tables (spec 7).

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  title text,
  triage_level text CHECK (triage_level IN ('RED', 'YELLOW', 'GREEN')),
  started_at timestamptz NOT NULL DEFAULT now(),
  last_message_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  -- Target of composite FKs: a child row must belong to its parent's user.
  UNIQUE (id, user_id)
);
CREATE INDEX conversations_user_recent_idx
  ON conversations (user_id, last_message_at DESC) WHERE deleted_at IS NULL;

CREATE TABLE messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  conversation_id uuid NOT NULL,
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,
  intent text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  superseded_at timestamptz,
  PRIMARY KEY (id, created_at),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
) PARTITION BY RANGE (created_at);
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);
CREATE TABLE messages_default PARTITION OF messages DEFAULT;
REVOKE ALL ON messages_default FROM etheria_app;
SELECT ensure_monthly_partitions('messages', 3);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  filename text NOT NULL,
  mime_type text NOT NULL CHECK (mime_type IN ('application/pdf', 'image/png', 'image/jpeg')),
  storage_key text NOT NULL UNIQUE,
  sha256 text NOT NULL,
  size_bytes integer NOT NULL CHECK (size_bytes > 0),
  page_count integer,
  doc_type text CHECK (doc_type IN ('lab_report', 'prescription', 'discharge_summary', 'imaging_report', 'other')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed')),
  report_date date,
  lab_name text,
  summary text,
  extracted jsonb,
  extraction_stats jsonb,
  error_code text,
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  UNIQUE (id, user_id),
  UNIQUE (user_id, sha256)
);

CREATE TABLE document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL,
  user_id uuid NOT NULL,
  chunk_index integer NOT NULL,
  page integer,
  source_kind text NOT NULL CHECK (source_kind IN ('text_layer', 'ocr')),
  content text NOT NULL,
  embedding vector(1024) NOT NULL,
  -- 'simple' keeps tokens such as HbA1c intact (spec 5.7).
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  UNIQUE (document_id, chunk_index),
  FOREIGN KEY (document_id, user_id) REFERENCES documents (id, user_id) ON DELETE CASCADE
);
CREATE INDEX document_chunks_embedding_idx ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX document_chunks_tsv_idx ON document_chunks USING gin (tsv);
CREATE INDEX document_chunks_user_idx ON document_chunks (user_id);

CREATE TABLE lab_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  document_id uuid NOT NULL,
  test_name text NOT NULL,
  value_text text NOT NULL,
  value_numeric numeric,
  unit text,
  ref_range_text text,
  ref_low numeric,
  ref_high numeric,
  flag text NOT NULL CHECK (flag IN ('low', 'normal', 'high', 'unknown')),
  report_date date,
  page integer,
  FOREIGN KEY (document_id, user_id) REFERENCES documents (id, user_id) ON DELETE CASCADE
);
CREATE INDEX lab_results_user_test_idx ON lab_results (user_id, lower(test_name));

CREATE TABLE medications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  document_id uuid,
  name_raw text NOT NULL,
  ingredients text[] NOT NULL DEFAULT '{}',
  dose text,
  frequency text,
  duration text,
  source text NOT NULL CHECK (source IN ('prescription', 'discharge_summary')),
  report_date date,
  FOREIGN KEY (document_id, user_id) REFERENCES documents (id, user_id) ON DELETE CASCADE
);
CREATE INDEX medications_user_idx ON medications (user_id);

-- Public reference data (spec 6.2): no RLS, read-only to the app.
CREATE TABLE medicine_brands (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name text NOT NULL,
  manufacturer text,
  type text,
  pack_size_label text,
  composition1 text,
  composition2 text,
  ingredients text[] NOT NULL DEFAULT '{}',
  is_discontinued boolean NOT NULL DEFAULT false
);
CREATE INDEX medicine_brands_name_trgm_idx ON medicine_brands USING gin (name gin_trgm_ops);
CREATE INDEX medicine_brands_name_lower_idx ON medicine_brands (lower(name));

CREATE TABLE drug_synonyms (
  alias citext PRIMARY KEY,
  canonical text NOT NULL
);
REVOKE INSERT, UPDATE, DELETE ON medicine_brands, drug_synonyms FROM etheria_app;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['conversations', 'messages', 'documents', 'document_chunks', 'lab_results', 'medications'] LOOP
    EXECUTE 'ALTER TABLE ' || quote_ident(t) || ' ENABLE ROW LEVEL SECURITY';
    EXECUTE 'CREATE POLICY ' || quote_ident(t || '_owner') || ' ON ' || quote_ident(t)
         || ' USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user())';
  END LOOP;
END
$$;

-- Readiness check (spec 7): a row in a default partition means a monthly partition is missing.
CREATE FUNCTION default_partitions_empty() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT NOT EXISTS (SELECT 1 FROM messages_default) AND NOT EXISTS (SELECT 1 FROM audit_log_default) $$;
REVOKE ALL ON FUNCTION default_partitions_empty() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION default_partitions_empty() TO etheria_app;
"""

DOWNGRADE = """
DROP FUNCTION IF EXISTS default_partitions_empty();
DROP TABLE IF EXISTS medications, lab_results, document_chunks, documents, messages,
  conversations, drug_synonyms, medicine_brands CASCADE;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/security/test_rls.py tests/integration/test_migrations.py -q`
Expected: all pass (`test_rls.py`: 19 tests; migrations still 8).

- [ ] **Step 5: Migrate the dev database and commit**

Run: `cd backend && uv run etheria migrate`
Expected: `database migrated to head`.

```bash
git add backend/migrations backend/tests
git commit -m "feat(db): migration 0002 with user data tables, RLS and composite ownership FKs"
```

---

### Task 6: Password hashing and tokens

**Files:**
- Create: `backend/src/etheria/auth/passwords.py`, `auth/tokens.py`, `backend/tests/unit/test_passwords.py`, `backend/tests/unit/test_tokens.py`

**Interfaces:**
- Consumes: `utcnow()` (Task 2).
- Produces: `hash_password(pw) -> str`, `verify_password(stored_hash, pw) -> bool` (never raises), `needs_rehash(stored_hash) -> bool`, `dummy_hash() -> str` (cached).
- Produces: `create_access_token(user_id: UUID, secret: str, ttl_seconds: int) -> str`, `decode_access_token(token, secret) -> AccessClaims(user_id: UUID, jti: str, expires_at: datetime)`, `InvalidToken`, `new_refresh_token() -> str`, `hash_refresh_token(raw) -> str` (SHA-256 hex).

- [ ] **Step 1: Write the failing tests**

File: `backend/tests/unit/test_passwords.py`
```python
from etheria.auth.passwords import dummy_hash, hash_password, needs_rehash, verify_password

PW = "correct horse battery"


def test_hash_is_argon2id_and_salted() -> None:
    first, second = hash_password(PW), hash_password(PW)
    assert first.startswith("$argon2id$")
    assert first != second


def test_verify_accepts_the_right_password_only() -> None:
    stored = hash_password(PW)
    assert verify_password(stored, PW) is True
    assert verify_password(stored, PW + "!") is False


def test_verify_never_raises_on_a_malformed_hash() -> None:
    assert verify_password("not-a-hash", PW) is False


def test_fresh_hashes_do_not_need_rehash() -> None:
    assert needs_rehash(hash_password(PW)) is False


def test_dummy_hash_is_a_cached_argon2id_hash() -> None:
    assert dummy_hash() is dummy_hash()
    assert dummy_hash().startswith("$argon2id$")
```

File: `backend/tests/unit/test_tokens.py`
```python
from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest

from etheria.auth.tokens import (
    InvalidToken,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
    new_refresh_token,
)

SECRET = "k" * 40


def test_access_token_round_trips() -> None:
    uid = uuid4()
    claims = decode_access_token(create_access_token(uid, SECRET, 900), SECRET)
    assert claims.user_id == uid
    assert len(claims.jti) == 32
    assert claims.expires_at > datetime.now(UTC)


def test_expired_token_is_rejected() -> None:
    with pytest.raises(InvalidToken):
        decode_access_token(create_access_token(uuid4(), SECRET, -10), SECRET)


def test_token_signed_with_another_secret_is_rejected() -> None:
    with pytest.raises(InvalidToken):
        decode_access_token(create_access_token(uuid4(), "z" * 40, 900), SECRET)


def test_unsigned_token_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": str(uuid4()), "iat": 0, "exp": 9_999_999_999, "jti": "x"}, None, algorithm="none"
    )
    with pytest.raises(InvalidToken):
        decode_access_token(forged, SECRET)


def test_token_without_jti_is_rejected() -> None:
    now = int(datetime.now(UTC).timestamp())
    token = jwt.encode({"sub": str(uuid4()), "iat": now, "exp": now + 60}, SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_access_token(token, SECRET)


def test_token_with_a_non_uuid_subject_is_rejected() -> None:
    now = int(datetime.now(UTC).timestamp())
    token = jwt.encode({"sub": "admin", "iat": now, "exp": now + 60, "jti": "j"}, SECRET, algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_access_token(token, SECRET)


def test_refresh_tokens_are_random_and_stored_hashed() -> None:
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b
    assert len(a) >= 43  # 32 random bytes, base64url
    assert hash_refresh_token(a) == hash_refresh_token(a)
    assert len(hash_refresh_token(a)) == 64
    assert hash_refresh_token(a) != a
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/unit/test_passwords.py tests/unit/test_tokens.py -q`
Expected: FAIL (`No module named 'etheria.auth.passwords'`).

- [ ] **Step 3: Implement**

File: `backend/src/etheria/auth/passwords.py`
```python
"""argon2id password hashing (spec 9) with argon2-cffi's default parameters."""

from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


@cache
def dummy_hash() -> str:
    """Verified against when the email is unknown, so login timing does not reveal accounts."""
    return _hasher.hash("timing-equaliser-not-a-real-password")
```

File: `backend/src/etheria/auth/tokens.py`
```python
"""Access tokens (HS256 JWT, 15 minutes) and opaque refresh tokens (spec 9)."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt

from etheria.core.clock import utcnow


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    jti: str
    expires_at: datetime


def create_access_token(user_id: UUID, secret: str, ttl_seconds: int) -> str:
    now = int(utcnow().timestamp())
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl_seconds, "jti": uuid4().hex}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token, secret, algorithms=["HS256"], options={"require": ["exp", "iat", "sub", "jti"]}
        )
        return AccessClaims(
            user_id=UUID(payload["sub"]),
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError) as e:
        raise InvalidToken(str(e)) from e


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/unit/test_passwords.py tests/unit/test_tokens.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/etheria/auth backend/tests/unit
git commit -m "feat(auth): argon2id passwords, JWT access tokens, hashed refresh tokens"
```

---

### Task 7: Auth service: register, login, refresh rotation with reuse detection, logout

**Files:**
- Create: `backend/src/etheria/db/models.py`, `db/repositories/users.py`, `db/repositories/refresh_tokens.py`, `db/repositories/audit.py`, `backend/src/etheria/auth/schemas.py`, `auth/service.py`, `backend/tests/integration/test_auth_service.py`

**Interfaces:**
- Consumes: `Database` (Task 3), passwords and tokens (Task 6), errors, `utcnow`, `Settings` (Task 2).
- Produces: ORM `User`, `RefreshToken`, `AuditLog`; repositories `users.get_by_email/get/create`, `refresh_tokens.create/get_for_update/revoke_family`, `audit.record(session, action, *, user_ref=None, ip=None, user_agent=None, resource_type=None, resource_id=None, details=None)`.
- Produces: `UserOut(id, email, display_name)`, `TokenOut(access_token, token_type="bearer", expires_in, user)`, `RegisterIn`, `LoginIn` (email normalised: stripped, lower-cased).
- Produces: `ClientMeta(ip, user_agent)`, `IssuedTokens(user, access_token, expires_in, refresh_token)`, `AuthService(db, settings)` with `register`, `login`, `refresh`, `logout`, `get_user`. Error codes: `email_taken` (409), `invalid_credentials`, `invalid_refresh`, `refresh_reused`, `token_invalid` (401).

- [ ] **Step 1: Write the failing tests**

File: `backend/tests/integration/test_auth_service.py`
```python
import asyncio
from uuid import uuid4

import psycopg
import pytest

from etheria.auth.service import AuthService, ClientMeta, IssuedTokens
from etheria.core.errors import Conflict, NotAuthenticated
from etheria.core.settings import Settings
from etheria.db.session import Database

META = ClientMeta(ip="127.0.0.1", user_agent="pytest")
PW = "correct horse battery"


def new_email() -> str:
    return f"u{uuid4().hex[:12]}@example.com"


@pytest.fixture
def svc(db: Database, settings: Settings) -> AuthService:
    return AuthService(db, settings)


def _audit_count(conn: psycopg.Connection, action: str, user_ref: str) -> int:
    row = conn.execute(
        "select count(*) from audit_log where action = %s and user_ref = %s", (action, user_ref)
    ).fetchone()
    assert row is not None
    return row[0]


async def test_register_then_login(svc: AuthService) -> None:
    email = new_email()
    issued = await svc.register(email, PW, "Asha", META)
    assert issued.user.email == email
    assert issued.expires_in == 900
    again = await svc.login(email, PW, META)
    assert again.user.id == issued.user.id


async def test_email_is_normalised(svc: AuthService) -> None:
    local = uuid4().hex[:10]
    issued = await svc.register(f"  {local}@Example.COM ", PW, None, META)
    assert issued.user.email == f"{local}@example.com"
    assert (await svc.login(f"{local.upper()}@EXAMPLE.com", PW, META)).user.id == issued.user.id


async def test_duplicate_email_is_a_conflict(svc: AuthService) -> None:
    email = new_email()
    await svc.register(email, PW, None, META)
    with pytest.raises(Conflict) as err:
        await svc.register(email.upper(), "another password!", None, META)
    assert err.value.code == "email_taken"


async def test_wrong_password_and_unknown_email_look_identical(svc: AuthService) -> None:
    email = new_email()
    await svc.register(email, PW, None, META)
    with pytest.raises(NotAuthenticated) as wrong:
        await svc.login(email, "wrong password!!", META)
    with pytest.raises(NotAuthenticated) as unknown:
        await svc.login(new_email(), "wrong password!!", META)
    assert (wrong.value.code, wrong.value.message) == (unknown.value.code, unknown.value.message)
    assert wrong.value.code == "invalid_credentials"


async def test_refresh_rotates_the_token(svc: AuthService) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    rotated = await svc.refresh(issued.refresh_token, META)
    assert rotated.refresh_token != issued.refresh_token
    assert rotated.user.id == issued.user.id


async def test_reusing_a_rotated_token_revokes_the_family(
    svc: AuthService, owner_conn: psycopg.Connection
) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    rotated = await svc.refresh(issued.refresh_token, META)
    with pytest.raises(NotAuthenticated) as err:
        await svc.refresh(issued.refresh_token, META)
    assert err.value.code == "refresh_reused"
    with pytest.raises(NotAuthenticated):
        await svc.refresh(rotated.refresh_token, META)  # the whole family is dead
    assert _audit_count(owner_conn, "refresh_token_reuse", str(issued.user.id)) == 1


async def test_concurrent_refresh_never_issues_two_successors(svc: AuthService) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    results = await asyncio.gather(
        svc.refresh(issued.refresh_token, META),
        svc.refresh(issued.refresh_token, META),
        return_exceptions=True,
    )
    successes = [r for r in results if isinstance(r, IssuedTokens)]
    failures = [r for r in results if isinstance(r, NotAuthenticated)]
    assert len(successes) == 1
    assert len(failures) == 1 and failures[0].code == "refresh_reused"


async def test_expired_refresh_token_is_rejected(svc: AuthService, owner_conn: psycopg.Connection) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    owner_conn.execute(
        "update refresh_tokens set expires_at = now() - interval '1 second' where user_id = %s",
        (issued.user.id,),
    )
    with pytest.raises(NotAuthenticated) as err:
        await svc.refresh(issued.refresh_token, META)
    assert err.value.code == "invalid_refresh"


async def test_logout_revokes_without_flagging_reuse(
    svc: AuthService, owner_conn: psycopg.Connection
) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    await svc.logout(issued.refresh_token, META)
    with pytest.raises(NotAuthenticated) as err:
        await svc.refresh(issued.refresh_token, META)
    assert err.value.code == "invalid_refresh"
    assert _audit_count(owner_conn, "refresh_token_reuse", str(issued.user.id)) == 0


async def test_auth_events_are_audited(svc: AuthService, owner_conn: psycopg.Connection) -> None:
    email = new_email()
    issued = await svc.register(email, PW, None, META)
    await svc.login(email, PW, META)
    with pytest.raises(NotAuthenticated):
        await svc.login(email, "wrong password!!", META)
    uid = str(issued.user.id)
    assert _audit_count(owner_conn, "register", uid) == 1
    assert _audit_count(owner_conn, "login", uid) == 1
    assert _audit_count(owner_conn, "login_failed", uid) == 1


async def test_get_user_for_a_deleted_account_is_not_authenticated(
    svc: AuthService, owner_conn: psycopg.Connection
) -> None:
    issued = await svc.register(new_email(), PW, None, META)
    owner_conn.execute("delete from users where id = %s", (issued.user.id,))
    with pytest.raises(NotAuthenticated):
        await svc.get_user(issued.user.id)
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/integration/test_auth_service.py -q`
Expected: FAIL (`No module named 'etheria.auth.service'`).

- [ ] **Step 3: Implement models, repositories, schemas, service**

File: `backend/src/etheria/db/models.py`
```python
"""ORM mappings. The schema itself lives in hand-written migrations; later
milestones add models here as they start using their tables."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), dict[str, Any]: JSONB}


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str]
    password_hash: Mapped[str]
    display_name: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str]
    family_id: Mapped[uuid.UUID]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    replaced_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_agent: Mapped[str | None]


class AuditLog(Base):
    """Partitioned by month in the database; insert-only from the app."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())
    user_ref: Mapped[str | None]
    action: Mapped[str]
    resource_type: Mapped[str | None]
    resource_id: Mapped[str | None]
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None]
    details: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))
```

File: `backend/src/etheria/db/repositories/users.py`
```python
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def get(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def create(
    session: AsyncSession, *, email: str, password_hash: str, display_name: str | None
) -> User:
    user = User(id=uuid4(), email=email, password_hash=password_hash, display_name=display_name)
    session.add(user)
    await session.flush()
    return user
```

File: `backend/src/etheria/db/repositories/refresh_tokens.py`
```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import RefreshToken


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_hash: str,
    family_id: UUID,
    expires_at: datetime,
    user_agent: str | None,
) -> RefreshToken:
    row = RefreshToken(
        id=uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id,
        expires_at=expires_at,
        user_agent=user_agent,
    )
    session.add(row)
    await session.flush()
    return row


async def get_for_update(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    """Row-locked, so two concurrent refreshes of one token are serialised."""
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def revoke_family(session: AsyncSession, family_id: UUID, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
```

File: `backend/src/etheria/db/repositories/audit.py`
```python
"""audit_log writes (spec 11.2): who did what, never health content."""

from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import AuditLog


async def record(
    session: AsyncSession,
    action: str,
    *,
    user_ref: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        insert(AuditLog).values(
            action=action,
            user_ref=user_ref,
            ip=ip,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    )
```

File: `backend/src/etheria/auth/schemas.py`
```python
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field


def _normalise_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


Email = Annotated[EmailStr, BeforeValidator(_normalise_email)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class RegisterIn(BaseModel):
    email: Email
    password: str = Field(min_length=10, max_length=256)
    display_name: str | None = Field(default=None, max_length=80)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)
```

File: `backend/src/etheria/auth/service.py`
```python
"""Authentication use cases (spec 9): argon2id passwords, 15-minute access
tokens, and rotating refresh tokens whose reuse revokes the whole family."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.auth.passwords import dummy_hash, hash_password, needs_rehash, verify_password
from etheria.auth.schemas import UserOut
from etheria.auth.tokens import create_access_token, hash_refresh_token, new_refresh_token
from etheria.core.clock import utcnow
from etheria.core.errors import AppError, Conflict, NotAuthenticated
from etheria.core.settings import Settings
from etheria.db.models import RefreshToken, User
from etheria.db.repositories import audit, refresh_tokens, users
from etheria.db.session import Database

INVALID_CREDENTIALS = "Invalid email or password"
SESSION_EXPIRED = "Your session has expired, please sign in again"
EMAIL_TAKEN = "An account with this email already exists"


@dataclass(frozen=True)
class ClientMeta:
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True)
class IssuedTokens:
    user: UserOut
    access_token: str
    expires_in: int
    refresh_token: str


def _normalise(email: str) -> str:
    return email.strip().lower()


def _password_ok(user: User | None, password: str) -> bool:
    # Unknown emails still pay for one hash check, so timing does not reveal accounts.
    return verify_password(user.password_hash if user else dummy_hash(), password)


class AuthService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    async def register(
        self, email: str, password: str, display_name: str | None, meta: ClientMeta
    ) -> IssuedTokens:
        email = _normalise(email)
        password_hash = await asyncio.to_thread(hash_password, password)  # CPU-bound
        try:
            async with self._db.system() as s:
                if await users.get_by_email(s, email) is not None:
                    raise Conflict(EMAIL_TAKEN, code="email_taken")
                user = await users.create(
                    s, email=email, password_hash=password_hash, display_name=display_name
                )
                issued = await self._issue(s, user, family_id=uuid4(), meta=meta)
                await audit.record(
                    s, "register", user_ref=str(user.id), ip=meta.ip, user_agent=meta.user_agent
                )
        except IntegrityError as e:  # a concurrent registration won the unique index
            raise Conflict(EMAIL_TAKEN, code="email_taken") from e
        return issued

    async def login(self, email: str, password: str, meta: ClientMeta) -> IssuedTokens:
        email = _normalise(email)
        issued: IssuedTokens | None = None
        async with self._db.system() as s:
            user = await users.get_by_email(s, email)
            if user is None or not await asyncio.to_thread(_password_ok, user, password):
                await audit.record(
                    s,
                    "login_failed",
                    user_ref=str(user.id) if user else None,
                    ip=meta.ip,
                    user_agent=meta.user_agent,
                )
            else:
                if needs_rehash(user.password_hash):
                    user.password_hash = await asyncio.to_thread(hash_password, password)
                issued = await self._issue(s, user, family_id=uuid4(), meta=meta)
                await audit.record(
                    s, "login", user_ref=str(user.id), ip=meta.ip, user_agent=meta.user_agent
                )
        if issued is None:
            raise NotAuthenticated(INVALID_CREDENTIALS, code="invalid_credentials")
        return issued

    async def refresh(self, raw_token: str, meta: ClientMeta) -> IssuedTokens:
        now = utcnow()
        failure: AppError | None = None
        issued: IssuedTokens | None = None
        async with self._db.system() as s:
            row = await refresh_tokens.get_for_update(s, hash_refresh_token(raw_token))
            if row is None:
                failure = NotAuthenticated(SESSION_EXPIRED, code="invalid_refresh")
            elif row.replaced_by is not None:
                # A token we already rotated came back: someone holds a copy. Kill the family.
                await refresh_tokens.revoke_family(s, row.family_id, now)
                await audit.record(
                    s,
                    "refresh_token_reuse",
                    user_ref=str(row.user_id),
                    ip=meta.ip,
                    user_agent=meta.user_agent,
                    details={"family_id": str(row.family_id)},
                )
                failure = NotAuthenticated(SESSION_EXPIRED, code="refresh_reused")
            elif row.revoked_at is not None or row.expires_at <= now:
                failure = NotAuthenticated(SESSION_EXPIRED, code="invalid_refresh")
            else:
                user = await users.get(s, row.user_id)
                if user is None:
                    failure = NotAuthenticated(SESSION_EXPIRED, code="invalid_refresh")
                else:
                    issued = await self._issue(
                        s, user, family_id=row.family_id, meta=meta, replaces=row, now=now
                    )
        # Raised after the transaction commits, so revocation and audit rows persist.
        if failure is not None:
            raise failure
        assert issued is not None
        return issued

    async def logout(self, raw_token: str | None, meta: ClientMeta) -> None:
        if not raw_token:
            return
        async with self._db.system() as s:
            row = await refresh_tokens.get_for_update(s, hash_refresh_token(raw_token))
            if row is not None:
                await refresh_tokens.revoke_family(s, row.family_id, utcnow())
                await audit.record(
                    s, "logout", user_ref=str(row.user_id), ip=meta.ip, user_agent=meta.user_agent
                )

    async def get_user(self, user_id: UUID) -> UserOut:
        async with self._db.system() as s:
            user = await users.get(s, user_id)
        if user is None:
            raise NotAuthenticated(SESSION_EXPIRED, code="token_invalid")
        return UserOut.model_validate(user)

    async def _issue(
        self,
        s: AsyncSession,
        user: User,
        *,
        family_id: UUID,
        meta: ClientMeta,
        replaces: RefreshToken | None = None,
        now: datetime | None = None,
    ) -> IssuedTokens:
        now = now or utcnow()
        raw = new_refresh_token()
        row = await refresh_tokens.create(
            s,
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id,
            expires_at=now + timedelta(days=self._settings.refresh_token_ttl_days),
            user_agent=meta.user_agent,
        )
        if replaces is not None:
            replaces.revoked_at = now
            replaces.replaced_by = row.id
        ttl = self._settings.access_token_ttl_seconds
        access = create_access_token(user.id, self._settings.jwt_secret.get_secret_value(), ttl)
        return IssuedTokens(UserOut.model_validate(user), access, ttl, raw)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/integration/test_auth_service.py -q`
Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/etheria/db backend/src/etheria/auth backend/tests/integration
git commit -m "feat(auth): service with refresh rotation, reuse detection and audit log"
```

---

### Task 8: Auth HTTP layer: routes, cookie, CSRF, rate limits, CORS

**Files:**
- Create: `backend/src/etheria/cache/rate_limit.py`, `backend/src/etheria/auth/dependencies.py`, `backend/src/etheria/auth/router.py`, `backend/tests/integration/test_rate_limit.py`, `backend/tests/integration/test_auth_api.py`
- Modify: `backend/src/etheria/api/app.py` (include the auth router), `backend/tests/conftest.py` (append `clean_redis`, `api_client`)

**Interfaces:**
- Consumes: `AuthService`, `ClientMeta`, schemas (Task 7); tokens (Task 6); app state (Task 3).
- Produces: `RateLimiter(redis)` with `hit(key, limit, window_s) -> tuple[bool, int]` and `enforce(key, limit, window_s)` (raises `RateLimited`).
- Produces: dependencies `current_user_id` (401 `not_authenticated` / `token_invalid` with `WWW-Authenticate: Bearer`), `require_same_origin` (403 `csrf_failed`), `get_auth_service`, `get_rate_limiter`, `client_meta`. M4 routers use `current_user_id`.
- Produces routes: `POST /auth/register` (201), `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` (204), `GET /auth/me`. Cookie name `REFRESH_COOKIE = "etheria_refresh"`.

- [ ] **Step 1: Write the failing tests**

Append to: `backend/tests/conftest.py`
```python


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
```
(Add `from redis.asyncio import Redis` to the import block.)

File: `backend/tests/integration/test_rate_limit.py`
```python
from redis.asyncio import Redis

from etheria.cache.rate_limit import RateLimiter
from etheria.core.settings import Settings


async def test_fixed_window_allows_the_limit_then_blocks(settings: Settings, clean_redis: None) -> None:
    redis = Redis.from_url(settings.redis_url)
    limiter = RateLimiter(redis)
    outcomes = [await limiter.hit("t:a", limit=3, window_s=60) for _ in range(4)]
    await redis.aclose()
    assert [allowed for allowed, _ in outcomes] == [True, True, True, False]
    assert 1 <= outcomes[-1][1] <= 60


async def test_keys_are_independent(settings: Settings, clean_redis: None) -> None:
    redis = Redis.from_url(settings.redis_url)
    limiter = RateLimiter(redis)
    for _ in range(3):
        await limiter.hit("t:a", limit=3, window_s=60)
    allowed, _ = await limiter.hit("t:b", limit=3, window_s=60)
    await redis.aclose()
    assert allowed
```

File: `backend/tests/integration/test_auth_api.py`
```python
from uuid import uuid4

import httpx

from etheria.auth.tokens import create_access_token
from etheria.core.settings import Settings

ORIGIN = "http://localhost:3000"
CSRF = {"Origin": ORIGIN, "X-Requested-With": "fetch"}
PW = "correct horse battery"


def new_email() -> str:
    return f"u{uuid4().hex[:12]}@example.com"


async def register(client: httpx.AsyncClient, email: str | None = None, password: str = PW) -> httpx.Response:
    return await client.post("/auth/register", json={"email": email or new_email(), "password": password})


async def call_refresh(
    client: httpx.AsyncClient, token: str, headers: dict[str, str] = CSRF
) -> httpx.Response:
    client.cookies.clear()
    return await client.post("/auth/refresh", headers={**headers, "Cookie": f"etheria_refresh={token}"})


async def test_register_returns_a_token_and_sets_the_refresh_cookie(api_client: httpx.AsyncClient) -> None:
    email = new_email()
    r = await register(api_client, email)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900 and body["access_token"]
    assert body["user"]["email"] == email
    cookie = r.headers["set-cookie"].lower()
    for part in ("etheria_refresh=", "httponly", "path=/auth", "samesite=lax", "max-age=1209600"):
        assert part in cookie


async def test_email_is_normalised_and_case_insensitive(api_client: httpx.AsyncClient) -> None:
    local = uuid4().hex[:10]
    r = await register(api_client, f"  {local}@Example.COM ")
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == f"{local}@example.com"
    login = await api_client.post("/auth/login", json={"email": f"{local}@EXAMPLE.com", "password": PW})
    assert login.status_code == 200
    again = await register(api_client, f"{local.upper()}@example.com")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_taken"


async def test_short_password_is_rejected_without_echoing_it(api_client: httpx.AsyncClient) -> None:
    r = await register(api_client, password="tiny-pw-9")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert "tiny-pw-9" not in r.text


async def test_login_failures_are_uniform(api_client: httpx.AsyncClient) -> None:
    email = new_email()
    await register(api_client, email)
    wrong = await api_client.post("/auth/login", json={"email": email, "password": "wrong password!!"})
    unknown = await api_client.post("/auth/login", json={"email": new_email(), "password": "wrong password!!"})
    assert wrong.status_code == unknown.status_code == 401
    strip = lambda r: {k: v for k, v in r.json()["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(wrong) == strip(unknown)


async def test_me_requires_a_valid_access_token(api_client: httpx.AsyncClient, settings: Settings) -> None:
    r = await register(api_client)
    token, user_id = r.json()["access_token"], r.json()["user"]["id"]

    missing = await api_client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "not_authenticated"
    assert missing.headers["www-authenticate"] == "Bearer"

    garbage = await api_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert garbage.json()["error"]["code"] == "token_invalid"

    expired = create_access_token(uuid4(), settings.jwt_secret.get_secret_value(), -10)
    stale = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert stale.status_code == 401

    ok = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["id"] == user_id


async def test_refresh_rotates_and_detects_reuse(api_client: httpx.AsyncClient) -> None:
    first = (await register(api_client)).cookies["etheria_refresh"]
    rotated = await call_refresh(api_client, first)
    assert rotated.status_code == 200, rotated.text
    second = rotated.cookies["etheria_refresh"]
    assert second != first

    reused = await call_refresh(api_client, first)
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_reused"
    assert (await call_refresh(api_client, second)).status_code == 401


async def test_refresh_requires_same_origin_headers(api_client: httpx.AsyncClient) -> None:
    token = (await register(api_client)).cookies["etheria_refresh"]
    no_header = await call_refresh(api_client, token, headers={"Origin": ORIGIN})
    evil = await call_refresh(api_client, token, headers={"Origin": "https://evil.example", "X-Requested-With": "fetch"})
    assert no_header.status_code == evil.status_code == 403
    assert no_header.json()["error"]["code"] == "csrf_failed"
    assert (await call_refresh(api_client, token)).status_code == 200  # still valid after the blocked attempts


async def test_refresh_without_a_cookie_is_401(api_client: httpx.AsyncClient) -> None:
    api_client.cookies.clear()
    r = await api_client.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_refresh"


async def test_logout_revokes_and_clears_the_cookie(api_client: httpx.AsyncClient) -> None:
    token = (await register(api_client)).cookies["etheria_refresh"]
    api_client.cookies.clear()
    out = await api_client.post("/auth/logout", headers={**CSRF, "Cookie": f"etheria_refresh={token}"})
    assert out.status_code == 204
    assert "max-age=0" in out.headers["set-cookie"].lower()
    after = await call_refresh(api_client, token)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "invalid_refresh"


async def test_login_is_rate_limited(api_client: httpx.AsyncClient) -> None:
    email = new_email()
    body = {"email": email, "password": "wrong password!!"}
    codes = [(await api_client.post("/auth/login", json=body)).status_code for _ in range(5)]
    assert codes == [401] * 5
    blocked = await api_client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1


async def test_register_is_rate_limited_per_ip(api_client: httpx.AsyncClient) -> None:
    codes = [(await register(api_client)).status_code for _ in range(6)]
    assert codes == [201] * 5 + [429]


async def test_cors_allows_only_the_frontend_origin(api_client: httpx.AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = await api_client.options("/auth/login", headers={"Origin": ORIGIN, **preflight})
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    assert ok.headers["access-control-allow-credentials"] == "true"
    evil = await api_client.options("/auth/login", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in evil.headers
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/integration/test_rate_limit.py tests/integration/test_auth_api.py -q`
Expected: FAIL (`No module named 'etheria.cache.rate_limit'`; auth routes 404).

- [ ] **Step 3: Implement**

File: `backend/src/etheria/cache/rate_limit.py`
```python
"""Fixed-window rate limiting in Redis (spec 8.3: Redis holds cache entries and
rate-limit counters, nothing else)."""

from redis.asyncio import Redis

from etheria.core.errors import RateLimited


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_s: int) -> tuple[bool, int]:
        """Count one attempt. Returns (allowed, seconds until the window resets)."""
        counter = f"rl:{key}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(counter)
            pipe.expire(counter, window_s, nx=True)
            pipe.ttl(counter)
            count, _, ttl = await pipe.execute()
        return count <= limit, max(int(ttl), 1)

    async def enforce(self, key: str, limit: int, window_s: int) -> None:
        allowed, retry_after = await self.hit(key, limit, window_s)
        if not allowed:
            raise RateLimited(retry_after)
```

File: `backend/src/etheria/auth/dependencies.py`
```python
"""FastAPI dependencies for auth. They read clients from app.state, which the
api factory populates (settings, db, redis)."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from etheria.auth.service import AuthService, ClientMeta
from etheria.auth.tokens import InvalidToken, decode_access_token
from etheria.cache.rate_limit import RateLimiter
from etheria.core.errors import Forbidden, NotAuthenticated

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def get_auth_service(request: Request) -> AuthService:
    return AuthService(request.app.state.db, request.app.state.settings)


def get_rate_limiter(request: Request) -> RateLimiter:
    return RateLimiter(request.app.state.redis)


def client_meta(request: Request) -> ClientMeta:
    user_agent = (request.headers.get("user-agent") or "")[:512] or None
    return ClientMeta(ip=request.client.host if request.client else None, user_agent=user_agent)


async def current_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID:
    if credentials is None:
        raise NotAuthenticated("Sign in required", headers=_CHALLENGE)
    secret = request.app.state.settings.jwt_secret.get_secret_value()
    try:
        return decode_access_token(credentials.credentials, secret).user_id
    except InvalidToken:
        raise NotAuthenticated(
            "Your session has expired, please sign in again", code="token_invalid", headers=_CHALLENGE
        ) from None


def require_same_origin(request: Request) -> None:
    """CSRF guard for the cookie-authenticated endpoints (spec 9)."""
    origin = request.headers.get("origin")
    if request.headers.get("x-requested-with") is None or origin not in request.app.state.settings.cors_origins:
        raise Forbidden("Cross-site request blocked", code="csrf_failed")


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
ClientMetaDep = Annotated[ClientMeta, Depends(client_meta)]
CurrentUserId = Annotated[UUID, Depends(current_user_id)]
```

File: `backend/src/etheria/auth/router.py`
```python
"""/auth endpoints (spec 9, 10)."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response

from etheria.auth.dependencies import (
    AuthServiceDep,
    ClientMetaDep,
    CurrentUserId,
    RateLimiterDep,
    require_same_origin,
)
from etheria.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from etheria.auth.service import IssuedTokens
from etheria.core.errors import NotAuthenticated
from etheria.core.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "etheria_refresh"
LOGIN_LIMIT = (5, 60)  # per IP + email, per minute
REGISTER_LIMIT = (5, 60)  # per IP, per minute
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _token_out(issued: IssuedTokens, response: Response, settings: Settings) -> TokenOut:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86_400,
        path="/auth",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return TokenOut(access_token=issued.access_token, expires_in=issued.expires_in, user=issued.user)


@router.post("/register", status_code=201)
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    svc: AuthServiceDep,
    limiter: RateLimiterDep,
    meta: ClientMetaDep,
) -> TokenOut:
    await limiter.enforce(f"register:{meta.ip}", *REGISTER_LIMIT)
    issued = await svc.register(body.email, body.password, body.display_name, meta)
    return _token_out(issued, response, _settings(request))


@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    svc: AuthServiceDep,
    limiter: RateLimiterDep,
    meta: ClientMetaDep,
) -> TokenOut:
    await limiter.enforce(f"login:{meta.ip}:{body.email}", *LOGIN_LIMIT)
    issued = await svc.login(body.email, body.password, meta)
    return _token_out(issued, response, _settings(request))


@router.post("/refresh", dependencies=[Depends(require_same_origin)])
async def refresh(
    request: Request,
    response: Response,
    svc: AuthServiceDep,
    meta: ClientMetaDep,
    token: RefreshCookie = None,
) -> TokenOut:
    if not token:
        raise NotAuthenticated("Your session has expired, please sign in again", code="invalid_refresh")
    issued = await svc.refresh(token, meta)
    return _token_out(issued, response, _settings(request))


@router.post("/logout", status_code=204, dependencies=[Depends(require_same_origin)])
async def logout(request: Request, svc: AuthServiceDep, meta: ClientMetaDep, token: RefreshCookie = None) -> Response:
    await svc.logout(token, meta)
    response = Response(status_code=204)
    response.delete_cookie(
        REFRESH_COOKIE, path="/auth", httponly=True, samesite="lax", secure=_settings(request).cookie_secure
    )
    return response


@router.get("/me")
async def me(user_id: CurrentUserId, svc: AuthServiceDep) -> UserOut:
    return await svc.get_user(user_id)
```

Modify `backend/src/etheria/api/app.py`: add `from etheria.auth import router as auth_router` to the imports and `app.include_router(auth_router.router)` after `app.include_router(health.router)`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/integration/test_rate_limit.py tests/integration/test_auth_api.py -q`
Expected: all pass (2 + 12).

- [ ] **Step 5: Commit**

```bash
git add backend/src/etheria backend/tests
git commit -m "feat(auth): /auth routes with refresh cookie, CSRF guard, rate limits and CORS"
```

---

### Task 9: Readiness endpoint

**Files:**
- Modify: `backend/src/etheria/api/routers/health.py`
- Create: `backend/tests/integration/test_health.py`

**Interfaces:**
- Consumes: app state `db`, `redis`, `neo4j`, `temporal`, `settings` (Task 3); `default_partitions_empty()` (Task 5).
- Produces: `GET /health/ready` -> 200 `{"status": "ready", "checks": {"postgres","redis","neo4j","temporal": "ok"}}` or 503 `{"status": "not_ready", "checks": {...: "error: <Type>: <message>"}}`.

- [ ] **Step 1: Write the failing tests**

File: `backend/tests/integration/test_health.py`
```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && uv run pytest tests/integration/test_health.py -q`
Expected: FAIL (404 on `/health/ready`).

- [ ] **Step 3: Implement**

File: `backend/src/etheria/api/routers/health.py`
```python
"""Liveness and readiness (spec 10)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from temporalio.client import Client

from etheria.db.session import Database

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
        state.temporal = await Client.connect(state.settings.temporal_address)
    if not await state.temporal.service_client.check_health():
        raise RuntimeError("temporal reports unhealthy")
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd backend && uv run pytest tests/integration/test_health.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/etheria/api backend/tests/integration/test_health.py
git commit -m "feat(api): /health/ready checks postgres, redis, neo4j, temporal and default partitions"
```

---

### Task 10: Docs, spec updates and full verification

**Files:**
- Modify: `docs/superpowers/specs/2026-09-28-etheria-v2-design.md` (sections 7, 9, 11.1, 13), `CLAUDE.md` (current state, commands)

- [ ] **Step 1: Spec updates**

1. Section 7, after the RLS paragraph, add: `Child tables carry composite foreign keys to their parent's \`(id, user_id)\` (messages -> conversations; chunks, lab results and medications -> documents). Referential-integrity checks bypass RLS, so without these a user could attach a row to another user's conversation. The app role cannot read partitions directly (only through the parent's policy), cannot write \`medicine_brands\` / \`drug_synonyms\`, and cannot delete \`audit_log\` rows.`
2. Section 9, Endpoints bullet: append ` Registration is rate limited to 5 per minute per IP (argon2id makes each attempt expensive). Error codes: \`email_taken\`, \`invalid_credentials\`, \`invalid_refresh\`, \`refresh_reused\`, \`token_invalid\`, \`csrf_failed\`, \`rate_limited\`.`
3. Section 11.1, abuse row: replace `login 5/min per IP + email` with `login 5/min per IP + email, register 5/min per IP`.
4. Section 13, item 1: append ` Refresh is single-flight in the client: concurrent 401s share one \`/auth/refresh\` call, because a second refresh with the same cookie is treated as reuse and revokes the session.`

- [ ] **Step 2: CLAUDE.md**

Replace the "Current state" bullets with:
```markdown
- Spec approved 2026-09-28. Plans live in `docs/superpowers/plans/`.
- M0 done (`docs/spikes/m0-results.md`). M1 done: settings, logging, error shape, schema with RLS and partitions, auth, health/readiness, test harness, import contracts.
- Next: M2 (knowledge layer). Needs `BIOPORTAL_API_KEY` (and optionally `NCBI_API_KEY`) in `backend/.env`.
```
In "Planned commands", add after the `docker compose` line:
```bash
cd backend && uv run etheria migrate               # alembic upgrade head (owner role)
uv run pytest -m "not integration"                 # unit tests, no docker needed
uv run pytest                                      # everything (needs docker infra)
```

- [ ] **Step 3: Full verification**

Run:
```bash
cd backend && uv run ruff check . && uv run lint-imports && uv run pytest -q
```
Expected: ruff `All checks passed!`, import-linter `Contracts: 5 kept, 0 broken.`, pytest all passed.

Run: `docker system df -v | grep -E '^etheria_'` and confirm the etheria volumes are still under 600 MB.

- [ ] **Step 4: Commit**

```bash
git add docs CLAUDE.md
git commit -m "docs: M1 schema, auth and client refresh rules; commands"
```
