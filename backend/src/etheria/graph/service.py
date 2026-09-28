"""Runs chat turns (spec 4.7, 4.8): conversation ownership, the user message row,
the graph run as a stream of events, regenerate, and thread rebuild/delete.

The `messages` table is the system of record. The user's message is stored in
its own transaction before the graph runs, so a crash mid-turn never loses what
they typed; `finalize` stores the reply. A thread with no checkpoint (the first
turn, or one pruned) is rebuilt from `messages` before the turn runs.

LangGraph concepts: `astream(..., stream_mode="custom", durability="exit")`
(one checkpoint per turn); time travel with `aget_state_history` to fork from
the checkpoint that ended the previous turn (regenerate); `aupdate_state(...,
as_node="finalize")` to write a rebuilt window as if the graph had produced it."""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from etheria.core.errors import AppError, NotFound
from etheria.db.models import Message
from etheria.db.repositories import chat
from etheria.db.session import Database
from etheria.graph.audit import run_audit
from etheria.graph.context import ChatContext
from etheria.graph.deps import AuditJob, ModelFactory
from etheria.graph.schemas import TurnData
from etheria.graph.state import WINDOW
from etheria.safety.texts import DISCLAIMER

log = structlog.get_logger("etheria.chat")

TITLE_CHARS = 80
ERROR_DETAIL = "Something went wrong while answering. Please try again."
_DISCLAIMER_SUFFIX = "\n\n_" + DISCLAIMER + "_"


@dataclass(frozen=True)
class Turn:
    user_id: UUID
    conversation_id: UUID
    user_message: Message
    request_id: str


def _window_message(m: Message) -> BaseMessage:
    if m.role == "user":
        return HumanMessage(m.content, id=str(m.id))
    return AIMessage(m.content.removesuffix(_DISCLAIMER_SUFFIX), id=str(m.id))


