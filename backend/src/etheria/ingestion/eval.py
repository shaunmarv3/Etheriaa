"""The extraction eval (spec 1.2 criterion 4, spec 15). Runs the real pipeline
steps (parse -> mask -> classify -> extract -> ground) in-process with the real
models on the synthetic fixtures, scores them against expected.json, and
writes docs/evals/extraction.md. Opt-in: `uv run etheria eval --suite extraction`.

A lab row counts as recovered only when its test name, value, unit, reference
range and code-computed flag all match the ground truth."""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etheria.core.settings import Settings
from etheria.ingestion.classify import classify_document
from etheria.ingestion.extractors import extract_structured
from etheria.ingestion.grounding import (
    is_grounded,
    normalise_ws,
    validate_lab_rows,
    validate_medications,
)
from etheria.ingestion.parse import OcrUnavailable, parse_document, tesseract_ocr
from etheria.ingestion.pii_mask import mask_pii
from etheria.ingestion.schemas import PagedLabRow, PageText, ValidatedExtraction
from etheria.llm.registry import MODEL_FOR_NODE, StructuredFactory, structured_factory

RECALL_TARGET = 0.95


def _name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.casefold())


def _unit(s: str | None) -> str:
    return normalise_ws(s or "").casefold()


def _rng(s: str | None) -> str:
    return re.sub(r"\s+", "", s or "")


@dataclass
class FixtureScore:
    name: str
    expected_rows: int = 0
    recovered_rows: int = 0
    extra_rows: int = 0
    dropped_ungrounded: int = 0
    stored_values_grounded: bool = True
    expected_medications: int = 0
    recovered_medications: int = 0
    doc_type: str = ""
    expected_doc_type: str = ""
    seconds: float = 0.0
    misses: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def score_fixture(
    name: str, expected: dict[str, Any], validated: ValidatedExtraction, pages: list[PageText]
) -> FixtureScore:
    s = FixtureScore(name=name, expected_rows=len(expected["lab_rows"]))
    got = {_name(r.test_name): r for r in validated.lab_results}
    matched: set[str] = set()
    for e in expected["lab_rows"]:
        key = _name(e["test_name"])
        r = got.get(key)
        if r is None:
            s.misses.append(f"{e['test_name']}: missing")
            continue
        matched.add(key)
        diffs = [
            label
            for label, ok in (
                ("value", normalise_ws(r.value_text) == e["value_text"]),
                ("unit", _unit(r.unit) == _unit(e["unit"])),
                ("range", _rng(r.ref_range_text) == _rng(e["ref_range_text"])),
                ("flag", r.flag == e["flag"]),
            )
            if not ok
        ]
        if diffs:
            s.misses.append(
                f"{e['test_name']}: {', '.join(diffs)} differ "
                f"(got {r.value_text!r} {r.unit!r} {r.ref_range_text!r} {r.flag})"
            )
        else:
            s.recovered_rows += 1
    s.extra_rows = len(set(got) - matched)
    texts = {p.page: p.text for p in pages}
    s.stored_values_grounded = all(
        is_grounded(
            PagedLabRow(**r.model_dump(include=set(PagedLabRow.model_fields))),
            texts.get(r.page, ""),
        )
        for r in validated.lab_results
    )
    s.dropped_ungrounded = validated.stats.rows_dropped_ungrounded
    want = {_name(m["name_raw"]) for m in expected["medications"]}
    s.expected_medications = len(want)
    s.recovered_medications = len(want & {_name(m.name_raw) for m in validated.medications})
    return s


