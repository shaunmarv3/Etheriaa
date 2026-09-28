"""load_context (spec 4.3): fill the turn with the user's record. A failure here
is a hard failure: the service turns it into an `error` event."""

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from etheria.db.repositories import health_record as hr
from etheria.graph.context import ChatContext
from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, status
from etheria.graph.state import ChatState


def make_load_context(deps: GraphDeps):
    async def load_context(state: ChatState, runtime: Runtime[ChatContext]) -> dict:
        timer = Timer()
        user_id = runtime.context.user_id
        message = next(
            (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
        )
        async with deps.db.for_user(user_id) as s:
            index = await hr.report_index(s, user_id)
            catalogue = await hr.test_catalogue(s, user_id)
            snapshot = await hr.lab_snapshot(s, user_id)
            meds = await hr.medications(s, user_id)
            conditions = await hr.conditions(s, user_id)
        if index:
            status("context", "Reading your reports")
        return {
            "turn": {
                "user_message": str(message),
                "report_index": index,
                "test_catalogue": catalogue,
                "lab_snapshot": snapshot,
                "current_medications": meds,
                "conditions": conditions,
                "trace": [
                    timer.entry(
                        "load_context",
                        "context",
                        f"{len(index)} reports, {len(snapshot)} abnormal values, "
                        f"{len(meds)} medicines",
                    )
                ],
            }
        }

    return load_context
