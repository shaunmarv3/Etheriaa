"""`uv run etheria seed`: the eight phases of spec 6.4, each reported on one
line. A failing phase stops the run (later phases depend on it) and the exit
code is non-zero, as it is when any canary fails. Nothing is swallowed: a
phase error is printed with its type and message."""

import time
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

import typer
from redis.asyncio import Redis

from etheria.cache.json_cache import JsonCache
from etheria.core.settings import BACKEND_DIR, Settings
from etheria.db.session import Database
from etheria.knowledge.neo4j import create_driver
from etheria.knowledge.resolver import MedicineResolver
from etheria.knowledge.schema import apply_schema
from etheria.medical_apis.base import create_http_client
from etheria.medical_apis.bioportal import BioPortal
from etheria.medical_apis.icd10 import Icd10
from etheria.medical_apis.rxnav import RxNav
from etheria.seed.codes import enrich_codes
from etheria.seed.curated import load_curated, validate_curated
from etheria.seed.download import ensure_file, load_manifest
from etheria.seed.load_neo4j import load_curated as load_curated_graph
from etheria.seed.load_neo4j import load_drugs, load_extra_drugs, load_interactions
from etheria.seed.load_postgres import load_drug_synonyms, load_medicine_brands
from etheria.seed.sources import read_ddinter, read_medicines
from etheria.seed.verify import (
    graph_counts,
    postgres_counts,
    render_section,
    run_canaries,
    write_numbers,
)

NUMBERS = BACKEND_DIR.parent / "docs" / "NUMBERS.md"


class PhaseFailed(Exception):
    pass


async def _phase(n: int, name: str, fn: Callable[[], Awaitable[str]]) -> None:
    start = time.monotonic()
    try:
        detail = await fn()
    except Exception as e:  # reported and re-raised as a stop, never swallowed
        typer.echo(
            f"phase {n} {name}: FAILED ({type(e).__name__}: {e}) {time.monotonic() - start:.1f}s"
        )
        raise PhaseFailed(name) from e
    typer.echo(f"phase {n} {name}: ok ({detail}) {time.monotonic() - start:.1f}s")


async def run_seed(
    settings: Settings, *, skip_codes: bool = False, verify_only: bool = False
) -> int:
    driver = create_driver(settings)
    redis = Redis.from_url(settings.redis_url)
    db = Database(settings.sqlalchemy_url)
    http = create_http_client()
    state: dict[str, Any] = {}
    try:
        if not verify_only:
            await _load(settings, driver, http, JsonCache(redis), state, skip_codes)
        return await _verify(settings, driver, db)
    except PhaseFailed:
        return 1
    finally:
        await http.aclose()
        await db.dispose()
        await redis.aclose()
        await driver.close()


async def _load(settings, driver, http, cache, state, skip_codes) -> None:  # noqa: ANN001
    seed_dir: Path = settings.seed_dir
    files = load_manifest()

    async def download() -> str:
        for f in files:
            await ensure_file(http, f, seed_dir)
        ddinter = read_ddinter([seed_dir / f.name for f in files if f.name.startswith("ddinter")])
        curated = load_curated()
        problems = validate_curated(curated, set(ddinter.drugs.values()))
        if problems:
            raise ValueError(f"curated data: {len(problems)} problems, first: {problems[0]}")
        state.update(ddinter=ddinter, curated=curated)
        return f"{len(files)} files verified; curated data consistent"

    async def postgres() -> str:
        brands = load_medicine_brands(
            settings.database_owner_url, read_medicines(seed_dir / "indian_medicine_data.csv")
        )
        synonyms = load_drug_synonyms(settings.database_owner_url, state["curated"].synonyms)
        return f"{brands:,} brands, {synonyms} synonyms"

    async def schema() -> str:
        await apply_schema(driver)
        return "constraints and full-text indexes"

    async def drugs() -> str:
        n = await load_drugs(driver, state["ddinter"].drugs)
        extra = await load_extra_drugs(driver, state["curated"].extra_drugs)
        return f"{n:,} DDInter drugs, {extra} curated extra drugs"

    async def interactions() -> str:
        pairs = state["ddinter"].pairs
        created = await load_interactions(driver, pairs)
        if created != len(pairs):
            raise ValueError(f"{created:,} of {len(pairs):,} pairs matched their drugs")
        return f"{created:,} DDInter pairs"

    async def curated() -> str:
        c = await load_curated_graph(driver, state["curated"])
        if c.members_created != c.members_expected or c.critical_created != c.critical_expected:
            raise ValueError(
                f"members {c.members_created}/{c.members_expected}, "
                f"critical {c.critical_created}/{c.critical_expected}"
            )
        return (
            f"{c.conditions} conditions, {c.symptoms} symptoms, {c.drug_classes} classes, "
            f"{c.associated_with} symptom edges, {c.critical_created} critical edges"
        )

    async def codes() -> str:
        if skip_codes:
            return "skipped (--skip-codes)"
        key = settings.bioportal_api_key
        report = await enrich_codes(
            driver,
            Icd10(http, cache),
            BioPortal(http, cache, key.get_secret_value()) if key else None,
            RxNav(http, cache),
        )
        if report.failed or report.icd10_unknown:
            raise ValueError(
                f"{len(report.failed)} API failures, unknown ICD-10 {report.icd10_unknown}; "
                f"first failure: {report.failed[:1]}"
            )
        return (
            f"ICD-10 {report.icd10_verified} verified, SNOMED {report.snomed_filled} "
            f"filled / {report.snomed_missing} no exact match"
            f"{' (skipped: no BIOPORTAL_API_KEY)' if report.snomed_skipped else ''}, "
            f"RxCUI {report.rxcui_filled} / {report.rxcui_missing} missing, "
            f"cache hits {cache.hits}"
        )

    await _phase(1, "download", download)
    await _phase(2, "postgres", postgres)
    await _phase(3, "neo4j schema", schema)
    await _phase(4, "drugs", drugs)
    await _phase(5, "interactions", interactions)
    await _phase(6, "curated domain", curated)
    await _phase(7, "codes", codes)


async def _verify(settings: Settings, driver, db: Database) -> int:  # noqa: ANN001
    result: dict[str, Any] = {}

    async def verify() -> str:
        counts = {
            "Neo4j": await graph_counts(driver),
            "Postgres": await postgres_counts(settings.database_owner_url, driver),
        }
        canaries = await run_canaries(driver, MedicineResolver(db, driver))
        write_numbers(
            NUMBERS, render_section(counts, canaries, measured_on=date.today().isoformat())
        )
        result["canaries"] = canaries
        passed = sum(c.passed for c in canaries)
        return f"canaries {passed}/{len(canaries)}; wrote docs/NUMBERS.md"

    await _phase(8, "verify", verify)
    failed = [c for c in result["canaries"] if not c.passed]
    for c in failed:
        typer.echo(f"CANARY FAILED: {c.name} -> {c.detail}")
    return 1 if failed else 0
