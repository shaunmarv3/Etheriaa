"""Streamed chat, regenerate and history over HTTP (spec 4.7, 4.8, 10), with
scripted models injected into the real app. Review Focus 1-4 of the M4 plan."""

import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from graph_fakes import BrokenStream, FakeModels, ScriptedChat, streaming, tool_call
from langchain_core.messages import AIMessage
from support import running_app

from etheria.graph.schemas import TriageAssessment, Understanding
from etheria.safety.texts import DISCLAIMER, EMERGENCY

METADATA_KEYS = {
    "type",
    "session_id",
    "triage_level",
    "symptoms",
    "follow_up_questions",
    "differential",
    "citations",
    "agent_trace",
    "message_id",
}
CHAT_RESPONSE_KEYS = {
    "session_id",
    "reply",
    "triage_level",
    "symptoms",
    "follow_up_questions",
    "differential",
    "citations",
    "message_id",
}


def _models(generate_text: str = "Rest and fluids help.", **extra) -> FakeModels:
    return FakeModels(
        structured={
            "understand": [Understanding(intent="general_health")],
            "triage": [TriageAssessment(level="GREEN", reasons=["general"])],
            **extra.pop("structured", {}),
        },
        chat={"generate": streaming(generate_text), **extra.pop("chat", {})},
    )


def make_app(settings, models: FakeModels) -> FastAPI:
    from etheria.api.app import create_app

    return create_app(settings, chat_overrides={"models": models, "reranker": None})


@pytest.fixture
async def chat_client(settings, migrated_db, clean_redis) -> AsyncIterator:
    """Yields a function that starts an app with the given models."""
    apps = []

    async def start(models: FakeModels) -> httpx.AsyncClient:
        cm = running_app(make_app(settings, models))
        client = await cm.__aenter__()
        apps.append(cm)
        return client

    yield start
    for cm in reversed(apps):
        await cm.__aexit__(None, None, None)


