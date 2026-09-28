"""input_guard (spec 4.3, 4.6): abuse and injection heuristics plus the
red-flag pre-scan. When the rules already say RED, the emergency block is sent
here, before any LLM call (plan Decision 2)."""

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, token
from etheria.graph.state import ChatState
from etheria.safety.input_guard import check
from etheria.safety.texts import emergency_block


def make_input_guard(deps: GraphDeps):
    async def input_guard(state: ChatState) -> dict:
        timer = Timer()
        result = check(state["turn"].user_message, deps.matcher)
        update: dict = {"guard": result}
        if result.rule_level == "RED":
            token(emergency_block(result.helpline))
            update |= {"emergency_sent": True, "helpline_sent": result.helpline}
        output = (
            f"blocked ({result.reason})"
            if result.blocked
            else f"rules: {result.rule_level or 'none'}"
        )
        update["trace"] = [timer.entry("input_guard", "safety", output, rules=result.rule_ids)]
        return {"turn": update}

    return input_guard
