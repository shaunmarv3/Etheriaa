"""Data carried through one chat turn (spec 4.2). `TurnData` lives in the
`turn` state field: `load_context` fills it, the nodes add to it, `finalize`
empties it, so a persisted checkpoint holds only the message window and the
summary.

The models the LLM fills (`Understanding`, `TriageAssessment`,
`ClinicalOutput`) carry field descriptions: `with_structured_output` sends them
to the model as the function schema."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from etheria.db.repositories.health_record import LabFact, MedFact, ReportCard
from etheria.safety.input_guard import GuardResult

Intent = Literal[
    "symptom_check",
    "report_question",
    "medication_question",
    "general_health",
    "follow_up",
    "upload_help",
    "off_topic",
]
Level = Literal["GREEN", "YELLOW", "RED"]
CitationSource = Literal["user_document", "neo4j", "pubmed", "medlineplus", "curated"]
EvidenceKind = Literal[
    "lab",
    "medication",
    "chunk",
    "pubmed",
    "medlineplus",
    "condition",
    "interaction",
    "caution",
    "note",
]


# ---- filled by the LLM ----


class SymptomMention(BaseModel):
    name: str = Field(description="A short clean symptom phrase, e.g. 'headache'")
    duration: str | None = Field(default=None, description="e.g. '3 days', '2-3 years'")
    severity: str | None = Field(default=None, description="e.g. 'mild', 'severe'")
    negated: bool = Field(default=False, description="True if the user does NOT have it")


class Understanding(BaseModel):
    intent: Intent
    symptoms: list[SymptomMention] = []
    medications: list[str] = Field(default=[], description="Medicine or brand names as written")
    relevant_tests: list[str] = Field(default=[], description="Names from the test catalogue")
    red_flags: list[str] = []
    pregnant: bool = False
    search_query: str = Field(default="", description="The question as one standalone sentence")


class TriageAssessment(BaseModel):
    level: Level
    reasons: list[str] = Field(default=[], description="One to three short reasons")
    self_harm: bool = False


class DifferentialItem(BaseModel):
    condition: str
    likelihood: Literal["likely", "possible", "unlikely"]
    rationale: str
    workup: list[str] = []
    citations: list[str] = Field(default=[], description="Evidence numbers, e.g. '[2]'")


class ClinicalOutput(BaseModel):
    differential: list[DifferentialItem] = []
    follow_up_questions: list[str] = []


# ---- built by code ----


class TriageResult(BaseModel):
    level: Level
    reasons: list[str] = []
    rule_ids: list[str] = []
    source: Literal["rules", "model", "both", "fallback"]
    helpline: bool = False


class Evidence(BaseModel):
    """One retrieved fact. `id` is stable across tools (spec 4.5, plan Decision 8);
    `n` is its citation number, assigned by rerank_evidence."""

    id: str
    source: CitationSource
    kind: EvidenceKind
    identifier: str
    title: str
    url: str | None = None
    text: str  # what the generator reads
    relevance: float = 1.0
    structured: bool = False  # structured evidence is never dropped by the reranker
    tool: str
    n: int | None = None


class TraceEntry(BaseModel):
    name: str
    role: str
    output: str
    tools: list[str] = []
    detail: dict[str, Any] = {}
    duration_ms: float = 0.0


class TurnData(BaseModel):
    user_message: str = ""
    started_at: float = 0.0  # time.perf_counter() when the turn started
    report_index: list[ReportCard] = []
    test_catalogue: list[str] = []
    lab_snapshot: list[LabFact] = []
    current_medications: list[MedFact] = []
    conditions: list[str] = []
    guard: GuardResult | None = None
    understanding: Understanding | None = None
    evidence: list[Evidence] = []
    agent_tools: list[str] = []
    cache_hits: int = 0
    triage: TriageResult | None = None
    emergency_sent: bool = False
    helpline_sent: bool = False  # Tele-MANAS line streamed with the block
    reply: str = ""
    guard_hits: list[str] = []
    clinical: ClinicalOutput | None = None
    canned: str | None = None
    trace: list[TraceEntry] = []


# Classes a checkpoint may contain (LangGraph's msgpack allowlist).
CHECKPOINT_TYPES = [
    TurnData,
    SymptomMention,
    Understanding,
    TriageAssessment,
    DifferentialItem,
    ClinicalOutput,
    TriageResult,
    Evidence,
    TraceEntry,
    ReportCard,
    LabFact,
    MedFact,
    GuardResult,
]
