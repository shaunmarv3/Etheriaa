"""Conversations, messages and the health-record reads the chat graph uses
(spec 4.3 load_context, 4.5 tools, 7). Real Postgres, app role, RLS on."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
from ingestion_fakes import new_user

from etheria.db.repositories import chat
from etheria.db.repositories import health_record as hr
from etheria.db.session import Database


async def _conversation(db: Database, user: UUID, title: str = "t"):
    async with db.for_user(user) as s:
        return await chat.create_conversation(s, user, title)


async def test_conversation_and_messages_roundtrip(db: Database, owner_conn) -> None:
    user = new_user(owner_conn)
    conv = await _conversation(db, user, "Fever for 3 days")
    async with db.for_user(user) as s:
        u = await chat.insert_message(
            s, conversation_id=conv.id, user_id=user, role="user", content="hi", intent=None
        )
        a = await chat.insert_message(
            s,
            conversation_id=conv.id,
            user_id=user,
            role="assistant",
            content="hello",
            intent="general_health",
            metadata={"triage_level": "GREEN"},
        )
        await chat.touch(s, user, conv.id, "YELLOW")
    async with db.for_user(user) as s:
        msgs = await chat.list_messages(s, user, conv.id)
        assert [(m.role, m.content) for m in msgs] == [("user", "hi"), ("assistant", "hello")]
        assert msgs[1].meta == {"triage_level": "GREEN"}
        last_user, last_assistant = await chat.last_turn(s, user, conv.id)
        assert (last_user.id, last_assistant.id) == (u.id, a.id)
        assert (await chat.get_conversation(s, user, conv.id)).triage_level == "YELLOW"


async def test_triage_level_only_rises(db: Database, owner_conn) -> None:
    user = new_user(owner_conn)
    conv = await _conversation(db, user)
    async with db.for_user(user) as s:
        await chat.touch(s, user, conv.id, "RED")
        await chat.touch(s, user, conv.id, "GREEN")
        assert (await chat.get_conversation(s, user, conv.id)).triage_level == "RED"


async def test_other_users_cannot_see_conversations(db: Database, owner_conn) -> None:
    a, b = new_user(owner_conn), new_user(owner_conn)
    conv = await _conversation(db, a)
    async with db.for_user(b) as s:
        assert await chat.get_conversation(s, b, conv.id) is None
        assert await chat.list_messages(s, b, conv.id) == []
        total, rows = await chat.list_conversations(s, b, page=1, page_size=10)
        assert (total, rows) == (0, [])
        assert not await chat.rename(s, b, conv.id, "mine now")
        assert not await chat.soft_delete(s, b, conv.id)


async def test_list_is_paged_newest_first_with_preview(db: Database, owner_conn) -> None:
    user = new_user(owner_conn)
    ids = []
    for i in range(3):
        conv = await _conversation(db, user, f"c{i}")
        async with db.for_user(user) as s:
            await chat.insert_message(
                s, conversation_id=conv.id, user_id=user, role="user", content=f"first {i}" * 60
            )
            await chat.touch(s, user, conv.id, None)
        ids.append(conv.id)
    async with db.for_user(user) as s:
        total, rows = await chat.list_conversations(s, user, page=1, page_size=2)
        assert total == 3
        assert [r.conversation.id for r in rows] == [ids[2], ids[1]]
        assert rows[0].message_count == 1
        assert rows[0].preview.startswith("first 2") and len(rows[0].preview) == 200
        _, page2 = await chat.list_conversations(s, user, page=2, page_size=2)
        assert [r.conversation.id for r in page2] == [ids[0]]


async def test_soft_delete_hides_and_rename_sets_title(db: Database, owner_conn) -> None:
    user = new_user(owner_conn)
    conv = await _conversation(db, user)
    async with db.for_user(user) as s:
        assert await chat.rename(s, user, conv.id, "Knee pain")
        assert (await chat.get_conversation(s, user, conv.id)).title == "Knee pain"
        assert await chat.soft_delete(s, user, conv.id)
        assert await chat.get_conversation(s, user, conv.id) is None
        assert (await chat.list_conversations(s, user, 1, 10))[0] == 0


async def test_superseded_messages_are_hidden(db: Database, owner_conn) -> None:
    user = new_user(owner_conn)
    conv = await _conversation(db, user)
    async with db.for_user(user) as s:
        await chat.insert_message(
            s, conversation_id=conv.id, user_id=user, role="user", content="q"
        )
        old = await chat.insert_message(
            s, conversation_id=conv.id, user_id=user, role="assistant", content="old"
        )
        await chat.supersede(s, user, old)
        await chat.insert_message(
            s, conversation_id=conv.id, user_id=user, role="assistant", content="new"
        )
        assert [m.content for m in await chat.list_messages(s, user, conv.id)] == ["q", "new"]
        await chat.update_metadata(s, user, old.id, old.created_at, {"audit": {"ok": True}})
        everything = await chat.list_messages(s, user, conv.id, include_superseded=True)
        assert [m.content for m in everything] == ["q", "old", "new"]
        assert everything[1].meta["audit"] == {"ok": True}


def _seed_record(owner_conn: psycopg.Connection, user: UUID) -> None:
    doc, older, dis = uuid4(), uuid4(), uuid4()
    rows = [
        (doc, "cbc.pdf", "lab_report", date(2026, 9, 1), "CBC", None),
        (older, "old.pdf", "lab_report", date(2026, 1, 1), "Old CBC", None),
        (
            dis,
            "dis.pdf",
            "discharge_summary",
            date(2026, 8, 1),
            "Discharge",
            '{"diagnoses": ["Chronic kidney disease stage 3", "Hypertension"]}',
        ),
    ]
    for d, name, kind, rdate, summary, extracted in rows:
        owner_conn.execute(
            "insert into documents (id, user_id, filename, mime_type, storage_key, sha256, "
            "size_bytes, page_count, doc_type, status, report_date, summary, extracted) "
            "values (%s, %s, %s, 'application/pdf', %s, %s, 1, 1, %s, 'done', %s, %s, %s)",
            (d, user, name, uuid4().hex, uuid4().hex, kind, rdate, summary, extracted),
        )
    labs = [
        (doc, "Haemoglobin", "9.1", Decimal("9.1"), "g/dL", "12-15", "low", date(2026, 9, 1)),
        (
            doc,
            "Platelet count",
            "2,45,000",
            Decimal(245000),
            "/uL",
            "1.5-4.1 lakh",
            "normal",
            date(2026, 9, 1),
        ),
        (older, "Haemoglobin", "11.0", Decimal("11.0"), "g/dL", "12-15", "low", date(2026, 1, 1)),
        (older, "TSH", "7.8", Decimal("7.8"), "uIU/mL", "0.4-4.2", "high", date(2026, 1, 1)),
    ]
    for d, test, vt, vn, unit, rng, flag, rdate in labs:
        owner_conn.execute(
            "insert into lab_results (user_id, document_id, test_name, value_text, value_numeric, "
            "unit, ref_range_text, flag, report_date, page) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)",
            (user, d, test, vt, vn, unit, rng, flag, rdate),
        )
    for name, rdate in (("Telma 40", date(2026, 8, 1)), ("telma 40", date(2026, 1, 1))):
        owner_conn.execute(
            "insert into medications (user_id, document_id, name_raw, frequency, source, "
            "report_date) values (%s, %s, %s, 'once daily', 'discharge_summary', %s)",
            (user, dis, name, rdate),
        )


async def test_health_record_reads(db: Database, owner_conn) -> None:
    user, other = new_user(owner_conn), new_user(owner_conn)
    _seed_record(owner_conn, user)
    _seed_record(owner_conn, other)
    async with db.for_user(user) as s:
        index = await hr.report_index(s, user)
        assert [c.filename for c in index] == ["cbc.pdf", "dis.pdf", "old.pdf"]
        assert await hr.test_catalogue(s, user) == ["Haemoglobin", "Platelet count", "TSH"]
        snapshot = await hr.lab_snapshot(s, user)
        # latest row per test, abnormal only, newest report first
        assert [(f.test_name, f.value_text) for f in snapshot] == [
            ("Haemoglobin", "9.1"),
            ("TSH", "7.8"),
        ]
        values = await hr.lab_values(s, user, ["haemoglobin", "Ferritin"], include_abnormal=False)
        assert [(f.test_name, f.value_text) for f in values] == [
            ("Haemoglobin", "9.1"),
            ("Haemoglobin", "11.0"),
        ]
        assert values[0].report_date == "2026-09-01" and values[0].filename == "cbc.pdf"
        meds = await hr.medications(s, user)
        assert [m.name_raw for m in meds] == ["Telma 40"]
        assert await hr.conditions(s, user) == [
            "Chronic kidney disease stage 3",
            "Hypertension",
        ]


async def test_app_role_can_use_the_checkpointer(settings) -> None:
    """Migration 0003 created the tables as the owner; the app role never runs setup()."""
    from typing import TypedDict

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.graph import END, START, StateGraph

    class S(TypedDict):
        n: int

    g = StateGraph(S)
    g.add_node("inc", lambda s: {"n": s["n"] + 1})
    g.add_edge(START, "inc")
    g.add_edge("inc", END)
    url = settings.database_url  # etheria_app on etheria_test
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        graph = g.compile(checkpointer=saver)
        cfg = {"configurable": {"thread_id": str(uuid4())}}
        await graph.ainvoke({"n": 1}, cfg, durability="exit")
        assert (await graph.aget_state(cfg)).values == {"n": 2}
        await saver.adelete_thread(cfg["configurable"]["thread_id"])
        assert (await graph.aget_state(cfg)).values == {}
