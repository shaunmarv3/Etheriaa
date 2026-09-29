from uuid import UUID, uuid4

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import AuditLog, Conversation, Document, User


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


async def erase(session: AsyncSession, user_id: UUID, pseudonym: str) -> list[str]:
    """Erasure (spec 7): pseudonymise the user's audit rows, delete their checkpoint
    threads, then the user row, from which every user table cascades. Runs in the
    caller's `for_user` transaction; returns the storage keys of the files to remove
    once it commits."""
    keys = list((await session.execute(select(Document.storage_key))).scalars())
    threads = [str(t) for t in (await session.execute(select(Conversation.id))).scalars()]
    await session.execute(
        update(AuditLog).where(AuditLog.user_ref == str(user_id)).values(user_ref=pseudonym)
    )
    if threads:  # the three tables AsyncPostgresSaver.adelete_thread clears
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            await session.execute(
                text(f"delete from {table} where thread_id = any(:ids)"), {"ids": threads}
            )
    await session.execute(delete(User).where(User.id == user_id))
    return keys