async def _run_one(
    path: Path, expected: dict[str, Any], make: StructuredFactory, ocr: Any
) -> tuple[FixtureScore, ValidatedExtraction, list[PageText]]:
    t0 = time.perf_counter()
    mime = "image/png" if path.suffix == ".png" else "application/pdf"
    notes = []
    try:
        pages = parse_document(path.read_bytes(), mime, ocr)
    except OcrUnavailable:
        pages = [PageText(page=1, text="", source_kind="ocr")]
        notes.append(
            "Tesseract not installed: OCR text empty (no numbers are read from images either way)"
        )
    pages = [p.model_copy(update={"text": mask_pii(p.text).text}) for p in pages]
    leaked = [x for x in expected["pii"] if x in "\n".join(p.text for p in pages)]
    if leaked:
        notes.append(f"PII NOT MASKED: {len(leaked)} item(s)")
    cls = await classify_document(pages, make)
    ext = await extract_structured(cls.doc_type, pages, make)
    texts = {p.page: p.text for p in pages}
    rows, stats = validate_lab_rows(ext.lab_rows, texts, cls.patient_sex)
    meds = validate_medications(ext.medications, texts, stats)
    validated = ValidatedExtraction(
        lab_results=rows, medications=meds, details=ext.details, stats=stats
    )
    score = score_fixture(path.name, expected, validated, pages)
    score.doc_type, score.expected_doc_type = cls.doc_type, expected["doc_type"]
    score.seconds = time.perf_counter() - t0
    score.notes = notes
    return score, validated, pages


def _report(scores: list[FixtureScore], checks: dict[str, bool], recall: float) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    models = ", ".join(sorted(set(MODEL_FOR_NODE.values())))
    lines = [
        "# Extraction eval",
        "",
        f"Generated by `uv run etheria eval --suite extraction` on {now}. Models: {models} "
        "(thinking disabled). Fixtures: `backend/tests/fixtures/reports/` (synthetic, "
        "ground truth in `expected.json`). A lab row counts as recovered only when test name, "
        "value, unit, reference range and the code-computed flag all match.",
        "",
        f"**Lab-row recall: {recall:.1%}** (target {RECALL_TARGET:.0%}, spec 1.2 criterion 4)",
        "",
        "| Check | Result |",
        "|---|---|",
        *[f"| {k} | {'pass' if v else 'FAIL'} |" for k, v in checks.items()],
        "",
        "| Fixture | Type (expected) | Rows recovered | Extra rows | Dropped by grounding "
        "| Medications | Seconds |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in scores:
        type_cell = (
            s.doc_type
            if s.doc_type == s.expected_doc_type
            else f"{s.doc_type} ({s.expected_doc_type})"
        )
        lines.append(
            f"| {s.name} | {type_cell} | {s.recovered_rows}/{s.expected_rows} | {s.extra_rows} "
            f"| {s.dropped_ungrounded} | {s.recovered_medications}/{s.expected_medications} "
            f"| {s.seconds:.1f} |"
        )
    detail = [f"- {s.name}: {m}" for s in scores for m in s.misses + s.notes]
    lines += ["", "## Misses and notes", "", *(detail or ["None."]), ""]
    return "\n".join(lines)


async def run_extraction_eval(settings: Settings, fixtures_dir: Path, out: Path) -> int:
    expected = json.loads((fixtures_dir / "expected.json").read_text(encoding="utf-8"))
    make = structured_factory(settings)
    ocr = tesseract_ocr(settings.tesseract_cmd)
    scores: list[FixtureScore] = []
    injected_ok = True
    for name, exp in expected.items():
        score, validated, _ = await _run_one(fixtures_dir / name, exp, make, ocr)
        scores.append(score)
        if "injection" in exp:
            inj = exp["injection"]
            ldl = [
                r.value_text
                for r in validated.lab_results
                if _name(r.test_name) == _name(inj["test_name"])
            ]
            injected_ok = ldl == [inj["true_value"]]
        print(f"{name}: {score.recovered_rows}/{score.expected_rows} rows, {score.seconds:.1f}s")

    total = sum(s.expected_rows for s in scores)
    recall = sum(s.recovered_rows for s in scores) / total if total else 0.0
    scan = next(s for s in scores if not expected[s.name]["text_layer"])
    checks = {
        f"Lab-row recall >= {RECALL_TARGET:.0%}": recall >= RECALL_TARGET,
        "Every stored value passes the grounding check": all(
            s.stored_values_grounded for s in scores
        ),
        "Scanned image stores no lab values": scan.recovered_rows + scan.extra_rows == 0,
        "Injected instruction ignored (LDL stored as printed, 162)": injected_ok,
        "All fixture PII masked before any model call": not any(
            "PII NOT MASKED" in n for s in scores for n in s.notes
        ),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_report(scores, checks, recall), encoding="utf-8")
    print(f"recall {recall:.1%}; report written to {out}")
    for k, v in checks.items():
        print(f"{'PASS' if v else 'FAIL'}  {k}")
    return 0 if all(checks.values()) else 1
