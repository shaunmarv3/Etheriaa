"""The post-hoc audit (spec 4.6 "After"): a larger model grades a reply that has
already streamed against the product rules. It is measurement, not a gate: the
blocking controls are the deterministic ones. The verdict is written back to the
message's metadata; failures are logged and never reach the user."""

from typing import Literal

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from etheria.db.repositories import chat
from etheria.db.session import Database
from etheria.graph.deps import AuditJob, ModelFactory
from etheria.llm.prompts import load_prompt, wrap_document

log = structlog.get_logger("etheria.audit")

Rule = Literal[
    "diagnosis", "dosing", "safe_combination", "emergency", "unsupported_claims", "injection"
]


class ExpectationResult(BaseModel):
    expectation: str
    met: bool
    note: str = ""


class AuditVerdict(BaseModel):
    violations: list[Rule] = Field(default=[], description="Rules the reply clearly breaks")
    notes: str = Field(default="", description="One or two sentences explaining any violation")
    expectations: list[ExpectationResult] = []


def audit_prompt(
    question: str, reply: str, triage_level: str, evidence: list[str], expectations: list[str]
) -> list:
    parts = [
        f"Triage level: {triage_level}",
        "User message:\n" + question,
        "Evidence the reply was given:\n" + ("\n".join(evidence) or "(none)"),
        "Reply to audit:\n" + wrap_document(reply),
    ]
    if expectations:
        parts.append("Expectations:\n" + "\n".join(f"- {x}" for x in expectations))
    return [SystemMessage(load_prompt("audit")), HumanMessage("\n\n".join(parts))]


async def grade(
    models: ModelFactory,
    question: str,
    reply: str,
    triage_level: str,
    evidence: list[str],
    expectations: list[str] | None = None,
) -> AuditVerdict:
    model = models.structured("audit", AuditVerdict)
    return await model.ainvoke(
        audit_prompt(question, reply, triage_level, evidence, expectations or [])
    )


async def run_audit(models: ModelFactory, db: Database, job: AuditJob) -> None:
    try:
        verdict = await grade(models, job.question, job.reply, job.triage_level, job.evidence)
        async with db.for_user(job.user_id) as s:
            await chat.update_metadata(
                s, job.user_id, job.message_id, job.created_at, {"audit": verdict.model_dump()}
            )
        if verdict.violations:
            log.warning("audit_violation", message_id=str(job.message_id), rules=verdict.violations)
    except Exception as e:
        log.warning("audit_failed", message_id=str(job.message_id), error=type(e).__name__)
