import psycopg
import pytest
from conftest import OWNER_URL, TEST_DB, with_db

from etheria.seed.load_postgres import load_drug_synonyms, load_medicine_brands
from etheria.seed.sources import BrandRow

ROWS = [
    BrandRow(
        "Dolo 650 Tablet",
        "Micro Labs Ltd",
        "allopathy",
        "strip of 15 tablets",
        "Paracetamol (650mg)",
        None,
        ["paracetamol"],
        False,
    ),
    BrandRow(
        "Augmentin 625 Duo Tablet",
        "GSK",
        "allopathy",
        "strip of 10 tablets",
        "Amoxycillin (500mg)",
        "Clavulanic Acid (125mg)",
        ["amoxycillin", "clavulanic acid"],
        True,
    ),
]


@pytest.fixture
def owner_url(migrated_db: str) -> str:
    return with_db(OWNER_URL, TEST_DB)


def test_brands_load_with_arrays_and_reload_replaces(owner_url: str, owner_conn) -> None:
    assert load_medicine_brands(owner_url, ROWS) == 2
    assert load_medicine_brands(owner_url, ROWS) == 2  # idempotent: replaced, not appended
    rows = owner_conn.execute(
        "select name, ingredients, is_discontinued, composition2 from medicine_brands order by name"
    ).fetchall()
    assert rows == [
        (
            "Augmentin 625 Duo Tablet",
            ["amoxycillin", "clavulanic acid"],
            True,
            "Clavulanic Acid (125mg)",
        ),
        ("Dolo 650 Tablet", ["paracetamol"], False, None),
    ]


def test_synonyms_replace_the_table(owner_url: str, owner_conn) -> None:
    load_drug_synonyms(owner_url, {"paracetamol": "Acetaminophen", "frusemide": "Furosemide"})
    assert load_drug_synonyms(owner_url, {"Paracetamol": "Acetaminophen"}) == 1
    assert owner_conn.execute("select alias::text, canonical from drug_synonyms").fetchall() == [
        ("Paracetamol", "Acetaminophen")
    ]
    # citext: lookups are case-insensitive
    assert owner_conn.execute(
        "select canonical from drug_synonyms where alias = 'PARACETAMOL'"
    ).fetchone() == ("Acetaminophen",)


def test_app_role_still_cannot_write_reference_tables(app_conn) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("insert into drug_synonyms values ('x', 'y')")
