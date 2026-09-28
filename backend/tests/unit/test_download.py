import hashlib
from pathlib import Path

import httpx
import pytest

from etheria.seed.download import ChecksumMismatch, SourceFile, ensure_file, load_manifest

BODY = b"DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n" + b"x" * 5000


def source(body: bytes = BODY) -> SourceFile:
    return SourceFile(
        name="f.csv",
        url="https://example.test/f.csv",
        sha256=hashlib.sha256(body).hexdigest(),
        size=len(body),
    )


class Server:
    """Serves BODY, honouring Range unless told not to; can drop the connection once."""

    def __init__(self, body: bytes = BODY, *, honour_range: bool = True, cut_at: int | None = None):
        self.body = body
        self.honour_range = honour_range
        self.cut_at = cut_at
        self.requests: list[httpx.Request] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        rng = req.headers.get("Range")
        if rng and self.honour_range:
            start = int(rng.removeprefix("bytes=").rstrip("-"))
            if start >= len(self.body):
                return httpx.Response(416)
            return httpx.Response(206, content=self.body[start:])
        if self.cut_at is not None:
            cut, self.cut_at = self.cut_at, None

            async def partial():
                yield self.body[:cut]
                raise httpx.ReadError("connection reset")

            return httpx.Response(200, content=partial())
        return httpx.Response(200, content=self.body)


def http(server: Server) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(server))


async def test_fresh_download_is_verified(tmp_path: Path) -> None:
    server = Server()
    path = await ensure_file(http(server), source(), tmp_path)
    assert path.read_bytes() == BODY
    assert "Range" not in server.requests[0].headers


async def test_complete_file_makes_no_request(tmp_path: Path) -> None:
    (tmp_path / "f.csv").write_bytes(BODY)
    server = Server()
    await ensure_file(http(server), source(), tmp_path)
    assert server.requests == []


async def test_partial_file_resumes_with_range(tmp_path: Path) -> None:
    (tmp_path / "f.csv").write_bytes(BODY[:1000])
    server = Server()
    path = await ensure_file(http(server), source(), tmp_path)
    assert server.requests[0].headers["Range"] == "bytes=1000-"
    assert path.read_bytes() == BODY


async def test_dropped_connection_is_retried_from_where_it_stopped(tmp_path: Path) -> None:
    server = Server(cut_at=2000)
    path = await ensure_file(http(server), source(), tmp_path, retry_delay_s=0)
    assert path.read_bytes() == BODY
    assert server.requests[1].headers["Range"] == "bytes=2000-"


async def test_server_ignoring_range_restarts_cleanly(tmp_path: Path) -> None:
    (tmp_path / "f.csv").write_bytes(BODY[:1000])
    path = await ensure_file(http(Server(honour_range=False)), source(), tmp_path)
    assert path.read_bytes() == BODY


async def test_checksum_mismatch_raises_and_deletes(tmp_path: Path) -> None:
    tampered = BODY[:-1] + b"y"
    with pytest.raises(ChecksumMismatch):
        await ensure_file(http(Server(tampered)), source(), tmp_path)
    assert not (tmp_path / "f.csv").exists()


async def test_gives_up_after_the_attempts(tmp_path: Path) -> None:
    def down(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    client = httpx.AsyncClient(transport=httpx.MockTransport(down))
    with pytest.raises(httpx.ConnectError):
        await ensure_file(client, source(), tmp_path, attempts=2, retry_delay_s=0)


def test_committed_manifest_lists_the_nine_sources() -> None:
    files = load_manifest()
    assert len(files) == 9
    assert sum(f.name.startswith("ddinter_downloads_code_") for f in files) == 8
    assert all(len(f.sha256) == 64 and f.size > 0 and f.url.startswith("https://") for f in files)
