"""The chat state's `turn` reducer (plan Decision 3) and the routing functions."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from etheria.graph.schemas import TraceEntry, TriageResult, TurnData, Understanding
from etheria.graph.state import merge_turn, route_after_guard, route_after_understand
from etheria.safety.input_guard import GuardResult


def _trace(name: str) -> TraceEntry:
    return TraceEntry(name=name, role="r", output="o", duration_ms=1.0)


def test_partial_updates_merge_field_by_field() -> None:
    t = merge_turn(TurnData(user_message="hi"), {"reply": "a"})
    t = merge_turn(t, {"triage": TriageResult(level="YELLOW", source="model")})
    assert (t.user_message, t.reply, t.triage.level) == ("hi", "a", "YELLOW")


def test_parallel_trace_entries_are_appended_not_overwritten() -> None:
    t = merge_turn(TurnData(), {"trace": [_trace("triage")]})
    t = merge_turn(t, {"trace": [_trace("retrieval_agent")]})
    assert [e.name for e in t.trace] == ["triage", "retrieval_agent"]


def test_a_turndata_replaces_and_none_empties() -> None:
    t = merge_turn(TurnData(reply="old"), TurnData(user_message="new"))
    assert (t.user_message, t.reply) == ("new", "")
    assert merge_turn(t, None) == TurnData()


def test_unknown_field_is_an_error() -> None:
    with pytest.raises(ValueError):
        merge_turn(TurnData(), {"not_a_field": 1})


def _state(n_messages: int, guard: GuardResult, intent: str | None = None) -> dict:
    msgs = [HumanMessage("q") if i % 2 == 0 else AIMessage("a") for i in range(n_messages)]
    u = Understanding(intent=intent) if intent else None
    return {"messages": msgs, "summary": "", "turn": TurnData(guard=guard, understanding=u)}


def test_route_after_guard() -> None:
    assert route_after_guard(_state(1, GuardResult(blocked=True, reason="x"))) == "canned_reply"
    assert route_after_guard(_state(21, GuardResult())) == "summarize"
    assert route_after_guard(_state(20, GuardResult())) == "understand"


def test_route_after_understand_fans_out_or_cans() -> None:
    assert route_after_understand(_state(1, GuardResult(), "off_topic")) == "canned_reply"
    assert route_after_understand(_state(1, GuardResult(), "upload_help")) == "canned_reply"
    assert route_after_understand(_state(1, GuardResult(), "symptom_check")) == [
        "retrieval_agent",
        "triage",
    ]


def test_an_emergency_is_never_canned() -> None:
    red = GuardResult(rule_level="RED", rule_ids=["self_harm"])
    assert route_after_understand(_state(1, red, "off_topic")) == ["retrieval_agent", "triage"]
