"""Conversation history (spec 10): list, detail, rename, delete. Shapes match
the frontend's api.ts (fetchHistory, fetchSessionDetail), with additive fields
(name, message_id, triage_level, citations, differential, incomplete). Another
user's conversation is not found, never forbidden."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, StringConstraints

from etheria.api.routers.chat import ServiceDep
from etheria.auth.dependencies import CurrentUserId
from etheria.core.errors import NotFound
from etheria.db.models import Conversation, Message
from etheria.db.repositories import chat

router = APIRouter(prefix="/history", tags=["history"])


class RenameRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def _session(c: Conversation) -> dict[str, Any]:
    return {
        "session_id": str(c.id),
        "triage_level": c.triage_level,
        "started_at": _iso(c.started_at),
        "ended_at": _iso(c.last_message_at),
        "name": c.title,
    }


def _message(m: Message) -> dict[str, Any]:
    meta = m.meta or {}
    return {
        "message_id": str(m.id),
        "role": m.role,
        "content": m.content,
        "intent": m.intent,
        "symptoms": meta.get("symptoms"),
        "triage_level": meta.get("triage_level"),
        "citations": meta.get("citations", []),
        "differential": meta.get("differential", []),
        "incomplete": bool(meta.get("incomplete", False)),
        "created_at": _iso(m.created_at),
    }


@router.get("/")
async def list_sessions(
    request: Request,
    user_id: CurrentUserId,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    async with request.app.state.db.for_user(user_id) as s:
        total, rows = await chat.list_conversations(s, user_id, page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "sessions": [
            _session(r.conversation) | {"message_count": r.message_count, "preview": r.preview}
            for r in rows
        ],
    }


@router.get("/{session_id}")
async def session_detail(request: Request, session_id: UUID, user_id: CurrentUserId) -> dict:
    async with request.app.state.db.for_user(user_id) as s:
        conv = await chat.get_conversation(s, user_id, session_id)
        if conv is None:
            raise NotFound("Conversation not found")
        messages = await chat.list_messages(s, user_id, session_id)
    return _session(conv) | {
        "message_count": len(messages),
        "messages": [_message(m) for m in messages],
    }


@router.patch("/{session_id}")
async def rename(
    request: Request, session_id: UUID, body: RenameRequest, user_id: CurrentUserId
) -> dict[str, str]:
    async with request.app.state.db.for_user(user_id) as s:
        if not await chat.rename(s, user_id, session_id, body.name):
            raise NotFound("Conversation not found")
    return {"session_id": str(session_id), "name": body.name}


@router.delete("/{session_id}", status_code=204)
async def delete(
    request: Request, session_id: UUID, user_id: CurrentUserId, service: ServiceDep
) -> Response:
    async with request.app.state.db.for_user(user_id) as s:
        if not await chat.soft_delete(s, user_id, session_id):
            raise NotFound("Conversation not found")
    await service.delete_thread(session_id)  # execution state goes with it (spec 4.8)
    return Response(status_code=204)
