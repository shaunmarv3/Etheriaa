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
