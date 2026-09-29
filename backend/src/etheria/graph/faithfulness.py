"""Faithfulness (RAGAS method, written here; spec 15): what share of a reply's
factual claims is supported by the context the reply was generated from.

Two calls to the audit model, as RAGAS does: split the reply into standalone
claims, then check each claim against the context. Score = supported / claims.
The context is exactly what `generate` saw: the user's record and the
evidence block. A claim from general medical knowledge that the context does
not hold counts as unsupported, so a low score marks a reply that leans on
the model's own knowledge, not necessarily a wrong one. Measurement only: it
runs in the eval, never on a live turn."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from etheria.graph.deps import ModelFactory
from etheria.llm.prompts import load_prompt, wrap_document


class Claims(BaseModel):
    claims: list[str] = Field(default=[], description="Standalone factual claims, one per item")


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool
    note: str = Field(default="", description="What is missing, for an unsupported claim")


class Check(BaseModel):
    number: int = Field(description="The claim's number in the list")
    supported: bool
    note: str = Field(default="", description="What is missing, for an unsupported claim")


class Verification(BaseModel):
    checks: list[Check] = []


class Faithfulness(BaseModel):
    verdicts: list[ClaimVerdict] = []

    @property
    def score(self) -> float | None:
        """None when the reply makes no factual claim (nothing to be unfaithful about)."""
        if not self.verdicts:
            return None
        return sum(v.supported for v in self.verdicts) / len(self.verdicts)

    @property
    def unsupported(self) -> list[ClaimVerdict]:
        return [v for v in self.verdicts if not v.supported]


async def faithfulness(
    models: ModelFactory, question: str, reply: str, context: str
) -> Faithfulness:
    claims: Claims = await models.structured("audit", Claims).ainvoke(
        [
            SystemMessage(load_prompt("faithfulness_claims")),
            HumanMessage(f"User message:\n{question}\n\nReply:\n{wrap_document(reply)}"),
        ]
    )
    if not claims.claims:
        return Faithfulness()
    listed = "\n".join(f"{i}. {c}" for i, c in enumerate(claims.claims, 1))
    checked: Verification = await models.structured("audit", Verification).ainvoke(
        [
            SystemMessage(load_prompt("faithfulness_verify")),
            HumanMessage(f"Context:\n{wrap_document(context)}\n\nClaims:\n{listed}"),
        ]
    )
    # Matched by number; a claim the verifier skipped counts as unsupported.
    by_number = {c.number: c for c in checked.checks}
    verdicts = []
    for i, claim in enumerate(claims.claims, 1):
        c = by_number.get(i)
        verdicts.append(
            ClaimVerdict(claim=claim, supported=c.supported, note=c.note)
            if c
            else ClaimVerdict(claim=claim, supported=False, note="not checked by the verifier")
        )
    return Faithfulness(verdicts=verdicts)
