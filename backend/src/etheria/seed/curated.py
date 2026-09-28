"""The curated knowledge files (spec 6.5): schemas and cross-reference checks.

Schema errors raise at load time. Cross-file problems (a condition naming a
symptom that does not exist, a class member DDInter does not know) are
returned as a list, so the seeder and the tests report all of them at once."""

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from etheria.knowledge.text import normalise_name

DATA_DIR = Path(__file__).with_name("data")

BODY_SYSTEMS = frozenset(
    {
        "Cardiovascular",
        "Respiratory",
        "Gastrointestinal",
        "Hepatobiliary",
        "Renal and urinary",
        "Reproductive",
        "Endocrine and metabolic",
        "Haematological",
        "Infectious",
        "Neurological",
        "Mental health",
        "Musculoskeletal",
        "Skin",
        "Eye",
        "Ear nose and throat",
    }
)


def _https(v: str) -> str:
    if not v.startswith("https://"):
        raise ValueError("source must be an https:// URL")
    return v


Source = Annotated[str, AfterValidator(_https)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")]
Weight = Annotated[float, Field(gt=0, le=1)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Symptom(_Model):
    code: Slug
    name: str
    lay_terms: list[str] = []
    source: Source


def _known_systems(v: list[str]) -> list[str]:
    unknown = set(v) - BODY_SYSTEMS
    if unknown:
        raise ValueError(f"unknown body systems {sorted(unknown)}")
    return v


class Condition(_Model):
    icd10: Annotated[str, StringConstraints(pattern=r"^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$")]
    name: str
    synonyms: list[str] = []
    body_systems: Annotated[list[str], Field(min_length=1), AfterValidator(_known_systems)]
    india_common: bool
    symptoms: Annotated[dict[str, Weight], Field(min_length=1)]  # symptom code -> weight
    first_line: list[str] = []  # drug class names
    self_care: list[str] = []
    red_flags: list[str] = []
    source: Source


class DrugClass(_Model):
    name: Slug
    label: str
    members: list[str] = []  # DDInter drug names; empty for non-drug classes (ORS)


class CriticalInteraction(_Model):
    a: dict[Literal["drug", "class"], str]
    b: dict[Literal["drug", "class"], str]
    severity: Literal["Major", "Moderate"]
    rationale: str
    source: Source

    @model_validator(mode="after")
    def _one_key_per_side(self) -> "CriticalInteraction":
        for side in (self.a, self.b):
            if len(side) != 1:
                raise ValueError("each side is exactly one of {drug: ...} or {class: ...}")
        return self


class ExtraDrug(_Model):
    """An India-common drug that DDInter does not list (for example aceclofenac).
    It becomes a Drug node so class-level safety-net pairs cover it."""

    name: str
    atc: Annotated[str, StringConstraints(pattern=r"^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$")]
    source: Source


class Curated(_Model):
    symptoms: list[Symptom]
    conditions: list[Condition]
    drug_classes: list[DrugClass]
    critical: list[CriticalInteraction]
    synonyms: dict[str, str]
    extra_drugs: list[ExtraDrug] = []


def _yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_curated(data_dir: Path = DATA_DIR) -> Curated:
    return Curated(
        symptoms=_yaml(data_dir / "symptoms.yaml"),
        conditions=_yaml(data_dir / "conditions.yaml"),
        drug_classes=_yaml(data_dir / "drug_classes.yaml"),
        critical=_yaml(data_dir / "critical_interactions.yaml"),
        synonyms=_yaml(data_dir / "drug_synonyms.yaml"),
        extra_drugs=_yaml(data_dir / "extra_drugs.yaml"),
    )


def _dupes(items: list[str]) -> list[str]:
    seen: set[str] = set()
    return sorted({i for i in items if i in seen or seen.add(i)})


def validate_curated(c: Curated, ddinter_names: set[str] | None = None) -> list[str]:
    problems: list[str] = []
    problems += [f"duplicate symptom code '{d}'" for d in _dupes([s.code for s in c.symptoms])]
    problems += [
        f"duplicate condition icd10 '{d}'" for d in _dupes([x.icd10 for x in c.conditions])
    ]
    problems += [f"duplicate drug class '{d}'" for d in _dupes([k.name for k in c.drug_classes])]

    # A term (name or lay term) must point at one symptom, or matching is ambiguous.
    owner: dict[str, str] = {}
    for s in c.symptoms:
        for term in {normalise_name(t) for t in [s.name, *s.lay_terms]}:
            if owner.setdefault(term, s.code) != s.code:
                problems.append(f"term '{term}' is ambiguous: {owner[term]} and {s.code}")

    codes = {s.code for s in c.symptoms}
    classes = {k.name for k in c.drug_classes}
    for x in c.conditions:
        problems += [
            f"condition {x.icd10}: unknown symptom '{code}'"
            for code in x.symptoms
            if code not in codes
        ]
        problems += [
            f"condition {x.icd10}: unknown drug class '{k}'"
            for k in x.first_line
            if k not in classes
        ]
    for i, ci in enumerate(c.critical):
        for side in (ci.a, ci.b):
            if "class" in side and side["class"] not in classes:
                problems.append(f"critical #{i}: unknown drug class '{side['class']}'")
        if ci.a == ci.b:
            problems.append(f"critical #{i}: both sides are the same")

    if ddinter_names is not None:
        ddinter = {normalise_name(n) for n in ddinter_names}
        problems += [
            f"extra drug '{d.name}' is already a DDInter drug"
            for d in c.extra_drugs
            if normalise_name(d.name) in ddinter
        ]
        known = ddinter | {normalise_name(d.name) for d in c.extra_drugs}
        for k in c.drug_classes:
            problems += [
                f"'{m}' in class {k.name} is not a DDInter or extra drug"
                for m in k.members
                if normalise_name(m) not in known
            ]
        for i, ci in enumerate(c.critical):
            for side in (ci.a, ci.b):
                if "drug" in side and normalise_name(side["drug"]) not in known:
                    problems.append(f"critical #{i}: '{side['drug']}' is not a known drug")
        problems += [
            f"synonym {alias} -> '{canon}' is not a known drug"
            for alias, canon in c.synonyms.items()
            if normalise_name(canon) not in known
        ]
    return problems
