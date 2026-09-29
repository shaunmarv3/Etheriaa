"""Upload fuzzing (spec 11.1 "malicious upload"): seeded random mutations of the
real fixtures. Validation must either accept a file or reject it with a known
code; it must never crash, and the endpoint must never answer 500."""

import random
from pathlib import Path

import httpx
import pytest
from ingestion_fakes import REPORTS

from etheria.core.settings import Settings
from etheria.ingestion.validation import UploadInfo, UploadRejected, inspect_upload

SEEDS = ["lab_cbc.pdf", "prescription.pdf", "lab_cbc_scan.png"]


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    return settings.model_copy(update={"upload_dir": tmp_path / "uploads"})


def mutations(data: bytes, rng: random.Random, n: int) -> list[bytes]:
    out = []
    for _ in range(n):
        b = bytearray(data)
        kind = rng.randrange(5)
        if kind == 0:  # flip random bytes
            for _ in range(rng.randint(1, 64)):
                b[rng.randrange(len(b))] = rng.randrange(256)
        elif kind == 1:  # truncate
            b = b[: rng.randrange(1, len(b))]
        elif kind == 2:  # splice a random block in
            at = rng.randrange(len(b))
            b[at:at] = rng.randbytes(rng.randint(1, 4096))
        elif kind == 3:  # keep the magic bytes, randomise the rest
            b = b[:8] + bytearray(rng.randbytes(rng.randint(1, 20_000)))
        else:  # duplicate a slice (repeated objects, broken xref offsets)
            i, j = sorted(rng.sample(range(len(b)), 2))
            b = b[:j] + b[i:j] + b[j:]
        out.append(bytes(b))
    return out


@pytest.mark.parametrize("seed_file", SEEDS)
def test_mutated_files_are_accepted_or_rejected_never_crash(seed_file: str) -> None:
    rng = random.Random(f"m7-{seed_file}")
    outcomes = {"accepted": 0, "rejected": 0}
    for blob in mutations((REPORTS / seed_file).read_bytes(), rng, 150):
        try:
            assert isinstance(inspect_upload(blob, seed_file), UploadInfo)
            outcomes["accepted"] += 1
        except UploadRejected:
            outcomes["rejected"] += 1
    assert outcomes["rejected"] > 0, outcomes


async def test_mutated_uploads_never_answer_500(api_client: httpx.AsyncClient, app) -> None:
    class FakeTemporal:
        async def start_workflow(self, *args, **kwargs):
            return None

    app.state.temporal = FakeTemporal()
    r = await api_client.post(
        "/auth/register",
        json={"email": f"fuzz{random.randrange(10**9)}@example.com", "password": "correct horse 9"},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    rng = random.Random("m7-api")
    blobs = mutations((REPORTS / "lab_cbc.pdf").read_bytes(), rng, 9)  # 10 uploads/hour limit
    statuses = []
    for i, blob in enumerate(blobs):
        r = await api_client.post(
            "/upload/", headers=headers, files={"file": (f"f{i}.pdf", blob, "application/pdf")}
        )
        statuses.append(r.status_code)
        assert r.status_code < 500, (i, r.text)
    assert set(statuses) <= {200, 201, 400, 413, 415}, statuses
