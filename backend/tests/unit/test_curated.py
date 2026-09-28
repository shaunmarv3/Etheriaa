from pathlib import Path

import pytest
from pydantic import ValidationError

from etheria.core.settings import BACKEND_DIR
from etheria.safety.red_flags import load_rules
from etheria.seed.curated import (
    Condition,
    CriticalInteraction,
    Curated,
    DrugClass,
    ExtraDrug,
    Symptom,
    load_curated,
    validate_curated,
)
from etheria.seed.sources import read_ddinter

SRC = "https://medlineplus.gov/x.html"


def small(**overrides) -> Curated:
    base = dict(
        symptoms=[
            Symptom(code="fever", name="Fever", lay_terms=["bukhar", "temperature"], source=SRC),
            Symptom(code="diarrhoea", name="Diarrhoea", lay_terms=["loose motions"], source=SRC),
        ],
        conditions=[
            Condition(
                icd10="A90",
                name="Dengue fever",
                synonyms=["dengue"],
                body_systems=["Infectious"],
                india_common=True,
                symptoms={"fever": 1.0},
                first_line=["antipyretic"],
                self_care=["Rest"],
                red_flags=["Bleeding gums"],
                source=SRC,
            )
        ],
        drug_classes=[
            DrugClass(name="antipyretic", label="Antipyretic", members=["Acetaminophen"])
        ],
        critical=[
            CriticalInteraction(
                a={"drug": "Tramadol"},
                b={"class": "antipyretic"},
                severity="Major",
                rationale="r",
                source=SRC,
            )
        ],
        synonyms={"paracetamol": "Acetaminophen"},
    )
    base.update(overrides)
    return Curated(**base)


def test_a_consistent_set_has_no_problems() -> None:
    assert validate_curated(small(), {"Acetaminophen", "Tramadol"}) == []


def test_unknown_symptom_code_on_a_condition() -> None:
    c = small()
    c.conditions[0].symptoms["rash"] = 0.5
    assert any("unknown symptom 'rash'" in p for p in validate_curated(c))


def test_condition_without_symptoms_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValidationError):
        Condition(
            icd10="A90",
            name="x",
            body_systems=["Infectious"],
            india_common=True,
            symptoms={},
            source=SRC,
        )


@pytest.mark.parametrize("weight", [0.0, 1.5, -0.1])
def test_weight_outside_zero_one(weight: float) -> None:
    with pytest.raises(ValidationError):
        Condition(
            icd10="A90",
            name="x",
            body_systems=["Infectious"],
            india_common=True,
            symptoms={"fever": weight},
            source=SRC,
        )


def test_bad_icd10_shape_and_unknown_body_system() -> None:
    with pytest.raises(ValidationError):
        Condition(
            icd10="dengue",
            name="x",
            body_systems=["Infectious"],
            india_common=True,
            symptoms={"fever": 1},
            source=SRC,
        )
    with pytest.raises(ValidationError):
        Condition(
            icd10="A90",
            name="x",
            body_systems=["Spleen stuff"],
            india_common=True,
            symptoms={"fever": 1},
            source=SRC,
        )


def test_source_must_be_https() -> None:
    with pytest.raises(ValidationError):
        Symptom(code="fever", name="Fever", source="medlineplus")


def test_duplicate_keys() -> None:
    c = small()
    c.symptoms.append(c.symptoms[0])
    c.conditions.append(c.conditions[0])
    problems = validate_curated(c)
    assert any("duplicate symptom code 'fever'" in p for p in problems)
    assert any("duplicate condition icd10 'A90'" in p for p in problems)


def test_a_lay_term_shared_by_two_symptoms_is_ambiguous() -> None:
    c = small()
    c.symptoms[1].lay_terms.append("Temperature")
    assert any("'temperature'" in p and "ambiguous" in p for p in validate_curated(c))


