"""The chat graph's state (spec 4.2) and its routing functions (spec 4.4).

LangGraph concepts: a `TypedDict` state whose fields carry *reducers*.
`messages` uses `add_messages` (append, or remove with `RemoveMessage`);
`turn` uses `merge_turn`, because nodes that run in parallel in the same
superstep (retrieval_agent and triage, generate and clinical_structuring) both
write to it. Without a reducer LangGraph would raise InvalidUpdateError."""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from etheria.graph.schemas import TurnData

WINDOW = 20  # summarise when the window holds more messages than this
KEEP = 8  # messages kept verbatim after summarising
_APPEND = frozenset({"trace", "agent_tools", "guard_hits"})


def merge_turn(current: TurnData | None, update: TurnData | dict[str, Any] | None) -> TurnData:
    """`None` empties the turn (finalize); a `TurnData` replaces it (the start of a
    turn); a dict updates the named fields, appending to the list fields that
    parallel nodes share (trace, agent_tools, guard_hits)."""
    if update is None:
        return TurnData()
    if isinstance(update, TurnData):
        return update
    base = current or TurnData()
    unknown = set(update) - set(TurnData.model_fields)
    if unknown:
        raise ValueError(f"unknown turn fields: {sorted(unknown)}")
    patch = {k: getattr(base, k) + list(v) if k in _APPEND else v for k, v in update.items()}
    return base.model_copy(update=patch)


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str
    turn: Annotated[TurnData, merge_turn]


def route_after_guard(state: ChatState) -> Literal["canned_reply", "summarize", "understand"]:
    guard = state["turn"].guard
    if guard is not None and guard.blocked:
        return "canned_reply"
    if len(state["messages"]) > WINDOW:
        return "summarize"
    return "understand"


def route_after_understand(state: ChatState) -> str | list[str]:
    turn = state["turn"]
    emergency = turn.guard is not None and turn.guard.rule_level == "RED"
    intent = turn.understanding.intent if turn.understanding else "general_health"
    if intent in ("off_topic", "upload_help") and not emergency:
        return "canned_reply"
    # Fan out: both branches run in the same superstep and join at rerank_evidence.
    return ["retrieval_agent", "triage"]
