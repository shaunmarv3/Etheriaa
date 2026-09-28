"""Phase 1: download the seed sources and verify them (spec 6.4).

The DDInter server is slow (one file took 16 minutes on 2026-09-28) but honours
HTTP Range, so an interrupted download resumes where it stopped. A file is
used only after its SHA-256 matches the manifest; a mismatch deletes it."""

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog
import yaml

log = structlog.get_logger(__name__)
MANIFEST = Path(__file__).with_name("manifest.yaml")


class ChecksumMismatch(Exception):
    pass


@dataclass(frozen=True)
class SourceFile:
    name: str
    url: str
    sha256: str
    size: int


def load_manifest(path: Path = MANIFEST) -> list[SourceFile]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [SourceFile(**f) for f in data["files"]]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(1 << 20):
            h.update(block)
    return h.hexdigest()


async def _fetch_from(http: httpx.AsyncClient, f: SourceFile, path: Path) -> None:
    """Append the missing bytes to `path` (or rewrite it if the server ignores Range)."""
    have = path.stat().st_size if path.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    async with http.stream("GET", f.url, headers=headers, timeout=httpx.Timeout(60.0)) as resp:
        if resp.status_code == 416:
            return  # nothing left to send: the checksum decides
        if resp.status_code not in (200, 206):
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code} for {f.url}", request=resp.request, response=resp
            )
        mode = "ab" if resp.status_code == 206 else "wb"
        with path.open(mode) as out:
            # No chunk_size: a sized chunker buffers, and a dropped connection
            # would lose the buffered bytes instead of leaving them to resume from.
            async for chunk in resp.aiter_bytes():
                out.write(chunk)


async def ensure_file(
    http: httpx.AsyncClient,
    f: SourceFile,
    dest_dir: Path,
    *,
    attempts: int = 6,
    retry_delay_s: float = 5.0,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f.name
    if path.exists() and path.stat().st_size > f.size:
        path.unlink()  # longer than expected: not a prefix of the right file
    for attempt in range(1, attempts + 1):
        if path.exists() and path.stat().st_size == f.size:
            break
        try:
            await _fetch_from(http, f, path)
        except httpx.HTTPError as e:
            if attempt == attempts:
                raise
            log.warning("download_retry", file=f.name, attempt=attempt, error=type(e).__name__)
            await asyncio.sleep(retry_delay_s)
    actual = sha256_of(path)
    if actual != f.sha256:
        path.unlink()
        raise ChecksumMismatch(f"{f.name}: sha256 {actual} != manifest {f.sha256}")
    return path
