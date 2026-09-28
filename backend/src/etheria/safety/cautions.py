"""Drug cautions from the user's own record (spec 4.5), evaluated in code.

Input: the resolved drugs with their classes, the user's lab rows, the diagnoses
from their discharge summaries and whether they said they are pregnant. Output:
one caution per (rule, drug, triggering fact). The wording that frames a
caution, and the "no recorded caution" note, live in safety/texts.py."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

CAUTIONS_FILE = Path(__file__).with_name("drug_cautions.yaml")
_WORDS = re.compile(r"[a-z0-9]+")


class Trigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab: str | None = None
    flag: Literal["high", "low"] | None = None
    condition_any: list[str] = []
    pregnancy: bool = False

    @model_validator(mode="after")
    def _exactly_one(self) -> "Trigger":
        kinds = [self.lab is not None, bool(self.condition_any), self.pregnancy]
        if sum(kinds) != 1 or (self.lab is not None) != (self.flag is not None):
            raise ValueError("a trigger is exactly one of {lab, flag}, condition_any, pregnancy")
        return self


class CautionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    drug_classes: list[str] = []
    drugs: list[str] = []
    trigger: Trigger
    rationale: str
    source: str


class CautionTable(BaseModel):
    lab_aliases: dict[str, list[str]]
    rules: list[CautionRule]

    @model_validator(mode="after")
    def _labs_known(self) -> "CautionTable":
        for r in self.rules:
            if r.trigger.lab is not None and r.trigger.lab not in self.lab_aliases:
                raise ValueError(f"rule {r.id}: unknown lab key {r.trigger.lab}")
        return self


class DrugClasses(BaseModel):
    drug: str
    classes: list[str]


class LabObservation(BaseModel):
    id: str
    test_name: str
    value_text: str
    unit: str | None = None
    flag: str
    report_date: str | None = None


class Caution(BaseModel):
    rule_id: str
    drug: str
    trigger: str  # "eGFR low", "pregnancy", or the matching diagnosis
    value: str | None  # the lab value as printed on the report
    rationale: str
    source: str
    lab_id: str | None = None


def _words(s: str) -> tuple[str, ...]:
    return tuple(_WORDS.findall(s.lower()))


@lru_cache
def load_cautions(path: Path = CAUTIONS_FILE) -> CautionTable:
    return CautionTable.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _lab_matches(test_name: str, aliases: list[str]) -> bool:
    name = _words(test_name)
    return any(name[: len(a)] == a for a in (_words(x) for x in aliases) if a)


def _applies(rule: CautionRule, drug: DrugClasses) -> bool:
    return bool(set(rule.drug_classes) & set(drug.classes)) or drug.drug.lower() in {
        d.lower() for d in rule.drugs
    }


def evaluate(
    drugs: list[DrugClasses],
    labs: list[LabObservation],
    conditions: list[str],
    pregnant: bool,
    rules: CautionTable,
) -> list[Caution]:
    out: dict[tuple[str, str, str], Caution] = {}
    for rule in rules.rules:
        t = rule.trigger
        for drug in drugs:
            if not _applies(rule, drug):
                continue
            base = {
                "rule_id": rule.id,
                "drug": drug.drug,
                "rationale": rule.rationale,
                "source": rule.source,
            }
            if t.lab is not None:
                for lab in labs:
                    if lab.flag == t.flag and _lab_matches(lab.test_name, rules.lab_aliases[t.lab]):
                        out[(rule.id, drug.drug, lab.id)] = Caution(
                            **base,
                            trigger=f"{lab.test_name} {lab.flag}",
                            value=lab.value_text,
                            lab_id=lab.id,
                        )
            elif t.pregnancy:
                if pregnant:
                    out[(rule.id, drug.drug, "pregnancy")] = Caution(
                        **base, trigger="pregnancy", value=None
                    )
            else:
                phrases = [_words(p) for p in t.condition_any]
                for cond in conditions:
                    words = _words(cond)
                    joined = " " + " ".join(words) + " "
                    if any(" " + " ".join(p) + " " in joined for p in phrases):
                        out[(rule.id, drug.drug, cond)] = Caution(**base, trigger=cond, value=None)
                        break
    return list(out.values())
