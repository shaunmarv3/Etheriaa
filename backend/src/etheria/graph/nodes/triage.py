"""triage (spec 4.3, 4.6 "Before"): the rule table plus the model's assessment;
the higher level wins, so rules can only raise it. If the model fails, the
level is at least YELLOW: fail toward caution, never GREEN. For RED the
emergency block goes out now unless input_guard already sent it."""

from langchain_core.messages import HumanMessage, SystemMessage

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, attempts, record_block, token
from etheria.graph.schemas import TriageAssessment, TriageResult
from etheria.graph.state import ChatState
from etheria.llm.prompts import load_prompt
from etheria.safety.texts import TELE_MANAS, emergency_block
from etheria.safety.triage_rules import max_level


def make_triage(deps: GraphDeps):
    async def triage(state: ChatState) -> dict:
        timer = Timer()
        turn = state["turn"]
        guard = turn.guard
        rule_level = guard.rule_level if guard else None
        rule_ids = guard.rule_ids if guard else []
        u = turn.understanding
        described = ""
        if u is not None:
            symptoms = [
                s.name + (f" ({s.duration})" if s.duration else "")
                for s in u.symptoms
                if not s.negated
            ]
            described = (
                f"Intent: {u.intent}. Symptoms: {', '.join(symptoms) or 'none'}. "
                f"Red flags noticed: {', '.join(u.red_flags) or 'none'}. "
                f"Pregnant: {'yes' if u.pregnant else 'not stated'}."
            )
        prompt = [
            SystemMessage(load_prompt("triage")),
            SystemMessage(record_block(turn)),
            HumanMessage(f"{turn.user_message}\n\n({described})"),
        ]
        model = deps.models.structured("triage", TriageAssessment)
        try:
            a: TriageAssessment = await attempts(lambda: model.ainvoke(prompt), 2, "triage")
            level = max_level(rule_level, a.level)
            if rule_level is None or level != rule_level:
                source = "model"
            else:
                source = "both" if a.level == rule_level else "rules"
            result = TriageResult(
                level=level,
                reasons=a.reasons,
                rule_ids=rule_ids,
                source=source,
                helpline=bool((guard and guard.helpline) or a.self_harm),
            )
        except Exception:
            result = TriageResult(
                level=max_level(rule_level, "YELLOW"),
                reasons=["Automatic assessment unavailable; defaulting to caution"],
                rule_ids=rule_ids,
                source="fallback",
                helpline=bool(guard and guard.helpline),
            )
        update: dict = {"triage": result}
        if result.level == "RED" and not turn.emergency_sent:
            token(emergency_block(result.helpline))
            update |= {"emergency_sent": True, "helpline_sent": result.helpline}
        elif result.helpline and turn.emergency_sent and not turn.helpline_sent:
            token(TELE_MANAS + "\n\n")  # self-harm seen by the model after the rule block
            update["helpline_sent"] = True
        update["trace"] = [
            timer.entry("triage", "safety", result.level, source=result.source, rules=rule_ids)
        ]
        return {"turn": update}

    return triage
