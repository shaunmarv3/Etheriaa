from pathlib import Path

import pytest

from etheria.knowledge.text import ingredient_candidates, normalise_name
from etheria.seed.sources import parse_ingredient, read_ddinter, read_medicines

HEADER = "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Dolo   650 ", "dolo 650"),
        ("WARFARIN", "warfarin"),
        ("Chorionic Gonadotropin (Human)", "chorionic gonadotropin (human)"),
        ("ﬂuconazole", "fluconazole"),  # NFKC folds the ligature
    ],
)
def test_normalise_name(raw: str, expected: str) -> None:
    assert normalise_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Amoxycillin  (500mg) ", "amoxycillin"),
        ("Atropine (1% w/v) ", "atropine"),
        ("Vitamin D3 (60000IU)", "vitamin d3"),
        ("  Clavulanic Acid (125mg)", "clavulanic acid"),
        ("Paracetamol", "paracetamol"),
        ("", None),
        ("   ", None),
        ("(5mg)", None),
    ],
)
def test_parse_ingredient(raw: str, expected: str | None) -> None:
    assert parse_ingredient(raw) == expected


@pytest.mark.parametrize(
    ("ingredient", "expected_first", "must_include"),
    [
        ("metoprolol succinate", "metoprolol succinate", "metoprolol"),
        ("escitalopram oxalate", "escitalopram oxalate", "escitalopram"),
        ("olmesartan medoxomil", "olmesartan medoxomil", "olmesartan"),
        ("salbutamol sulphate", "salbutamol sulfate", "salbutamol"),
        ("zinc sulphate", "zinc sulfate", "zinc sulfate"),
        ("aluminium hydroxide", "aluminum hydroxide", "aluminum hydroxide"),
        ("paracetamol/acetaminophen", "paracetamol", "acetaminophen"),
    ],
)
def test_ingredient_candidates(ingredient: str, expected_first: str, must_include: str) -> None:
    cands = ingredient_candidates(ingredient)
    assert cands[0] == expected_first
    assert must_include in cands
    assert len(cands) == len(set(cands))


def test_salt_words_are_only_stripped_from_the_end() -> None:
    # "sodium valproate" is a synonym-table job, not a salt strip to "valproate".
    assert ingredient_candidates("sodium valproate") == ["sodium valproate"]


def test_pairs_are_deduplicated_across_files_and_directions(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text(
        HEADER
        + "DDInter1951,Warfarin,DDInter14,Acetaminophen,Moderate\n"
        + "DDInter1,Abacavir,DDInter1348,Orlistat,Moderate\n",
        encoding="utf-8",
    )
    b.write_text(
        HEADER + "DDInter14,Acetaminophen,DDInter1951,Warfarin,Moderate\n", encoding="utf-8"
    )
    data = read_ddinter([a, b])
    assert data.drugs == {
        "DDInter1951": "Warfarin",
        "DDInter14": "Acetaminophen",
        "DDInter1": "Abacavir",
        "DDInter1348": "Orlistat",
    }
    assert data.pairs == {
        ("DDInter14", "DDInter1951"): "Moderate",
        ("DDInter1", "DDInter1348"): "Moderate",
    }


def test_conflicting_levels_keep_the_most_severe(tmp_path: Path) -> None:
    f = tmp_path / "a.csv"
    f.write_text(
        HEADER
        + "DDInter1,A,DDInter2,B,Minor\n"
        + "DDInter2,B,DDInter1,A,Major\n"
        + "DDInter1,A,DDInter2,B,Unknown\n",
        encoding="utf-8",
    )
    assert read_ddinter([f]).pairs == {("DDInter1", "DDInter2"): "Major"}


def test_read_medicines(tmp_path: Path) -> None:
    f = tmp_path / "m.csv"
    f.write_text(
        "id,name,price(₹),Is_discontinued,manufacturer_name,type,pack_size_label,"
        "short_composition1,short_composition2\n"
        "1,Augmentin 625 Duo Tablet,223.42,FALSE,Glaxo SmithKline Pharmaceuticals Ltd,"
        "allopathy,strip of 10 tablets,Amoxycillin  (500mg) ,  Clavulanic Acid (125mg)\n"
        "2,Dolo 650 Tablet,30.0,TRUE,Micro Labs Ltd,allopathy,strip of 15 tablets,"
        "Paracetamol (650mg),\n",
        encoding="utf-8",
    )
    rows = list(read_medicines(f))
    assert rows[0].name == "Augmentin 625 Duo Tablet"
    assert rows[0].ingredients == ["amoxycillin", "clavulanic acid"]
    assert rows[0].composition1 == "Amoxycillin (500mg)"
    assert rows[0].is_discontinued is False
    assert rows[1].ingredients == ["paracetamol"]
    assert rows[1].composition2 is None
    assert rows[1].is_discontinued is True
