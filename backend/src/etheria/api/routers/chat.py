"""Chat endpoints (spec 4.7, 10): POST /chat/stream (SSE) and POST
/chat/regenerate. Event and response shapes match the frontend's api.ts."""

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, StringConstraints

from etheria.auth.dependencies import CurrentUserId, RateLimiterDep
from etheria.core.errors import AppError, ServiceUnavailable
from etheria.graph.service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

CHAT_PER_MINUTE = 20


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    session_id: UUID | None = None
    voice_b64: str | None = None


class RegenerateRequest(BaseModel):
    session_id: UUID


def chat_service(request: Request) -> ChatService:
    service = request.app.state.chat
    if service is None:
        raise ServiceUnavailable("Chat is not configured on this server", code="chat_unavailable")
    return service


ServiceDep = Annotated[ChatService, Depends(chat_service)]


async def _limit(request: Request, limiter: Any, user_id: UUID) -> None:
    limit = getattr(request.app.state, "chat_limit", CHAT_PER_MINUTE)
    await limiter.enforce(f"chat:{user_id}", limit, 60)


def _sse(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async def lines() -> AsyncIterator[str]:
        async for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return lines()


@router.post("/stream")
async def stream(
    body: ChatRequest,
    request: Request,
    user_id: CurrentUserId,
    limiter: RateLimiterDep,
    service: ServiceDep,
) -> StreamingResponse:
    await _limit(request, limiter, user_id)
    if body.voice_b64:
        raise AppError("Voice input is not available yet", code="voice_unavailable")
    turn = await service.open_turn(user_id, body.message, body.session_id, request.state.request_id)
    return StreamingResponse(
        _sse(service.events(turn)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/regenerate")
async def regenerate(
    body: RegenerateRequest,
    request: Request,
    user_id: CurrentUserId,
    limiter: RateLimiterDep,
    service: ServiceDep,
) -> dict[str, Any]:
    await _limit(request, limiter, user_id)
    return await service.regenerate(user_id, body.session_id, request.state.request_id)
