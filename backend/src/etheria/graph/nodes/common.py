"""Helpers shared by the chat nodes: stream events, timing, retries, and the
text blocks that describe the user's record and the evidence to a model.

LangGraph concept: *custom stream mode*. `get_stream_writer()` returns a
function that sends any JSON-able value to callers streaming with
`stream_mode="custom"`; the chat service forwards these as SSE events. Outside
a custom stream the writer is a no-op."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from etheria.graph.schemas import Evidence, TraceEntry, TurnData
from etheria.llm.prompts import datamark

log = structlog.get_logger("etheria.graph")


def emit(event: dict[str, Any]) -> None:
    get_stream_writer()(event)


def status(stage: str, message: str) -> None:
    emit({"type": "status", "stage": stage, "message": message})


def token(text: str) -> None:
    if text:
        emit({"type": "token", "content": text})


class Timer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    def entry(
        self, name: str, role: str, output: str, tools: list[str] | None = None, **detail: Any
    ) -> TraceEntry:
        return TraceEntry(
            name=name,
            role=role,
            output=output,
            tools=tools or [],
            detail=detail,
            duration_ms=(time.perf_counter() - self.started) * 1000,
        )


async def attempts[T](fn: Callable[[], Awaitable[T]], n: int, node: str) -> T:
    """Run `fn` up to n times; re-raise the last error. Retries live in the node
    (plan Decision 9) so that its fallback can be recorded in the trace."""
    for i in range(n):
        try:
            return await fn()
        except Exception as e:
            log.warning("node_attempt_failed", node=node, attempt=i + 1, error=type(e).__name__)
            if i == n - 1:
                raise
    raise AssertionError("unreachable")


def history(messages: list[BaseMessage], summary: str, last: int = 6) -> list[BaseMessage]:
    """The rolling summary plus the last few messages before the current one."""
    earlier = [m for m in messages[:-1] if isinstance(m, (HumanMessage, AIMessage))][-last:]
    out: list[BaseMessage] = []
    if summary:
        out.append(SystemMessage(f"Summary of the earlier conversation:\n{summary}"))
    return out + earlier


def lab_line(f: Any) -> str:
    rng = f" (range {f.ref_range_text})" if f.ref_range_text else ""
    unit = f" {f.unit}" if f.unit else ""
    when = f", {f.report_date}" if f.report_date else ""
    return f"{f.test_name}: {f.value_text}{unit}{rng}, flag {f.flag}; {f.filename}{when}"


def record_block(turn: TurnData) -> str:
    """The user's own record, as the models see it."""
    lines = ["The user's record (from their own uploaded reports):"]
    if turn.report_index:
        lines.append("Reports:")
        lines += [
            f"- {c.filename} ({c.doc_type or 'document'}"
            + (f", {c.report_date}" if c.report_date else "")
            + ")"
            + (f": {c.summary}" if c.summary else "")
            for c in turn.report_index[:10]
        ]
    else:
        lines.append("- No reports uploaded.")
    if turn.test_catalogue:
        lines.append("Test catalogue: " + ", ".join(turn.test_catalogue))
    if turn.lab_snapshot:
        lines.append("Abnormal lab values (latest):")
        lines += [f"- {lab_line(f)}" for f in turn.lab_snapshot]
    if turn.current_medications:
        lines.append(
            "Medicines on their reports: " + ", ".join(m.name_raw for m in turn.current_medications)
        )
    if turn.conditions:
        lines.append("Diagnoses on their discharge summaries: " + ", ".join(turn.conditions))
    return "\n".join(lines)


def render_evidence(e: Evidence) -> str:
    body = datamark(e.text) if e.kind == "chunk" else e.text
    return f"[{e.n}] ({e.title}) {body}"


def evidence_block(evidence: list[Evidence]) -> str:
    if not evidence:
        return "Evidence: none was found for this question."
    return "Evidence (cite by number):\n" + "\n".join(render_evidence(e) for e in evidence)
