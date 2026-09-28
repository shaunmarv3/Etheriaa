"""Builds the chat graph (spec 4.4):

    START -> load_context -> input_guard
    input_guard --blocked--> canned_reply
    input_guard --window > 20--> summarize -> understand
    input_guard --otherwise--> understand
    understand --off_topic | upload_help--> canned_reply
    understand --otherwise--> retrieval_agent and triage (parallel)
    [retrieval_agent, triage] -> rerank_evidence            (waiting join)
    rerank_evidence -> generate and clinical_structuring    (parallel)
    [generate, clinical_structuring] -> finalize            (waiting join)
    canned_reply -> finalize -> END

LangGraph concepts: conditional edges (a routing function picks the next
node, or a list of nodes to fan out to); a *waiting edge* `add_edge([a, b], c)`
runs `c` once, after both `a` and `b` have finished."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from etheria.graph.agent import make_retrieval_agent
from etheria.graph.context import ChatContext
from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.canned import canned_reply
from etheria.graph.nodes.clinical import make_clinical
from etheria.graph.nodes.context import make_load_context
from etheria.graph.nodes.finalize import make_finalize
from etheria.graph.nodes.generate import make_generate
from etheria.graph.nodes.guard import make_input_guard
from etheria.graph.nodes.rerank import make_rerank
from etheria.graph.nodes.summarize import make_summarize
from etheria.graph.nodes.triage import make_triage
from etheria.graph.nodes.understand import make_understand
from etheria.graph.schemas import CHECKPOINT_TYPES
from etheria.graph.state import ChatState, route_after_guard, route_after_understand


def serializer() -> JsonPlusSerializer:
    """The checkpoint serializer, allowing exactly our state classes (without the
    allowlist LangGraph warns, and will later refuse, to load them)."""
    return JsonPlusSerializer(
        allowed_msgpack_modules=[(c.__module__, c.__name__) for c in CHECKPOINT_TYPES]
    )


def build_graph(
    deps: GraphDeps, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    g = StateGraph(ChatState, context_schema=ChatContext)
    g.add_node("load_context", make_load_context(deps))
    g.add_node("input_guard", make_input_guard(deps))
    g.add_node("summarize", make_summarize(deps))
    g.add_node("understand", make_understand(deps))
    g.add_node("retrieval_agent", make_retrieval_agent(deps))
    g.add_node("triage", make_triage(deps))
    g.add_node("rerank_evidence", make_rerank(deps))
    g.add_node("generate", make_generate(deps))
    g.add_node("clinical_structuring", make_clinical(deps))
    g.add_node("canned_reply", canned_reply)
    g.add_node("finalize", make_finalize(deps))

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "input_guard")
    g.add_conditional_edges(
        "input_guard", route_after_guard, ["canned_reply", "summarize", "understand"]
    )
    g.add_edge("summarize", "understand")
    g.add_conditional_edges(
        "understand", route_after_understand, ["canned_reply", "retrieval_agent", "triage"]
    )
    g.add_edge(["retrieval_agent", "triage"], "rerank_evidence")
    g.add_edge("rerank_evidence", "generate")
    g.add_edge("rerank_evidence", "clinical_structuring")
    g.add_edge(["generate", "clinical_structuring"], "finalize")
    g.add_edge("canned_reply", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer, name="etheria_chat")


def mermaid(graph: CompiledStateGraph) -> str:
    return graph.get_graph().draw_mermaid()
