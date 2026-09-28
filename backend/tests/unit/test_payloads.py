"""SSE / REST payloads match the v1 frontend's types.ts exactly (spec 4.7, 15).
The key sets below are copied from D:/Etheria/etheria/src/lib/types.ts."""

from etheria.graph import payloads
from etheria.graph.schemas import (
    ClinicalOutput,
    DifferentialItem,
    Evidence,
    SymptomMention,
    TraceEntry,
    TriageResult,
    TurnData,
    Understanding,
)

CITATION_KEYS = {"source", "identifier", "title", "url", "relevanceScore"}
SYMPTOM_KEYS = {"name", "cui", "icd10", "snomed", "duration", "severity", "type", "rxcui"}
DIFFERENTIAL_KEYS = {"condition", "likelihood", "rationale", "workup", "citations"}
TRACE_KEYS = {
    "intent",
    "symptoms_extracted",
    "routing_flags",
    "cache_hit",
    "sources",
    "context_chars",
    "triage_reasoning",
    "duration_ms",
    "agents",
}
AGENT_KEYS = {"name", "role", "output", "tools", "detail"}
METADATA_KEYS = {
    "type",
    "session_id",
    "triage_level",
    "symptoms",
    "follow_up_questions",
    "differential",
    "citations",
    "agent_trace",
    "message_id",
}
CITATION_SOURCES = {"pubmed", "rxnorm", "umls", "user_document", "neo4j", "medlineplus", "curated"}


def _evidence(n: int, source: str = "pubmed") -> Evidence:
    return Evidence(
        id=f"pubmed:{n}",
        source=source,
        kind="pubmed",
        identifier=str(n),
        title=f"t{n}",
        url=f"https://pubmed.ncbi.nlm.nih.gov/{n}/",
        text="x",
        relevance=0.5,
        tool="search_medical_literature",
        n=n,
    )


def _turn() -> TurnData:
    return TurnData(
        user_message="fever and body pain",
        understanding=Understanding(
            intent="symptom_check",
            symptoms=[
                SymptomMention(name="fever", duration="3 days"),
                SymptomMention(name="cough", negated=True),
            ],
            medications=["Dolo 650"],
        ),
        evidence=[_evidence(1), _evidence(2, "neo4j")],
        triage=TriageResult(level="YELLOW", reasons=["fever 3 days"], source="both"),
        reply="Dengue is one possibility [2].",
        clinical=ClinicalOutput(
            differential=[
                DifferentialItem(
                    condition="Dengue fever",
                    likelihood="possible",
                    rationale="Fever with body pain.",
                    workup=["NS1 antigen"],
                    citations=["[2]"],
                )
            ],
            follow_up_questions=["Any rash?", "Any bleeding?"],
        ),
        agent_tools=["explore_conditions"],
        trace=[TraceEntry(name="triage", role="safety", output="YELLOW", duration_ms=3.0)],
    )


def test_citation_keys_and_camel_case_score() -> None:
    c = payloads.citation(_evidence(1))
    assert set(c) == CITATION_KEYS
    assert c["relevanceScore"] == 0.5


def test_only_cited_evidence_is_returned() -> None:
    cited = payloads.cited_evidence(_turn().evidence, "Dengue is one possibility [2].")
    assert [e.n for e in cited] == [2]
    assert [e.n for e in payloads.cited_evidence(_turn().evidence, "see [1, 2] and [9]")] == [1, 2]


def test_symptoms_skip_negated_and_include_medicines() -> None:
    out = payloads.symptoms(_turn().understanding)
    assert out == [
        {"name": "fever", "duration": "3 days", "type": "symptom"},
        {"name": "Dolo 650", "type": "medication"},
    ]
    assert all(set(s) <= SYMPTOM_KEYS for s in out)


def test_differential_keys() -> None:
    (d,) = payloads.differential(_turn().clinical)
    assert set(d) == DIFFERENTIAL_KEYS


def test_agent_trace_keys() -> None:
    trace = payloads.agent_trace(_turn(), duration_ms=1234.5)
    assert set(trace) == TRACE_KEYS
    assert set(trace["agents"][0]) == AGENT_KEYS
    assert trace["routing_flags"]["explore_conditions"] is True
    assert trace["sources"] == {"pubmed": 1, "neo4j": 1}
    assert trace["triage_reasoning"] == "fever 3 days"


def test_metadata_event_keys() -> None:
    event = payloads.metadata_event(
        session_id="s", message_id="m", turn=_turn(), reply=_turn().reply, duration_ms=10
    )
    assert set(event) == METADATA_KEYS
    assert event["type"] == "metadata"
    assert event["triage_level"] == "YELLOW"
    assert [c["identifier"] for c in event["citations"]] == ["2"]
    assert event["follow_up_questions"] == ["Any rash?", "Any bleeding?"]


def test_evidence_sources_are_known_citation_sources() -> None:
    assert set(Evidence.model_fields["source"].annotation.__args__) <= CITATION_SOURCES
