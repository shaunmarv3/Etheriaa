"""finalize (spec 4.3, 4.6 "After", 4.8): the join after generate ||
clinical_structuring, and after canned_reply.

A final deterministic pass over the whole reply (a pattern split across two
stream flushes is caught here and fixed in the stored copy), the RED header
check, the disclaimer, then the assistant message is stored in `messages`, the
non-blocking audit is started, the `metadata` event goes out and the per-turn
state is emptied so the checkpoint stays small."""

import time

from langgraph.runtime import Runtime

from etheria.db.repositories import chat
from etheria.graph import payloads
from etheria.graph.context import ChatContext
from etheria.graph.deps import AuditJob, GraphDeps
from etheria.graph.nodes.common import Timer, emit, render_evidence, token
from etheria.graph.state import ChatState
from etheria.safety.stream_guard import StreamGuard
from etheria.safety.texts import DISCLAIMER, emergency_block


def final_pass(reply: str) -> tuple[str, list[str]]:
    guard = StreamGuard(max_chars=10_000, max_wait_s=float("inf"))
    text = "".join(guard.feed(reply) + guard.flush())
    return text, guard.hits


def make_finalize(deps: GraphDeps):
    async def finalize(state: ChatState, runtime: Runtime[ChatContext]) -> dict:
        timer = Timer()
        ctx = runtime.context
        turn = state["turn"]
        body, late_hits = final_pass(turn.reply)
        red = turn.triage is not None and turn.triage.level == "RED"
        # The stored reply opens with the block exactly as it was streamed; the RED
        # header check adds it if a RED turn somehow reached here without it.
        header = emergency_block(turn.helpline_sent) if (turn.emergency_sent or red) else ""
        disclaimer = "\n\n_" + DISCLAIMER + "_"
        token(disclaimer)
        content = header + body + disclaimer
        duration_ms = (time.perf_counter() - turn.started_at) * 1000 if turn.started_at else 0.0
        entry = timer.entry("finalize", "persist", "stored", late_guard_hits=late_hits)
        final_turn = turn.model_copy(update={"trace": [*turn.trace, entry]})
        meta_event = payloads.metadata_event(
            session_id=str(ctx.conversation_id),
            message_id="",
            turn=final_turn,
            reply=body,
            duration_ms=duration_ms,
        )
        metadata = {
            k: meta_event[k]
            for k in (
                "triage_level",
                "symptoms",
                "follow_up_questions",
                "differential",
                "citations",
                "agent_trace",
            )
        }
        metadata |= {
            "guard_hits": turn.guard_hits,
            "late_guard_hits": late_hits,
            "regenerated": ctx.regenerate,
            "canned": turn.canned,
        }
        intent = turn.understanding.intent if turn.understanding else turn.canned
        async with deps.db.for_user(ctx.user_id) as s:
            message = await chat.insert_message(
                s,
                conversation_id=ctx.conversation_id,
                user_id=ctx.user_id,
                role="assistant",
                content=content,
                intent=intent,
                metadata=metadata,
            )
            await chat.touch(
                s, ctx.user_id, ctx.conversation_id, turn.triage.level if turn.triage else None
            )
        if deps.start_audit is not None and turn.canned is None:
            deps.start_audit(
                AuditJob(
                    user_id=ctx.user_id,
                    message_id=message.id,
                    created_at=message.created_at,
                    question=turn.user_message,
                    reply=content,
                    triage_level=metadata["triage_level"],
                    evidence=[render_evidence(e) for e in turn.evidence],
                )
            )
        emit(meta_event | {"message_id": str(message.id)})
        return {"turn": None}

    return finalize
