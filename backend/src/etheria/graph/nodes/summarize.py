"""summarize (spec 4.3, 4.8): when the window exceeds 20 messages, fold all but
the last 8 into the rolling summary and remove them from the state.

LangGraph concept: `RemoveMessage(id=...)` is understood by the `add_messages`
reducer as "delete this message", so a node can shrink the window."""

from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, attempts, log
from etheria.graph.state import KEEP, ChatState
from etheria.llm.prompts import load_prompt


def make_summarize(deps: GraphDeps):
    async def summarize(state: ChatState) -> dict:
        timer = Timer()
        old = state["messages"][:-KEEP]
        transcript = "\n".join(f"{m.type}: {m.content}" for m in old)
        prompt = [
            SystemMessage(load_prompt("summarize")),
            HumanMessage(
                f"Existing summary:\n{state.get('summary') or '(none)'}\n\n"
                f"Messages to fold in:\n{transcript}"
            ),
        ]
        model = deps.models.chat("summarize")
        try:
            reply = await attempts(lambda: model.ainvoke(prompt), 2, "summarize")
        except Exception as e:
            # Skip; the next turn tries again (spec 4.3).
            log.warning("summarize_skipped", error=type(e).__name__)
            entry = timer.entry("summarize", "memory", "skipped after an error")
            return {"turn": {"trace": [entry]}}
        return {
            "summary": str(reply.content).strip(),
            "messages": [RemoveMessage(id=m.id) for m in old if m.id],
            "turn": {"trace": [timer.entry("summarize", "memory", f"folded {len(old)} messages")]},
        }

    return summarize
