"""Drug cautions from the user's own record (spec 4.5): code, not the model."""

import pytest

from etheria.safety.cautions import DrugClasses, LabObservation, evaluate, load_cautions


@pytest.fixture(scope="module")
def rules():
    return load_cautions()


IBUPROFEN = DrugClasses(drug="Ibuprofen", classes=["nsaid"])


def _lab(test: str, value: str, flag: str, lab_id: str = "l1") -> LabObservation:
    return LabObservation(id=lab_id, test_name=test, value_text=value, unit=None, flag=flag)


def test_ckd_labs_give_nsaid_cautions(rules) -> None:
    labs = [_lab("Serum Creatinine", "2.1", "high", "a"), _lab("eGFR", "32", "low", "b")]
    found = evaluate([IBUPROFEN], labs, [], pregnant=False, rules=rules)
    assert {(c.drug, c.trigger, c.value) for c in found} == {
        ("Ibuprofen", "Serum Creatinine high", "2.1"),
        ("Ibuprofen", "eGFR low", "32"),
    }
    assert all(c.source.startswith("https://") and c.rationale for c in found)
    assert {c.lab_id for c in found} == {"a", "b"}


def test_normal_labs_give_no_caution(rules) -> None:
    labs = [_lab("Serum Creatinine", "0.9", "normal")]
    assert evaluate([IBUPROFEN], labs, [], pregnant=False, rules=rules) == []


def test_pregnancy_gives_a_caution(rules) -> None:
    (c,) = evaluate([IBUPROFEN], [], [], pregnant=True, rules=rules)
    assert c.trigger == "pregnancy"
    assert c.lab_id is None


def test_lab_aliases_match(rules) -> None:
    for name in ("Platelet count", "Platelets", "PLATELET COUNT"):
        found = evaluate([IBUPROFEN], [_lab(name, "62000", "low")], [], False, rules)
        assert found, name


def test_condition_from_a_discharge_summary(rules) -> None:
    found = evaluate([IBUPROFEN], [], ["Chronic kidney disease stage 3"], False, rules)
    assert [c.trigger for c in found] == ["Chronic kidney disease stage 3"]


def test_class_must_match(rules) -> None:
    para = DrugClasses(drug="Acetaminophen", classes=["paracetamol"])
    assert evaluate([para], [_lab("eGFR", "32", "low")], [], True, rules) == []


def test_metformin_and_low_egfr(rules) -> None:
    met = DrugClasses(drug="Metformin", classes=["biguanide"])
    (c,) = evaluate([met], [_lab("Estimated GFR", "28", "low")], [], False, rules)
    assert c.rule_id.startswith("biguanide")


def test_every_rule_is_well_formed(rules) -> None:
    assert len(rules.rules) >= 12
    assert len({r.id for r in rules.rules}) == len(rules.rules)
