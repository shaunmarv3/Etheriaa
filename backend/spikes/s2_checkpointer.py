"""Spike 2 (spec 4.8, D8, D13): checkpoints as execution state, not history.

LangGraph concepts exercised:
- AsyncPostgresSaver: the Postgres checkpointer (one row set per checkpoint).
- durability="exit": persist only when the run ends (one checkpoint per turn).
- Time travel: aget_state_history + running from an old checkpoint_id = a fork.
- aupdate_state(as_node=...): write state as if a node produced it (rebuild path).
- aprune / adelete_thread: storage control.

The graph is a stand-in for the real one: same shape of state (messages window +
summary + a per-turn `turn` dict that finalize empties), no LLM calls.

Run: cd backend && uv run python spikes/s2_checkpointer.py
"""

import json
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from _common import check, load_env, require, run, summary
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str
    turn: dict[str, Any]


async def load_context(state: State) -> dict:
    return {"turn": {"evidence": ["x" * 2000] * 10}}  # ~20 KB of per-turn junk


async def understand(state: State) -> dict:
    return {"turn": {**state["turn"], "intent": "general_health"}}


async def generate(state: State) -> dict:
    n = sum(isinstance(m, HumanMessage) for m in state["messages"])
    return {"messages": [AIMessage(f"answer to turn {n}")], "turn": {**state["turn"], "reply": "ok"}}


async def finalize(state: State) -> dict:
    return {"turn": {}}  # spec 4.2: finalize empties the per-turn field


def build(checkpointer):
    g = StateGraph(State)
    for name, fn in [("load_context", load_context), ("understand", understand),
                     ("generate", generate), ("finalize", finalize)]:
        g.add_node(name, fn)
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "understand")
    g.add_edge("understand", "generate")
    g.add_edge("generate", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


async def history(graph, cfg) -> list:
    return [s async for s in graph.aget_state_history(cfg)]


async def turn(graph, cfg, text: str):
    return await graph.ainvoke({"messages": [HumanMessage(text)], "summary": ""}, cfg, durability="exit")


async def main() -> int:
    load_env()
    dsn = require("DATABASE_OWNER_URL")
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        graph = build(saver)
        thread = str(uuid4())
        cfg = {"configurable": {"thread_id": thread}}

        # 1. one checkpoint per turn
        await turn(graph, cfg, "turn one")
        n1 = len(await history(graph, cfg))
        await turn(graph, cfg, "turn two")
        n2 = len(await history(graph, cfg))
        check("durability=exit: 1 checkpoint per turn", n2 - n1 == 1, f"after t1={n1} after t2={n2}")

        # 2. finalize empties turn; measure the persisted size
        snap = await graph.aget_state(cfg)
        size = len(json.dumps(snap.values, default=str))
        check("persisted turn is empty", snap.values["turn"] == {}, f"state json ~{size} bytes")

        # 3. regenerate = fork from the checkpoint that ended the previous turn
        hist = await history(graph, cfg)  # newest first

        def humans(s) -> int:
            return sum(isinstance(m, HumanMessage) for m in s.values.get("messages", []))

        prev = next(s for s in hist if humans(s) == 1 and s.next == ())
        fork_cfg = prev.config  # carries checkpoint_id
        await graph.ainvoke({"messages": [HumanMessage("turn two")], "summary": ""}, fork_cfg,
                            durability="exit")
        latest = await graph.aget_state(cfg)
        check("fork: latest state has 2 turns, not 3", humans(latest) == 2, f"humans={humans(latest)}")
        check("fork: latest parent is the turn-1 checkpoint",
              latest.parent_config["configurable"]["checkpoint_id"]
              == prev.config["configurable"]["checkpoint_id"])
        check("fork: old turn-2 checkpoint still in history",
              len(await history(graph, cfg)) == len(hist) + 1)

        # 4. aprune is NOT implemented by langgraph-checkpoint-postgres 3.1.x
        #    (the base class raises NotImplementedError). Pruning an idle thread
        #    therefore means deleting it; the next turn rebuilds it from messages.
        try:
            await saver.aprune([thread], strategy="keep_latest")
            pruned = "implemented"
        except NotImplementedError:
            pruned = "NotImplementedError"
        print(f"      aprune on AsyncPostgresSaver: {pruned}")

        # 5. prune = adelete_thread; fallback = rebuild from the messages table (simulated)
        rebuilt = [HumanMessage("turn one"), AIMessage("answer to turn 1")]
        await saver.adelete_thread(thread)
        check("adelete_thread removes everything", len(await history(graph, cfg)) == 0)
        await graph.aupdate_state(cfg, {"messages": rebuilt, "summary": "", "turn": {}}, as_node="finalize")
        out = await turn(graph, cfg, "turn two again")
        check("rebuilt thread runs the next turn", humans(await graph.aget_state(cfg)) == 2,
              out["messages"][-1].content)
    return summary()


if __name__ == "__main__":
    run(main)