def test_unknown_first_line_class_and_critical_class() -> None:
    c = small()
    c.conditions[0].first_line.append("nsaid")
    c.critical[0].b = {"class": "ssri"}
    problems = validate_curated(c)
    assert any("unknown drug class 'nsaid'" in p for p in problems)
    assert any("unknown drug class 'ssri'" in p for p in problems)


def test_ddinter_names_are_checked_when_given() -> None:
    problems = validate_curated(small(), {"Tramadol"})  # Acetaminophen missing
    assert any("'Acetaminophen'" in p and "class antipyretic" in p for p in problems)
    assert any("'Acetaminophen'" in p and "synonym" in p for p in problems)


def test_critical_side_must_be_exactly_one_of_drug_or_class() -> None:
    with pytest.raises(ValidationError):
        CriticalInteraction(
            a={"drug": "A", "class": "b"},
            b={"drug": "C"},
            severity="Major",
            rationale="r",
            source=SRC,
        )


# --- the committed files ---


def test_committed_curated_files_are_consistent() -> None:
    assert validate_curated(load_curated()) == []


def test_committed_curated_files_match_ddinter() -> None:
    files = sorted((BACKEND_DIR / "data" / "seed").glob("ddinter_downloads_code_*.csv"))
    if len(files) != 8:
        pytest.skip("DDInter not downloaded (uv run etheria seed)")
    names = set(read_ddinter(files).drugs.values())
    assert validate_curated(load_curated(), names) == []


def test_committed_curated_scope_matches_spec() -> None:
    c = load_curated()
    assert len(c.conditions) >= 90
    assert len(c.symptoms) >= 100
    assert len(c.critical) >= 25
    codes = {s.code for s in c.symptoms}
    lay = {t.lower() for s in c.symptoms for t in s.lay_terms}
    assert "loose motions" in lay  # a canary depends on it
    assert "diarrhoea" in codes
    names = {x.name.lower() for x in c.conditions}
    for must in [
        "dengue",
        "malaria",
        "typhoid",
        "tuberculosis",
        "chikungunya",
        "hypothyroidism",
        "migraine",
        "asthma",
    ]:
        assert any(must in n for n in names), must


def test_red_flag_rules_load_and_cover_spec_categories() -> None:
    rules = load_rules()
    cats = {r.category for r in rules}
    for must in [
        "cardiac",
        "stroke",
        "breathing",
        "anaphylaxis",
        "seizure_unconscious",
        "bleeding",
        "self_harm",
        "meningitis",
        "dengue_warning",
    ]:
        assert must in cats, must
    assert all(r.helpline == "tele_manas" for r in rules if r.category == "self_harm")
    assert len({r.id for r in rules}) == len(rules)


def test_red_flag_rule_needs_a_trigger(tmp_path: Path) -> None:
    f = tmp_path / "r.yaml"
    f.write_text("- {id: x, level: RED, category: cardiac}\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_rules(f)


def test_extra_drugs_satisfy_class_members_but_must_not_duplicate_ddinter() -> None:
    c = small(
        drug_classes=[
            DrugClass(name="antipyretic", label="A", members=["Acetaminophen", "Aceclofenac"])
        ],
        extra_drugs=[ExtraDrug(name="Aceclofenac", atc="M01AB16", source=SRC)],
    )
    assert validate_curated(c, {"Acetaminophen", "Tramadol"}) == []
    problems = validate_curated(c, {"Acetaminophen", "Tramadol", "Aceclofenac"})
    assert any("'Aceclofenac' is already a DDInter drug" in p for p in problems)


def test_atc_code_shape() -> None:
    with pytest.raises(ValidationError):
        ExtraDrug(name="X", atc="M01", source=SRC)


def test_tinnitus_has_its_medical_name_as_a_lay_term() -> None:
    from etheria.seed.curated import load_curated

    (s,) = [s for s in load_curated().symptoms if s.code == "tinnitus"]
    assert {"tinnitus", "ringing in my ears", "ears ringing"} <= set(s.lay_terms)
