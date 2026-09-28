"""Reads of the user's own record for the chat graph (spec 4.3 load_context,
4.5 tools): report cards, the test catalogue, the abnormal lab snapshot, lab
values by test name, medications and discharge diagnoses.

Only documents that finished processing count. Every query filters by user
as well as running under RLS."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SNAPSHOT_LIMIT = 30
VALUES_LIMIT = 60


class ReportCard(BaseModel):
    document_id: str
    filename: str
    doc_type: str | None
    report_date: str | None
    lab_name: str | None
    summary: str | None


class LabFact(BaseModel):
    id: str
    document_id: str
    filename: str
    test_name: str
    value_text: str
    unit: str | None
    ref_range_text: str | None
    flag: str
    report_date: str | None
    page: int | None


class MedFact(BaseModel):
    id: str
    document_id: str | None
    name_raw: str
    dose: str | None
    frequency: str | None
    duration: str | None
    source: str
    report_date: str | None


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


_LAB_COLUMNS = (
    "l.id, l.document_id, d.filename, l.test_name, l.value_text, l.unit, l.ref_range_text, "
    "l.flag, l.report_date, l.page"
)


def _lab(row: Any) -> LabFact:
    return LabFact(
        id=str(row.id),
        document_id=str(row.document_id),
        filename=row.filename,
        test_name=row.test_name,
        value_text=row.value_text,
        unit=row.unit,
        ref_range_text=row.ref_range_text,
        flag=row.flag,
        report_date=_iso(row.report_date),
        page=row.page,
    )


async def report_index(s: AsyncSession, user_id: UUID) -> list[ReportCard]:
    rows = await s.execute(
        text(
            "SELECT id, filename, doc_type, report_date, lab_name, summary FROM documents "
            "WHERE user_id = :u AND status = 'done' "
            "ORDER BY report_date DESC NULLS LAST, uploaded_at DESC"
        ),
        {"u": user_id},
    )
    return [
        ReportCard(
            document_id=str(r.id),
            filename=r.filename,
            doc_type=r.doc_type,
            report_date=_iso(r.report_date),
            lab_name=r.lab_name,
            summary=r.summary,
        )
        for r in rows
    ]


async def _latest_per_test(s: AsyncSession, user_id: UUID) -> list[LabFact]:
    rows = await s.execute(
        text(
            f"SELECT DISTINCT ON (lower(l.test_name)) {_LAB_COLUMNS} "
            "FROM lab_results l JOIN documents d ON d.id = l.document_id "
            "WHERE l.user_id = :u "
            "ORDER BY lower(l.test_name), l.report_date DESC NULLS LAST, d.uploaded_at DESC"
        ),
        {"u": user_id},
    )
    return [_lab(r) for r in rows]


async def test_catalogue(s: AsyncSession, user_id: UUID) -> list[str]:
    """The user's distinct test names (latest spelling), for validating requests."""
    return sorted((f.test_name for f in await _latest_per_test(s, user_id)), key=str.lower)


async def lab_snapshot(
    s: AsyncSession, user_id: UUID, limit: int = SNAPSHOT_LIMIT
) -> list[LabFact]:
    """The latest value of every test, abnormal ones only, newest report first."""
    abnormal = [f for f in await _latest_per_test(s, user_id) if f.flag in ("high", "low")]
    abnormal.sort(key=lambda f: f.test_name.lower())
    abnormal.sort(key=lambda f: f.report_date or "", reverse=True)  # stable: names stay sorted
    return abnormal[:limit]


async def lab_values(
    s: AsyncSession, user_id: UUID, test_names: list[str], include_abnormal: bool
) -> list[LabFact]:
    """Every stored value of the named tests (all reports, newest first), plus the
    abnormal snapshot when asked."""
    rows = await s.execute(
        text(
            f"SELECT {_LAB_COLUMNS} FROM lab_results l JOIN documents d ON d.id = l.document_id "
            "WHERE l.user_id = :u AND lower(l.test_name) = ANY(:names) "
            "ORDER BY l.report_date DESC NULLS LAST, d.uploaded_at DESC, l.test_name "
            "LIMIT :lim"
        ),
        {"u": user_id, "names": [n.lower() for n in test_names], "lim": VALUES_LIMIT},
    )
    facts = [_lab(r) for r in rows]
    if include_abnormal:
        seen = {f.id for f in facts}
        facts += [f for f in await lab_snapshot(s, user_id) if f.id not in seen]
    return facts


async def medications(s: AsyncSession, user_id: UUID) -> list[MedFact]:
    """One row per medicine name (the latest mention), newest first."""
    rows = await s.execute(
        text(
            "SELECT * FROM ("
            "  SELECT DISTINCT ON (lower(name_raw)) id, document_id, name_raw, dose, frequency, "
            "  duration, source, report_date FROM medications WHERE user_id = :u "
            "  ORDER BY lower(name_raw), report_date DESC NULLS LAST"
            ") m ORDER BY report_date DESC NULLS LAST, name_raw"
        ),
        {"u": user_id},
    )
    return [
        MedFact(
            id=str(r.id),
            document_id=str(r.document_id) if r.document_id else None,
            name_raw=r.name_raw,
            dose=r.dose,
            frequency=r.frequency,
            duration=r.duration,
            source=r.source,
            report_date=_iso(r.report_date),
        )
        for r in rows
    ]


async def conditions(s: AsyncSession, user_id: UUID) -> list[str]:
    """Diagnoses from the user's discharge summaries (display-only JSONB, spec 5.5)."""
    rows = await s.execute(
        text(
            "SELECT dx FROM documents d, "
            "LATERAL jsonb_array_elements_text(coalesce(d.extracted->'diagnoses', '[]')) "
            "WITH ORDINALITY AS t(dx, n) "
            "WHERE d.user_id = :u AND d.status = 'done' AND d.doc_type = 'discharge_summary' "
            "ORDER BY d.report_date DESC NULLS LAST, n"
        ),
        {"u": user_id},
    )
    out: list[str] = []
    for (dx,) in rows:
        if dx not in out:
            out.append(dx)
    return out
