"""SSE and REST payloads in the v1 frontend's shapes (spec 4.7): `Citation`
(camel-case `relevanceScore`: the stream hands citations to the UI without key
conversion), `Symptom`, `DifferentialDiagnosis` and `AgentTrace` (snake_case, as
typed in frontend/src/lib/types.ts). Contract tests pin the key sets."""

import re
from typing import Any

from etheria.graph.schemas import ClinicalOutput, Evidence, TurnData, Understanding

_REF = re.compile(r"\[(\d+(?:\s*[,-]\s*\d+)*)\]")


def citation(e: Evidence) -> dict[str, Any]:
    return {
        "source": e.source,
        "identifier": e.identifier,
        "title": e.title,
        "url": e.url,
        "relevanceScore": round(e.relevance, 3),
    }


def cited_numbers(text: str) -> set[int]:
    out: set[int] = set()
    for group in _REF.findall(text):
        for part in re.split(r"\s*,\s*", group):
            if "-" in part:
                lo, hi = (int(x) for x in part.split("-", 1))
                out.update(range(lo, hi + 1))
            else:
                out.add(int(part))
    return out


def cited_evidence(evidence: list[Evidence], reply: str) -> list[Evidence]:
    """Only evidence the reply actually cites becomes a citation."""
    used = cited_numbers(reply)
    return sorted((e for e in evidence if e.n in used), key=lambda e: e.n or 0)


def symptoms(u: Understanding | None) -> list[dict[str, Any]]:
    if u is None:
        return []
    out: list[dict[str, Any]] = []
    for s in u.symptoms:
        if s.negated:
            continue
        item: dict[str, Any] = {"name": s.name}
        if s.duration:
            item["duration"] = s.duration
        if s.severity:
            item["severity"] = s.severity
        item["type"] = "symptom"
        out.append(item)
    out += [{"name": m, "type": "medication"} for m in u.medications]
    return out


def differential(c: ClinicalOutput | None) -> list[dict[str, Any]]:
    if c is None:
        return []
    return [d.model_dump() for d in c.differential]


def agent_trace(turn: TurnData, duration_ms: float) -> dict[str, Any]:
    u = turn.understanding
    sources: dict[str, int] = {}
    for e in turn.evidence:
        sources[e.source] = sources.get(e.source, 0) + 1
    flags = {tool: True for tool in turn.agent_tools}
    flags["emergency"] = bool(turn.triage and turn.triage.level == "RED")
    flags["blocked"] = bool(turn.guard and turn.guard.blocked)
    return {
        "intent": u.intent if u else (turn.canned or "general_health"),
        "symptoms_extracted": symptoms(u),
        "routing_flags": flags,
        "cache_hit": turn.cache_hits > 0,
        "sources": sources,
        "context_chars": sum(len(e.text) for e in turn.evidence),
        "triage_reasoning": "; ".join(turn.triage.reasons) if turn.triage else None,
        "duration_ms": round(duration_ms, 1),
        "agents": [
            {
                "name": t.name,
                "role": t.role,
                "output": t.output,
                "tools": t.tools,
                "detail": {**t.detail, "duration_ms": round(t.duration_ms, 1)},
            }
            for t in turn.trace
        ],
    }


def metadata_event(
    *, session_id: str, message_id: str, turn: TurnData, reply: str, duration_ms: float
) -> dict[str, Any]:
    return {
        "type": "metadata",
        "session_id": session_id,
        "triage_level": turn.triage.level if turn.triage else "GREEN",
        "symptoms": symptoms(turn.understanding),
        "follow_up_questions": turn.clinical.follow_up_questions if turn.clinical else [],
        "differential": differential(turn.clinical),
        "citations": [citation(e) for e in cited_evidence(turn.evidence, reply)],
        "agent_trace": agent_trace(turn, duration_ms),
        "message_id": message_id,
    }
