"""FastAPI application factory (spec 3.1). The api package sits on top: it may
import anything, and nothing imports it (import-linter enforces this)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from etheria.api.chat_wiring import build_chat
from etheria.api.errors import install_error_handlers
from etheria.api.middleware import RequestContextMiddleware
from etheria.api.routers import chat, health, history, upload
from etheria.auth import router as auth_router
from etheria.core.crypto import encryption_key
from etheria.core.logging import configure_logging
from etheria.core.settings import Settings, get_settings
from etheria.db.session import Database
from etheria.ingestion.storage import FileStore
from etheria.knowledge.neo4j import create_driver


def create_app(
    settings: Settings | None = None, chat_overrides: dict[str, Any] | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Clients connect lazily: the app starts even when a dependency is down,
        # and /health/ready reports which one.
        app.state.db = Database(settings.sqlalchemy_url)
        app.state.redis = Redis.from_url(settings.redis_url)
        app.state.neo4j = create_driver(settings)
        app.state.temporal = None  # connected on first use (upload, readiness)
        app.state.file_store = FileStore(settings.upload_dir, encryption_key(settings))
        stack = await build_chat(
            settings, app.state.db, app.state.redis, app.state.neo4j, chat_overrides
        )
        app.state.chat = stack.service
        try:
            yield
        finally:
            await stack.close()
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
    app.include_router(auth_router.router)
    app.include_router(upload.router)
    app.include_router(chat.router)
    app.include_router(history.router)
    return app