async def _token(client: httpx.AsyncClient) -> dict[str, str]:
    email = f"{uuid4().hex[:10]}@example.com"
    r = await client.post("/auth/register", json={"email": email, "password": "correct horse 1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _stream(client, headers, body) -> list[dict]:
    r = await client.post("/chat/stream", json=body, headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(line[len("data: ") :])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]


def _text(events: list[dict]) -> str:
    return "".join(e["content"] for e in events if e["type"] == "token")


async def test_stream_contract_and_history(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    events = await _stream(client, headers, {"message": "How do I sleep better?"})
    types = [e["type"] for e in events]
    assert types[-2:] == ["metadata", "done"]
    assert set(types) <= {"status", "token", "metadata", "done"}
    meta = events[-2]
    assert set(meta) == METADATA_KEYS
    assert _text(events).startswith("Rest and fluids help.")
    assert _text(events).endswith(DISCLAIMER + "_")
    session = meta["session_id"]

    r = await client.get("/history/", params={"page": 1, "page_size": 10}, headers=headers)
    body = r.json()
    assert (body["total"], body["page"], body["page_size"]) == (1, 1, 10)
    (s,) = body["sessions"]
    assert s["session_id"] == session and s["message_count"] == 2
    assert s["preview"] == "How do I sleep better?" and s["triage_level"] == "GREEN"
    assert {"started_at", "ended_at", "name"} <= set(s)

    detail = (await client.get(f"/history/{session}", headers=headers)).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["message_id"] == meta["message_id"]
    assert assistant["content"] == _text(events)
    assert {"intent", "symptoms", "triage_level", "citations", "differential", "created_at"} <= set(
        assistant
    )


async def test_second_turn_continues_the_session(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    first = await _stream(client, headers, {"message": "hello"})
    session = first[-2]["session_id"]
    second = await _stream(client, headers, {"message": "thanks", "session_id": session})
    assert second[-2]["session_id"] == session
    detail = (await client.get(f"/history/{session}", headers=headers)).json()
    assert [m["content"][:6] for m in detail["messages"] if m["role"] == "user"] == [
        "hello",
        "thanks",
    ]


async def test_cross_user_conversation_is_404(chat_client) -> None:
    client = await chat_client(_models())
    alice, bob = await _token(client), await _token(client)
    session = (await _stream(client, alice, {"message": "hello"}))[-2]["session_id"]
    r = await client.post(
        "/chat/stream", json={"message": "hi", "session_id": session}, headers=bob
    )
    assert (r.status_code, r.json()["error"]["code"]) == (404, "not_found")
    r = await client.post("/chat/regenerate", json={"session_id": session}, headers=bob)
    assert r.status_code == 404
    for method in ("get", "delete"):
        r = await client.request(method, f"/history/{session}", headers=bob)
        assert r.status_code == 404, method
    r = await client.patch(f"/history/{session}", json={"name": "x"}, headers=bob)
    assert r.status_code == 404
    assert (await client.get(f"/history/{session}", headers=alice)).status_code == 200


async def test_stream_red_block_first(chat_client) -> None:
    client = await chat_client(_models("Call now."))
    headers = await _token(client)
    events = await _stream(client, headers, {"message": "chest pain and sweating, left arm heavy"})
    first_token = next(e for e in events if e["type"] == "token")
    assert first_token["content"].startswith("**" + EMERGENCY.strip("*"))
    assert events[-2]["triage_level"] == "RED"


async def test_generate_failure_mid_stream(chat_client) -> None:
    client = await chat_client(_models(chat={"generate": BrokenStream(before="Rest well. Drink")}))
    headers = await _token(client)
    events = await _stream(client, headers, {"message": "I feel tired"})
    assert events[-1]["type"] == "error" and "detail" in events[-1]
    assert "Rest well." in _text(events)
    history = (await client.get("/history/", headers=headers)).json()["sessions"]
    session = history[0]["session_id"]
    detail = (await client.get(f"/history/{session}", headers=headers)).json()
    partial = detail["messages"][-1]
    assert partial["role"] == "assistant" and partial["content"].startswith("Rest well.")
    assert partial["incomplete"] is True


async def test_next_turn_works_after_a_failure(settings, chat_client) -> None:
    broken = await chat_client(_models(chat={"generate": BrokenStream(before="Rest")}))
    headers = await _token(broken)
    session = None
    events = await _stream(broken, headers, {"message": "I feel tired"})
    history = (await broken.get("/history/", headers=headers)).json()["sessions"]
    session = history[0]["session_id"]
    assert events[-1]["type"] == "error"
    healthy = await chat_client(_models("Sleep and water."))
    events = await _stream(healthy, headers, {"message": "and now?", "session_id": session})
    assert events[-1]["type"] == "done"


async def test_turn_after_thread_deleted(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    session = (await _stream(client, headers, {"message": "first question"}))[-2]["session_id"]
    app = client._transport.app  # type: ignore[attr-defined]
    await app.state.chat.checkpointer.adelete_thread(session)  # a pruned thread
    events = await _stream(client, headers, {"message": "second question", "session_id": session})
    assert events[-1]["type"] == "done"
    state = await app.state.chat.graph.aget_state({"configurable": {"thread_id": session}})
    contents = [str(m.content) for m in state.values["messages"]]
    assert contents[0] == "first question"  # rebuilt from the messages table
    assert contents[-2] == "second question"


async def test_regenerate_forks_and_supersedes(chat_client) -> None:
    models = _models(
        chat={"generate": ScriptedChat(script=[AIMessage("First answer."), AIMessage("Second.")])}
    )
    client = await chat_client(models)
    headers = await _token(client)
    await _stream(client, headers, {"message": "turn one"})
    session = (await client.get("/history/", headers=headers)).json()["sessions"][0]["session_id"]
    await _stream(client, headers, {"message": "turn two", "session_id": session})
    r = await client.post("/chat/regenerate", json={"session_id": session}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == CHAT_RESPONSE_KEYS
    assert body["session_id"] == session
    detail = (await client.get(f"/history/{session}", headers=headers)).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]  # the old reply is hidden
    assert detail["messages"][-1]["message_id"] == body["message_id"]
    app = client._transport.app  # type: ignore[attr-defined]
    state = await app.state.chat.graph.aget_state({"configurable": {"thread_id": session}})
    users = [m for m in state.values["messages"] if m.type == "human"]
    assert [m.content for m in users] == ["turn one", "turn two"]  # a fork, not a third turn


async def test_regenerate_first_turn(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    session = (await _stream(client, headers, {"message": "only turn"}))[-2]["session_id"]
    r = await client.post("/chat/regenerate", json={"session_id": session}, headers=headers)
    assert r.status_code == 200, r.text
    detail = (await client.get(f"/history/{session}", headers=headers)).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


async def test_rename_and_delete(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    session = (await _stream(client, headers, {"message": "hello"}))[-2]["session_id"]
    r = await client.patch(f"/history/{session}", json={"name": "Sleep"}, headers=headers)
    assert r.json() == {"session_id": session, "name": "Sleep"}
    assert (await client.get("/history/", headers=headers)).json()["sessions"][0]["name"] == "Sleep"
    assert (await client.delete(f"/history/{session}", headers=headers)).status_code == 204
    assert (await client.get(f"/history/{session}", headers=headers)).status_code == 404
    app = client._transport.app  # type: ignore[attr-defined]
    state = await app.state.chat.graph.aget_state({"configurable": {"thread_id": session}})
    assert state.values == {}  # checkpoints deleted with the conversation


async def test_chat_rate_limit(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    app = client._transport.app  # type: ignore[attr-defined]
    app.state.chat_limit = 2
    for _ in range(2):
        assert (
            await client.post("/chat/stream", json={"message": "hi"}, headers=headers)
        ).status_code == 200
    r = await client.post("/chat/stream", json={"message": "hi"}, headers=headers)
    assert (r.status_code, r.json()["error"]["code"]) == (429, "rate_limited")


async def test_message_validation(chat_client) -> None:
    client = await chat_client(_models())
    headers = await _token(client)
    for body in ({"message": "   "}, {"message": "x" * 4001}):
        r = await client.post("/chat/stream", json=body, headers=headers)
        assert r.status_code == 422, body
    assert (await client.post("/chat/stream", json={"message": "hi"})).status_code == 401


async def test_agent_tools_run_through_the_api(owner_conn, chat_client) -> None:
    models = _models(
        "Your values [1].",
        chat={
            "retrieval_agent": ScriptedChat(
                script=[tool_call("get_current_medications", {}), AIMessage("DONE")]
            )
        },
    )
    client = await chat_client(models)
    headers = await _token(client)
    events = await _stream(client, headers, {"message": "what medicines am I on?"})
    meta = events[-2]
    assert meta["agent_trace"]["routing_flags"]["get_current_medications"] is True
