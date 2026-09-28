"""understand (spec 4.3): structured output describing the question. Three
attempts, then a `general_health` fallback recorded in the trace. Test names the
model returns are kept only if they are in the user's catalogue."""

from langchain_core.messages import HumanMessage, SystemMessage

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, attempts, history, record_block, status
from etheria.graph.schemas import Understanding
from etheria.graph.state import ChatState
from etheria.llm.prompts import load_prompt


def make_understand(deps: GraphDeps):
    async def understand(state: ChatState) -> dict:
        timer = Timer()
        turn = state["turn"]
        status("understand", "Understanding your question")
        prompt = [
            SystemMessage(load_prompt("understand")),
            SystemMessage(record_block(turn)),
            *history(state["messages"], state.get("summary", ""), last=4),
            HumanMessage(turn.user_message),
        ]
        model = deps.models.structured("understand", Understanding)
        fallback = False
        try:
            result: Understanding = await attempts(lambda: model.ainvoke(prompt), 3, "understand")
        except Exception:
            result, fallback = Understanding(intent="general_health"), True
        known = {t.lower(): t for t in turn.test_catalogue}
        result = result.model_copy(
            update={
                "relevant_tests": [
                    known[t.lower()] for t in result.relevant_tests if t.lower() in known
                ],
                "search_query": result.search_query or turn.user_message,
            }
        )
        output = f"intent {result.intent}" + (" (fallback)" if fallback else "")
        entry = timer.entry(
            "understand",
            "understanding",
            output,
            symptoms=[s.name for s in result.symptoms],
            medications=result.medications,
            fallback=fallback,
        )
        return {"turn": {"understanding": result, "trace": [entry]}}

    return understand