class ChatService:
    def __init__(
        self,
        db: Database,
        graph: CompiledStateGraph,
        checkpointer: BaseCheckpointSaver,
        audit_models: ModelFactory | None = None,
    ) -> None:
        self.db = db
        self.graph = graph
        self.checkpointer = checkpointer
        self._audit_models = audit_models
        self._audits: set[asyncio.Task] = set()

    # ---- the audit runs after the reply, outside the request ----

    def start_audit(self, job: AuditJob) -> None:
        if self._audit_models is None:
            return
        task = asyncio.create_task(run_audit(self._audit_models, self.db, job))
        self._audits.add(task)
        task.add_done_callback(self._audits.discard)

    async def drain(self, timeout_s: float = 10.0) -> None:
        if self._audits:
            await asyncio.wait(self._audits, timeout=timeout_s)

    # ---- a turn ----

    async def open_turn(
        self, user_id: UUID, message: str, session_id: UUID | None, request_id: str
    ) -> Turn:
        """Checks ownership and stores the user's message. Raises NotFound for a
        conversation the user does not own, before any streaming starts."""
        async with self.db.for_user(user_id) as s:
            if session_id is None:
                conv = await chat.create_conversation(s, user_id, message[:TITLE_CHARS])
            else:
                conv = await chat.get_conversation(s, user_id, session_id)
                if conv is None:
                    raise NotFound("Conversation not found")
            stored = await chat.insert_message(
                s, conversation_id=conv.id, user_id=user_id, role="user", content=message
            )
            await chat.touch(s, user_id, conv.id, None)
        return Turn(user_id, conv.id, stored, request_id)

    def _config(self, conversation_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(conversation_id)}}

    async def _rebuild(self, user_id: UUID, conversation_id: UUID, upto: Message) -> None:
        """Write the window from `messages` (everything before `upto`) into a thread
        that has no checkpoint."""
        async with self.db.for_user(user_id) as s:
            earlier = [
                m
                for m in await chat.list_messages(s, user_id, conversation_id)
                if (m.created_at, str(m.id)) < (upto.created_at, str(upto.id))
            ]
        if earlier:
            await self.graph.aupdate_state(
                self._config(conversation_id),
                {
                    "messages": [_window_message(m) for m in earlier[-WINDOW:]],
                    "summary": "",
                    "turn": TurnData(),
                },
                as_node="finalize",
            )

    async def _ensure_thread(self, turn: Turn) -> None:
        state = await self.graph.aget_state(self._config(turn.conversation_id))
        if not state.values:
            await self._rebuild(turn.user_id, turn.conversation_id, turn.user_message)

    def _input(self, message: Message) -> dict[str, Any]:
        return {
            "messages": [HumanMessage(message.content, id=str(message.id))],
            "turn": TurnData(started_at=time.perf_counter()),
        }

    async def events(self, turn: Turn, regenerate: bool = False) -> AsyncIterator[dict]:
        """The turn as SSE-ready events; always ends with `done` or `error`."""
        streamed: list[str] = []
        finished = False
        try:
            await self._ensure_thread(turn)
            async for event in self._run(turn, self._config(turn.conversation_id), regenerate):
                if event.get("type") == "token":
                    streamed.append(event["content"])
                elif event.get("type") == "metadata":
                    finished = True
                yield event
        except Exception:
            log.exception("chat_turn_failed", conversation_id=str(turn.conversation_id))
            if streamed and not finished:
                await self._store_partial(turn, "".join(streamed))
            yield {"type": "error", "detail": ERROR_DETAIL}
            return
        yield {"type": "done"}

    async def _run(
        self, turn: Turn, config: dict[str, Any], regenerate: bool
    ) -> AsyncIterator[dict]:
        ctx = ChatContext(
            user_id=turn.user_id,
            conversation_id=turn.conversation_id,
            request_id=turn.request_id,
            regenerate=regenerate,
        )
        async for event in self.graph.astream(
            self._input(turn.user_message),
            config,
            context=ctx,
            stream_mode="custom",
            durability="exit",
        ):
            yield event

    async def _store_partial(self, turn: Turn, text: str) -> None:
        async with self.db.for_user(turn.user_id) as s:
            await chat.insert_message(
                s,
                conversation_id=turn.conversation_id,
                user_id=turn.user_id,
                role="assistant",
                content=text.strip(),
                metadata={"incomplete": True},
            )

    # ---- regenerate ----

    async def regenerate(self, user_id: UUID, session_id: UUID, request_id: str) -> dict:
        async with self.db.for_user(user_id) as s:
            if await chat.get_conversation(s, user_id, session_id) is None:
                raise NotFound("Conversation not found")
            last_user, last_assistant = await chat.last_turn(s, user_id, session_id)
        if last_user is None:
            raise AppError("There is no message to regenerate", code="nothing_to_regenerate")
        turn = Turn(user_id, session_id, last_user, request_id)
        config = self._config(session_id)
        fork = None
        async for snapshot in self.graph.aget_state_history(config):
            ids = {m.id for m in snapshot.values.get("messages", [])}
            if not snapshot.next and str(last_user.id) not in ids and snapshot.values:
                fork = snapshot.config  # the checkpoint that ended the previous turn
                break
        if fork is None:
            # First turn, or a pruned thread: rebuild everything before this message.
            await self.checkpointer.adelete_thread(str(session_id))
            await self._rebuild(user_id, session_id, last_user)
            state = await self.graph.aget_state(config)
            fork = state.config if state.values else config
        events = [e async for e in self._run(turn, fork, regenerate=True)]
        metadata = next((e for e in events if e.get("type") == "metadata"), None)
        if metadata is None:
            raise AppError("Could not regenerate the reply", code="regenerate_failed")
        if last_assistant is not None:
            async with self.db.for_user(user_id) as s:
                await chat.supersede(s, user_id, last_assistant)
        return {
            "session_id": str(session_id),
            "reply": "".join(e["content"] for e in events if e.get("type") == "token"),
            "triage_level": metadata["triage_level"],
            "symptoms": metadata["symptoms"],
            "follow_up_questions": metadata["follow_up_questions"],
            "differential": metadata["differential"],
            "citations": metadata["citations"],
            "message_id": metadata["message_id"],
        }

    async def delete_thread(self, conversation_id: UUID) -> None:
        await self.checkpointer.adelete_thread(str(conversation_id))
