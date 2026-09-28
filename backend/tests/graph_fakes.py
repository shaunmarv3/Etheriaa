"""Test doubles for the chat graph: scripted models and fake services, so graph
tests run the real nodes, state, routing and database without network or LLM."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import psycopg
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import RunnableLambda

from etheria.graph.deps import GraphDeps
from etheria.graph.schemas import ClinicalOutput, TriageAssessment, Understanding
from etheria.knowledge.conditions import ConditionHit, Exploration
from etheria.knowledge.interactions import InteractionFinding, InteractionReport
from etheria.knowledge.resolver import Resolution
from etheria.medical_apis.medlineplus import HealthTopic
from etheria.medical_apis.pubmed import Article
from etheria.safety.cautions import load_cautions
from etheria.safety.triage_rules import RuleMatcher


class ScriptedChat(BaseChatModel):
    """Returns the scripted messages in order (the last one repeats). An
    Exception in the script is raised instead. `bind_tools` returns itself, so
    it can drive create_agent."""

    script: list[Any]
    calls: int = 0
    delay_s: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChat":
        return self

    def _next(self) -> AIMessage:
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kw):
        return ChatResult(generations=[ChatGeneration(message=self._next())])

    async def _agenerate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kw):
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        return ChatResult(generations=[ChatGeneration(message=self._next())])


class BrokenStream(BaseChatModel):
    """Streams `before` word by word, then raises."""

    before: str = ""
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "broken"

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        raise RuntimeError("model down")

    async def _astream(self, messages, stop=None, run_manager=None, **kw) -> AsyncIterator:
        self.calls += 1
        for word in self.before.split(" ") if self.before else []:
            yield ChatGenerationChunk(message=AIMessageChunk(content=word + " "))
        raise RuntimeError("model down")


def streaming(text: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(text)]))


def tool_call(name: str, args: dict[str, Any], call_id: str = "c1") -> AIMessage:
    return AIMessage("", tool_calls=[{"id": call_id, "name": name, "args": args}])


class FakeModels:
    """ModelFactory. `structured[node]` is a list consumed in order (the last item
    repeats; an Exception is raised). `chat[node]` is a model instance."""

    def __init__(
        self,
        structured: dict[str, list[Any]] | None = None,
        chat: dict[str, BaseChatModel] | None = None,
    ) -> None:
        self._structured = structured or {}
        self._chat = chat or {}
        self.calls: dict[str, int] = {}

    def structured(self, node: str, schema: type) -> RunnableLambda:
        items = self._structured.get(node) or [_default(node)]

        async def run(_: Any) -> Any:
            i = self.calls.get(node, 0)
            self.calls[node] = i + 1
            item = items[min(i, len(items) - 1)]
            if isinstance(item, Exception):
                raise item
            return item

        return RunnableLambda(run)

    def chat(self, node: str) -> BaseChatModel:
        if node in self._chat:
            return self._chat[node]
        if node == "retrieval_agent":
            return ScriptedChat(script=[AIMessage("DONE")])
        return streaming("OK.")


def _default(node: str) -> Any:
    return {
        "understand": Understanding(intent="general_health"),
        "triage": TriageAssessment(level="GREEN", reasons=["general question"]),
        "clinical_structuring": ClinicalOutput(follow_up_questions=["How long has it lasted?"]),
    }[node]


class FakeExplorer:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s
        self.calls: list[list[str]] = []

    async def explore(self, symptoms: list[str], k: int = 5) -> Exploration:
        self.calls.append(symptoms)
        await asyncio.sleep(self.delay_s)
        return Exploration(
            matched={s: s for s in symptoms},
            unmatched=[],
            conditions=[
                ConditionHit(
                    icd10="A90",
                    name="Dengue fever",
                    score=2.6,
                    coverage=0.39,
                    matched_symptoms=symptoms,
                    first_line_classes=["Paracetamol (acetaminophen)"],
                    self_care=["Rest", "Fluids"],
                    red_flags=["Bleeding gums"],
                )
            ],
        )


class FakeResolver:
    TABLE = {
        "brufen": Resolution(
            query="Brufen",
            status="ambiguous",
            candidates=["Brufen 400 Tablet", "Brufen MR Tablet"],
            shared_ingredients=["Ibuprofen"],
        ),
        "warfarin": Resolution(query="warfarin", status="resolved", ingredients=["Warfarin"]),
        "ibuprofen": Resolution(query="ibuprofen", status="resolved", ingredients=["Ibuprofen"]),
        "telma 40": Resolution(query="Telma 40", status="resolved", ingredients=["Telmisartan"]),
    }

    async def resolve(self, name: str) -> Resolution:
        return self.TABLE.get(name.lower(), Resolution(query=name, status="unresolved"))


class FakeInteractions:
    CLASSES = {"Ibuprofen": ["nsaid"], "Warfarin": ["vitamin_k_antagonist"], "Telmisartan": ["arb"]}

    def __init__(self) -> None:
        self.checked: list[list[str]] = []

    async def check(self, names: list[str]) -> InteractionReport:
        self.checked.append(names)
        lowered = {n.lower() for n in names}
        findings = []
        if {"brufen", "warfarin"} <= lowered or {"ibuprofen", "warfarin"} <= lowered:
            findings.append(
                InteractionFinding(
                    a="Ibuprofen", b="Warfarin", severity="Major", sources=["critical", "ddinter"]
                )
            )
        not_found = [("Ibuprofen", "Telmisartan")] if "telma 40" in lowered else []
        return InteractionReport(
            findings=findings, not_found=not_found, unresolved=[], duplicate_ingredients=[]
        )

    async def drug_classes(self, drugs: list[str]) -> dict[str, list[str]]:
        return {d: self.CLASSES.get(d, []) for d in drugs}


class FakePubMed:
    async def search_articles(self, query: str, k: int = 3) -> list[Article]:
        return [
            Article(pmid="123", title="A study", abstract="Findings.", year="2024", mesh_terms=[])
        ]


class FakeMedline:
    async def search(self, term: str, k: int = 3) -> list[HealthTopic]:
        return [
            HealthTopic(
                title="Tinnitus",
                url="https://medlineplus.gov/tinnitus.html",
                summary="Tinnitus is ringing in the ears.",
            )
        ]


class FakeEmbedder:
    async def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 1023


def make_deps(db: Any, models: FakeModels, **overrides: Any) -> GraphDeps:
    values: dict[str, Any] = {
        "db": db,
        "models": models,
        "matcher": RuleMatcher.load(),
        "cautions": load_cautions(),
        "explorer": FakeExplorer(),
        "interactions": FakeInteractions(),
        "resolver": FakeResolver(),
        "pubmed": FakePubMed(),
        "medlineplus": FakeMedline(),
        "query_embedder": FakeEmbedder(),
        "reranker": None,
    }
    values.update(overrides)
    return GraphDeps(**values)


def new_conversation(conn: psycopg.Connection, user: UUID) -> UUID:
    row = conn.execute(
        "insert into conversations (user_id, title) values (%s, 't') returning id", (user,)
    ).fetchone()
    assert row is not None
    return row[0]


def add_lab(
    conn: psycopg.Connection, user: UUID, test: str, value: str, flag: str, unit: str = ""
) -> UUID:
    doc = conn.execute(
        "insert into documents (user_id, filename, mime_type, storage_key, sha256, size_bytes, "
        "page_count, doc_type, status, report_date) values (%s, 'lab.pdf', 'application/pdf', "
        "gen_random_uuid()::text, gen_random_uuid()::text, 1, 1, 'lab_report', 'done', "
        "'2026-09-01') returning id",
        (user,),
    ).fetchone()[0]
    conn.execute(
        "insert into lab_results (user_id, document_id, test_name, value_text, unit, flag, "
        "report_date, page) values (%s, %s, %s, %s, %s, %s, '2026-09-01', 1)",
        (user, doc, test, value, unit or None, flag),
    )
    return doc


def events_of(events: list[dict], kind: str) -> Iterator[dict]:
    return (e for e in events if e.get("type") == kind)
