from etheria.medical_apis.base import MedicalApiError
from etheria.medical_apis.bioportal import Concept
from etheria.medical_apis.icd10 import Icd10Code
from etheria.seed.codes import ConditionRef, concept_terms, gather_codes


class FakeIcd:
    async def lookup(self, code: str) -> Icd10Code | None:
        if code == "BOOM":
            raise MedicalApiError("icd10", "HTTP 500")
        return {"A90": Icd10Code(code="A90", name="Dengue fever [classical dengue]")}.get(code)


class FakeBioPortal:
    concepts = {
        "dengue": Concept(pref_label="Dengue", snomed="38362002", cui="C0011311"),
        "diarrhoea": Concept(pref_label="Diarrhea", snomed="62315008", cui="C0011991"),
    }

    async def find_concept(self, term: str) -> Concept | None:
        if term == "explodes":
            raise MedicalApiError("bioportal", "timeout")
        return self.concepts.get(term.lower())


class FakeRxNav:
    async def rxcui(self, name: str) -> str | None:
        return {"acetaminophen": "161"}.get(name.lower())


def test_concept_terms_try_plain_name_parenthetical_then_synonyms() -> None:
    ref = ConditionRef(icd10="I10", name="High blood pressure (hypertension)", synonyms=["BP"])
    assert concept_terms(ref.name, ref.synonyms) == [
        "High blood pressure",
        "hypertension",
        "High blood pressure (hypertension)",
        "BP",
    ]


async def test_gather_codes_counts_filled_missing_and_failed() -> None:
    conditions = [
        ConditionRef(icd10="A90", name="Dengue fever", synonyms=["dengue"]),
        ConditionRef(icd10="Z99.9", name="Unknown thing", synonyms=[]),
        ConditionRef(icd10="BOOM", name="explodes", synonyms=[]),
    ]
    symptoms = [("diarrhoea", "Diarrhoea"), ("zzz", "Nothing")]
    drugs = ["Acetaminophen", "Aceclofenac"]
    rows, report = await gather_codes(
        conditions, symptoms, drugs, FakeIcd(), FakeBioPortal(), FakeRxNav(), concurrency=2
    )
    assert rows.conditions == [
        {
            "icd10": "A90",
            "icd10_name": "Dengue fever [classical dengue]",
            "snomed": "38362002",
            "cui": "C0011311",
        },
        {"icd10": "Z99.9", "icd10_name": None, "snomed": None, "cui": None},
    ]
    assert rows.symptoms == [
        {"code": "diarrhoea", "snomed": "62315008", "cui": "C0011991"},
        {"code": "zzz", "snomed": None, "cui": None},
    ]
    assert rows.drugs == [
        {"name": "Acetaminophen", "rxcui": "161"},
        {"name": "Aceclofenac", "rxcui": None},
    ]
    assert report.icd10_verified == 1
    assert report.icd10_unknown == ["Z99.9"]
    assert report.snomed_filled == 2 and report.snomed_missing == 2
    assert report.rxcui_filled == 1 and report.rxcui_missing == 1
    assert len(report.failed) == 1 and "BOOM" in report.failed[0]


async def test_without_bioportal_snomed_is_skipped_not_failed() -> None:
    rows, report = await gather_codes(
        [ConditionRef(icd10="A90", name="Dengue fever", synonyms=[])],
        [],
        [],
        FakeIcd(),
        None,
        FakeRxNav(),
    )
    assert rows.conditions[0]["snomed"] is None
    assert report.failed == [] and report.snomed_skipped
