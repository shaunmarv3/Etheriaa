"""Conversations and messages (spec 4.8, 7, 10). The `messages` table is the
system of record; LangGraph checkpoints are only execution state.

Every function expects a session from `Database.for_user(user_id)` and also
filters by user explicitly: RLS is the second line of defence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, func, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB, distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import Conversation, Message

PREVIEW_CHARS = 200
_LEVEL_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}


@dataclass
class ConversationSummary:
    conversation: Conversation
    message_count: int
    preview: str


async def create_conversation(s: AsyncSession, user_id: UUID, title: str | None) -> Conversation:
    conv = Conversation(id=uuid4(), user_id=user_id, title=title)
    s.add(conv)
    await s.flush()
    await s.refresh(conv)
    return conv


async def get_conversation(
    s: AsyncSession, user_id: UUID, conversation_id: UUID
) -> Conversation | None:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
        Conversation.deleted_at.is_(None),
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def list_conversations(
    s: AsyncSession, user_id: UUID, page: int, page_size: int
) -> tuple[int, list[ConversationSummary]]:
    live = (Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
    total = (await s.execute(select(func.count()).select_from(Conversation).where(*live))).scalar()
    convs = list(
        (
            await s.execute(
                select(Conversation)
                .where(*live)
                .order_by(Conversation.last_message_at.desc(), Conversation.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars()
    )
    if not convs:
        return total or 0, []
    visible = (Message.user_id == user_id, Message.superseded_at.is_(None))
    counts = dict(
        (
            await s.execute(
                select(Message.conversation_id, func.count())
                .where(*visible, Message.conversation_id.in_([c.id for c in convs]))
                .group_by(Message.conversation_id)
            )
        ).all()
    )
    first_user = (
        select(Message.conversation_id, Message.content)
        .where(
            *visible,
            Message.role == "user",
            Message.conversation_id.in_([c.id for c in convs]),
        )
        .ext(distinct_on(Message.conversation_id))
        .order_by(Message.conversation_id, Message.created_at)
    )
    previews = dict((await s.execute(first_user)).all())
    return total or 0, [
        ConversationSummary(c, counts.get(c.id, 0), (previews.get(c.id) or "")[:PREVIEW_CHARS])
        for c in convs
    ]


async def rename(s: AsyncSession, user_id: UUID, conversation_id: UUID, title: str) -> bool:
    conv = await get_conversation(s, user_id, conversation_id)
    if conv is None:
        return False
    conv.title = title
    return True


async def soft_delete(s: AsyncSession, user_id: UUID, conversation_id: UUID) -> bool:
    conv = await get_conversation(s, user_id, conversation_id)
    if conv is None:
        return False
    conv.deleted_at = func.now()
    return True


async def touch(
    s: AsyncSession, user_id: UUID, conversation_id: UUID, triage_level: str | None
) -> None:
    """Bump last_message_at; the conversation's triage level only rises."""
    values: dict[str, Any] = {"last_message_at": func.now()}
    if triage_level in _LEVEL_RANK:
        rank = case(
            {lv: r for lv, r in _LEVEL_RANK.items()}, value=Conversation.triage_level, else_=-1
        )
        values["triage_level"] = case(
            (rank < _LEVEL_RANK[triage_level], triage_level), else_=Conversation.triage_level
        )
    await s.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .values(**values)
    )


async def insert_message(
    s: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: UUID,
    role: str,
    content: str,
    intent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Message:
    msg = Message(
        id=uuid4(),
        # clock_timestamp, not the column default now(): two messages written in
        # one transaction must still sort in the order they were written.
        created_at=func.clock_timestamp(),
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content,
        intent=intent,
        meta=metadata or {},
    )
    s.add(msg)
    await s.flush()
    await s.refresh(msg)
    return msg


async def list_messages(
    s: AsyncSession, user_id: UUID, conversation_id: UUID, include_superseded: bool = False
) -> list[Message]:
    stmt = select(Message).where(
        Message.conversation_id == conversation_id, Message.user_id == user_id
    )
    if not include_superseded:
        stmt = stmt.where(Message.superseded_at.is_(None))
    return list((await s.execute(stmt.order_by(Message.created_at, Message.id))).scalars())


async def last_turn(
    s: AsyncSession, user_id: UUID, conversation_id: UUID
) -> tuple[Message | None, Message | None]:
    """The newest visible user message and the assistant reply after it, if any."""
    msgs = await list_messages(s, user_id, conversation_id)
    last_user = next((m for m in reversed(msgs) if m.role == "user"), None)
    if last_user is None:
        return None, None
    after = [m for m in msgs if m.created_at >= last_user.created_at and m.role == "assistant"]
    return last_user, (after[-1] if after else None)


async def supersede(s: AsyncSession, user_id: UUID, message: Message) -> None:
    await s.execute(
        update(Message)
        .where(
            Message.id == message.id,
            Message.created_at == message.created_at,
            Message.user_id == user_id,
        )
        .values(superseded_at=func.now())
    )


async def update_metadata(
    s: AsyncSession, user_id: UUID, message_id: UUID, created_at: datetime, patch: dict[str, Any]
) -> None:
    """Merge keys into a message's metadata (used by the post-hoc audit)."""
    await s.execute(
        update(Message)
        .where(
            Message.id == message_id,
            Message.created_at == created_at,
            Message.user_id == user_id,
        )
        .values(meta=Message.meta.op("||")(literal(patch, JSONB)))
    )
