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
