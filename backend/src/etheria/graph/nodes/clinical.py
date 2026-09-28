"""clinical_structuring (spec 4.3): the differential (symptom questions only) and
2-4 follow-up questions, in parallel with generate. Empty on failure, and
skipped for RED, where the reply must stay short and action-oriented. The same
deterministic rules as the stream are applied to every string it returns."""

from langchain_core.messages import HumanMessage, SystemMessage

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, attempts, evidence_block, record_block
from etheria.graph.schemas import ClinicalOutput, DifferentialItem
from etheria.graph.state import ChatState
from etheria.llm.prompts import load_prompt
from etheria.safety.stream_guard import apply_rules

MAX_DIFFERENTIAL = 4
MAX_FOLLOW_UPS = 4


def _clean(text: str) -> str:
    return apply_rules(text)[0]


def make_clinical(deps: GraphDeps):
    async def clinical_structuring(state: ChatState) -> dict:
        timer = Timer()
        turn = state["turn"]
        u = turn.understanding
        if turn.triage and turn.triage.level == "RED":
            entry = timer.entry("clinical_structuring", "clinical", "skipped (RED)")
            return {"turn": {"clinical": ClinicalOutput(), "trace": [entry]}}
        wants_differential = u is not None and (
            u.intent == "symptom_check" or (u.intent == "follow_up" and bool(u.symptoms))
        )
        prompt = [
            SystemMessage(load_prompt("clinical_structuring")),
            SystemMessage(record_block(turn) + "\n\n" + evidence_block(turn.evidence)),
            HumanMessage(
                f"{turn.user_message}\n\n"
                f"(Differential wanted: {'yes' if wants_differential else 'no'})"
            ),
        ]
        model = deps.models.structured("clinical_structuring", ClinicalOutput)
        try:
            out: ClinicalOutput = await attempts(lambda: model.ainvoke(prompt), 2, "clinical")
        except Exception:
            entry = timer.entry("clinical_structuring", "clinical", "empty after an error")
            return {"turn": {"clinical": ClinicalOutput(), "trace": [entry]}}
        differential = (
            [
                DifferentialItem(
                    condition=d.condition,
                    likelihood=d.likelihood,
                    rationale=_clean(d.rationale),
                    workup=[_clean(w) for w in d.workup],
                    citations=d.citations,
                )
                for d in out.differential[:MAX_DIFFERENTIAL]
            ]
            if wants_differential
            else []
        )
        result = ClinicalOutput(
            differential=differential,
            follow_up_questions=[_clean(q) for q in out.follow_up_questions[:MAX_FOLLOW_UPS]],
        )
        entry = timer.entry(
            "clinical_structuring",
            "clinical",
            f"{len(result.differential)} differential, "
            f"{len(result.follow_up_questions)} follow-ups",
        )
        return {"turn": {"clinical": result, "trace": [entry]}}

    return clinical_structuring
