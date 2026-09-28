"""retrieval_agent (spec 4.5): a bounded tool-calling agent, run as a subgraph
by a wrapper node.

LangGraph/LangChain concepts: `create_agent` returns a compiled graph (model
node <-> tools node). Middleware bounds it: `ModelCallLimitMiddleware` ends the
run after 3 model calls, `ToolCallLimitMiddleware` allows 8 tool calls. A
custom `state_schema` gives the tools data the model should not have to pass as
arguments (the test catalogue, a stated pregnancy). The wrapper streams the
agent with `stream_mode="updates"` and collects each tool's artifact as it
arrives, so when the 25 s bound cuts the run, the evidence gathered so far
survives."""

import asyncio
import json
import time
import warnings

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from etheria.graph.context import ChatContext
from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, history, log, record_block, status
from etheria.graph.schemas import Evidence
from etheria.graph.state import ChatState
from etheria.graph.tools import make_tools
from etheria.llm.prompts import load_prompt

# ToolRuntime carries our frozen dataclass context through a pydantic field typed
# `None`; pydantic warns on every tool call. Harmless; silenced by message.
warnings.filterwarnings("ignore", message=r"Pydantic serializer warnings", category=UserWarning)

MODEL_CALLS = 3
TOOL_CALLS = 8

STATUS = {
    "get_lab_values": "Checking your lab results",
    "get_current_medications": "Checking your medicines",
    "search_my_reports": "Searching your reports",
    "search_medical_literature": "Searching medical research",
    "search_health_topics": "Looking up health information",
    "explore_conditions": "Checking possible causes",
    "resolve_medicine": "Identifying the medicine",
    "check_interactions": "Checking medicine interactions",
}


class RetrievalState(AgentState):
    test_catalogue: list[str]
    pregnant: bool


def build_agent(deps: GraphDeps):
    return create_agent(
        deps.models.chat("retrieval_agent"),
        make_tools(deps),
        system_prompt=load_prompt("retrieval_agent"),
        state_schema=RetrievalState,
        context_schema=ChatContext,
        middleware=[
            ModelCallLimitMiddleware(run_limit=MODEL_CALLS, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=TOOL_CALLS),
        ],
        name="retrieval_agent",
    )


def agent_input(state: ChatState) -> str:
    turn = state["turn"]
    u = turn.understanding
    understanding = u.model_dump(exclude_defaults=True) if u else {}
    recent = history(state["messages"], state.get("summary", ""), last=4)
    lines = [
        "Understanding: " + json.dumps(understanding, ensure_ascii=False),
        "",
        record_block(turn),
    ]
    if recent:
        lines += ["", "Recent conversation:"]
        lines += [f"{m.type}: {str(m.content)[:400]}" for m in recent]
    lines += ["", f"User message: {turn.user_message}"]
    return "\n".join(lines)


def make_retrieval_agent(deps: GraphDeps):
    agent = build_agent(deps)

    async def retrieval_agent(state: ChatState, runtime: Runtime[ChatContext]) -> dict:
        timer = Timer()
        turn = state["turn"]
        u = turn.understanding
        evidence: list[Evidence] = []
        called: list[str] = []
        cache_before = deps.cache_hits()
        inputs = {
            "messages": [HumanMessage(agent_input(state))],
            "test_catalogue": turn.test_catalogue,
            "pregnant": bool(u and u.pregnant),
        }

        async def run() -> None:
            async for update in agent.astream(
                inputs, context=runtime.context, stream_mode="updates"
            ):
                for part in update.values():
                    for m in (part or {}).get("messages", []) if isinstance(part, dict) else []:
                        if isinstance(m, AIMessage):
                            for call in m.tool_calls:
                                called.append(call["name"])
                                status("retrieval", STATUS.get(call["name"], "Looking things up"))
                        elif isinstance(m, ToolMessage) and m.artifact:
                            evidence.extend(m.artifact)

        outcome = "done"
        started = time.perf_counter()
        try:
            await asyncio.wait_for(run(), deps.agent_timeout_s)
        except TimeoutError:
            outcome = "timed out; kept what was collected"
        except Exception as e:  # keep the evidence; generation continues without the rest
            log.warning("retrieval_agent_failed", error=type(e).__name__)
            outcome = f"failed ({type(e).__name__}); kept what was collected"
        entry = timer.entry(
            "retrieval_agent",
            "retrieval",
            f"{len(evidence)} evidence items; {outcome}",
            tools=called,
            seconds=round(time.perf_counter() - started, 2),
        )
        return {
            "turn": {
                "evidence": evidence,
                "agent_tools": called,
                "cache_hits": deps.cache_hits() - cache_before,
                "trace": [entry],
            }
        }

    return retrieval_agent
