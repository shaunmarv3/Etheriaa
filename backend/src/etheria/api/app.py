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
