"""The upload endpoints (spec 5.1, 5.2, 10). Temporal is replaced by a fake
client that records start_workflow calls; the workflow itself is covered in
test_ingest_workflow.py."""

import io
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pymupdf
import pytest
from fastapi import FastAPI
from ingestion_fakes import REPORTS
from PIL import Image

from etheria.core.settings import Settings
from etheria.ingestion.validation import MAX_BYTES, MAX_PAGES

PDF = (REPORTS / "lab_cbc.pdf").read_bytes()


class FakeTemporal:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.started: list[dict] = []

    async def start_workflow(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("temporal unreachable")
        self.started.append(kwargs)


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    return settings.model_copy(update={"upload_dir": tmp_path / "uploads"})


@pytest.fixture
def temporal(app: FastAPI, api_client: httpx.AsyncClient) -> FakeTemporal:
    fake = FakeTemporal()
    app.state.temporal = fake
    return fake


async def auth(client: httpx.AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": f"u{uuid4().hex[:12]}@example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def post(client, headers, data: bytes = PDF, name: str = "cbc.pdf"):
    return await client.post("/upload/", headers=headers, files={"file": (name, data, "x/y")})


def stored_files(settings: Settings) -> list[Path]:
    root = settings.upload_dir
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


def pdf_pages(n: int) -> bytes:
    doc = pymupdf.open()
    for _ in range(n):
        doc.new_page().insert_text((72, 72), "page")
    return doc.tobytes()


async def test_upload_pdf_returns_pending_and_starts_workflow(
    api_client, temporal: FakeTemporal, owner_conn: psycopg.Connection
):
    h = await auth(api_client)
    r = await post(api_client, h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"document_id", "filename", "status", "page_count"}
    assert (body["filename"], body["status"], body["page_count"]) == ("cbc.pdf", "pending", 1)
    (call,) = temporal.started
    assert call["id"] == f"ingest-{body['document_id']}" and call["task_queue"] == "ingestion"
    actions = owner_conn.execute(
        "select action from audit_log where resource_id = %s", (body["document_id"],)
    ).fetchall()
    assert actions == [("upload",)]


async def test_file_on_disk_is_encrypted(api_client, temporal, settings: Settings):
    await post(api_client, await auth(api_client))
    (path,) = stored_files(settings)
    blob = path.read_bytes()
    assert b"%PDF" not in blob and b"Haemoglobin" not in blob


async def test_duplicate_upload_returns_existing(api_client, temporal: FakeTemporal):
    h = await auth(api_client)
    first = (await post(api_client, h)).json()
    again = await post(api_client, h, name="renamed.pdf")
    assert again.status_code == 200
    assert again.json()["document_id"] == first["document_id"]
    assert len(temporal.started) == 1


async def test_concurrent_same_file_upload_returns_the_winner(
    api_client, temporal: FakeTemporal, settings: Settings, monkeypatch
):
    """Two uploads of one file race past the duplicate check; the loser hits the
    unique (user_id, sha256) index and must answer like a duplicate, not 500."""
    from etheria.api.routers import upload as router

    h = await auth(api_client)
    first = (await post(api_client, h)).json()

    real, calls = router.repo.get_by_sha, []

    async def first_check_misses(*args, **kwargs):
        calls.append(1)
        return None if len(calls) == 1 else await real(*args, **kwargs)

    monkeypatch.setattr(router.repo, "get_by_sha", first_check_misses)
    loser = await post(api_client, h)
    assert loser.status_code == 200, loser.text
    assert loser.json()["document_id"] == first["document_id"]
    assert len(stored_files(settings)) == 1
    assert len(temporal.started) == 1


async def test_same_file_other_user_gets_own_document(api_client, temporal: FakeTemporal):
    a = (await post(api_client, await auth(api_client))).json()
    b = (await post(api_client, await auth(api_client))).json()
    assert a["document_id"] != b["document_id"]
    assert len(temporal.started) == 2


@pytest.mark.parametrize(
    "data,status,code",
    [
        (b"PK\x03\x04" + b"\x00" * 64, 415, "unsupported_type"),
        (pdf_pages(MAX_PAGES + 1), 400, "too_many_pages"),
        (b"%PDF-" + b"0" * MAX_BYTES, 413, "file_too_large"),
        (b"", 400, "empty_file"),
    ],
    ids=["zip", "31_pages", "over_10mb", "empty"],
)
async def test_upload_rejections_write_nothing(
    api_client, temporal: FakeTemporal, settings: Settings, data: bytes, status: int, code: str
):
    h = await auth(api_client)
    r = await post(api_client, h, data)
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert stored_files(settings) == []
    assert temporal.started == []
    assert (await api_client.get("/upload/", headers=h)).json() == {"documents": []}


async def test_encrypted_pdf_rejected(api_client, temporal):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    r = await post(api_client, await auth(api_client), data)
    assert (r.status_code, r.json()["error"]["code"]) == (400, "encrypted_pdf")


async def test_png_named_pdf_is_accepted_as_image(api_client, temporal):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, format="PNG")
    h = await auth(api_client)
    r = await post(api_client, h, buf.getvalue(), "scan.pdf")
    assert r.status_code == 201
    (doc,) = (await api_client.get("/upload/", headers=h)).json()["documents"]
    assert doc["file_type"] == "image"


async def test_upload_rate_limited_after_10(api_client, temporal):
    h = await auth(api_client)
    for _ in range(10):
        assert (await post(api_client, h)).status_code in (200, 201)
    r = await post(api_client, h)
    assert (r.status_code, r.json()["error"]["code"]) == (429, "rate_limited")


async def test_temporal_down_rolls_back(api_client, temporal: FakeTemporal, settings: Settings):
    temporal.fail = True
    h = await auth(api_client)
    r = await post(api_client, h)
    assert (r.status_code, r.json()["error"]["code"]) == (503, "ingestion_unavailable")
    assert stored_files(settings) == []
    assert (await api_client.get("/upload/", headers=h)).json() == {"documents": []}


async def test_list_shape(api_client, temporal):
    h = await auth(api_client)
    doc_id = (await post(api_client, h)).json()["document_id"]
    (doc,) = (await api_client.get("/upload/", headers=h)).json()["documents"]
    assert set(doc) == {
        "document_id",
        "filename",
        "file_type",
        "status",
        "page_count",
        "uploaded_at",
        "doc_type",
        "summary",
        "report_date",
    }
    assert (doc["document_id"], doc["file_type"], doc["status"]) == (doc_id, "pdf", "pending")


async def test_download_roundtrip(api_client, temporal, owner_conn: psycopg.Connection):
    h = await auth(api_client)
    doc_id = (await post(api_client, h)).json()["document_id"]
    r = await api_client.get(f"/upload/{doc_id}/download", headers=h)
    assert r.status_code == 200
    assert r.content == PDF
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert "cbc.pdf" in r.headers["content-disposition"]
    actions = {
        a
        for (a,) in owner_conn.execute(
            "select action from audit_log where resource_id = %s", (doc_id,)
        )
    }
    assert "download" in actions


async def test_delete_removes_rows_and_file(api_client, temporal, settings: Settings):
    h = await auth(api_client)
    doc_id = (await post(api_client, h)).json()["document_id"]
    assert len(stored_files(settings)) == 1
    r = await api_client.delete(f"/upload/{doc_id}", headers=h)
    assert r.status_code == 204
    assert stored_files(settings) == []
    assert (await api_client.get("/upload/", headers=h)).json() == {"documents": []}
    assert (await api_client.delete(f"/upload/{doc_id}", headers=h)).status_code == 404


async def test_cross_user_document_is_404(api_client, temporal, settings: Settings):
    owner, other = await auth(api_client), await auth(api_client)
    doc_id = (await post(api_client, owner)).json()["document_id"]
    for method, url in (("GET", f"/upload/{doc_id}/download"), ("DELETE", f"/upload/{doc_id}")):
        r = await api_client.request(method, url, headers=other)
        assert (r.status_code, r.json()["error"]["code"]) == (404, "not_found")
    assert len(stored_files(settings)) == 1
    assert (await api_client.get("/upload/", headers=other)).json() == {"documents": []}


async def test_bad_document_id_is_404(api_client, temporal):
    h = await auth(api_client)
    r = await api_client.get("/upload/not-a-uuid/download", headers=h)
    assert r.status_code in (404, 422)


async def test_upload_requires_auth(api_client, temporal):
    r = await api_client.post("/upload/", files={"file": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 401
