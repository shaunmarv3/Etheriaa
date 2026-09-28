"""Phase 2: the Postgres reference tables (spec 6.2). Runs as the owner role:
the app role is read-only on these tables. Each load replaces the table in
one transaction, so a re-run gives the same rows and a failure leaves the
previous contents in place."""

from collections.abc import Iterable

import psycopg

from etheria.seed.sources import BrandRow

_BRAND_COLUMNS = (
    "name, manufacturer, type, pack_size_label, composition1, composition2, "
    "ingredients, is_discontinued"
)


def load_medicine_brands(owner_url: str, rows: Iterable[BrandRow]) -> int:
    with psycopg.connect(owner_url) as conn, conn.transaction():
        conn.execute("TRUNCATE medicine_brands RESTART IDENTITY")
        with conn.cursor().copy(f"COPY medicine_brands ({_BRAND_COLUMNS}) FROM STDIN") as copy:
            copy.set_types(["text"] * 6 + ["text[]", "bool"])
            for row in rows:
                copy.write_row(row)
        count = conn.execute("SELECT count(*) FROM medicine_brands").fetchone()
    return count[0] if count else 0


def load_drug_synonyms(owner_url: str, synonyms: dict[str, str]) -> int:
    with psycopg.connect(owner_url) as conn, conn.transaction():
        conn.execute("DELETE FROM drug_synonyms")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO drug_synonyms (alias, canonical) VALUES (%s, %s)",
                list(synonyms.items()),
            )
    return len(synonyms)
