"""generate (spec 4.3, 4.6 "While", plan Decision 1): stream the answer through
StreamGuard and emit the guarded text as custom `token` events, so what the
user sees is exactly what is stored.

For RED the emergency block is already out (input_guard or triage); this node
sends it only as a last safety net. One retry if the model fails before its
first token; after that the error propagates and the chat service stores the
partial answer as incomplete."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import (
    Timer,
    evidence_block,
    history,
    log,
    record_block,
    status,
    token,
)
from etheria.graph.schemas import TurnData
from etheria.graph.state import ChatState
from etheria.llm.prompts import load_prompt
from etheria.safety.stream_guard import StreamGuard
from etheria.safety.texts import emergency_block

_KNOWLEDGE = {"pubmed", "medlineplus", "condition", "interaction", "caution", "chunk"}


def context_block(turn: TurnData) -> str:
    triage = turn.triage
    lines = [
        f"Triage level: {triage.level if triage else 'YELLOW'}"
        + (f" ({'; '.join(triage.reasons)})" if triage and triage.reasons else ""),
    ]
    u = turn.understanding
    if u is not None:
        lines.append(f"Intent: {u.intent}")
        if u.pregnant:
            lines.append("The user says she is pregnant.")
    lines += ["", record_block(turn), "", evidence_block(turn.evidence)]
    if (
        not any(e.kind in _KNOWLEDGE for e in turn.evidence)
        and u
        and u.intent
        not in (
            "general_health",
            "follow_up",
        )
    ):
        lines.append("No verified source was found for this question: follow the no-evidence rule.")
    return "\n".join(lines)


def make_generate(deps: GraphDeps):
    async def generate(state: ChatState) -> dict:
        timer = Timer()
        turn = state["turn"]
        update: dict = {}
        if turn.triage and turn.triage.level == "RED" and not turn.emergency_sent:
            token(emergency_block(turn.triage.helpline))
            update |= {"emergency_sent": True, "helpline_sent": turn.triage.helpline}
        status("generate", "Writing the answer")
        prompt = [
            SystemMessage(load_prompt("generate")),
            SystemMessage(context_block(turn)),
            *history(state["messages"], state.get("summary", "")),
            HumanMessage(turn.user_message),
        ]
        model = deps.models.chat("generate")
        guard = StreamGuard()
        parts: list[str] = []
        for attempt in (1, 2):
            try:
                async for chunk in model.astream(prompt):
                    for segment in guard.feed(str(chunk.content)):
                        parts.append(segment)
                        token(segment)
                break
            except Exception as e:
                if parts or attempt == 2:
                    raise
                log.warning("generate_retry", error=type(e).__name__)
                guard = StreamGuard()
        for segment in guard.flush():
            parts.append(segment)
            token(segment)
        reply = "".join(parts).strip()
        update |= {
            "reply": reply,
            "guard_hits": guard.hits,
            "trace": [
                timer.entry("generate", "answer", f"{len(reply)} characters", guard=guard.hits)
            ],
        }
        return {"messages": [AIMessage(reply)], "turn": update}

    return generate
