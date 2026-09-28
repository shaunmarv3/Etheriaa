"""Parsing the downloaded sources (spec 6.4 phases 2, 4, 5)."""

import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from etheria.knowledge.text import normalise_name

_PARENS = re.compile(r"\([^)]*\)")
_SPACES = re.compile(r"\s+")
# DDInter levels, most severe first. The files never disagreed on 2026-09-28,
# but if they ever do, the more severe level wins.
SEVERITY_ORDER = ("Major", "Moderate", "Minor", "Unknown")
_RANK = {level: i for i, level in enumerate(SEVERITY_ORDER)}


@dataclass
class DDInterData:
    drugs: dict[str, str]  # ddinter_id -> name
    pairs: dict[tuple[str, str], str]  # (lower id, higher id) -> level


def read_ddinter(paths: list[Path]) -> DDInterData:
    drugs: dict[str, str] = {}
    pairs: dict[tuple[str, str], str] = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                a, b = row["DDInterID_A"], row["DDInterID_B"]
                drugs[a] = row["Drug_A"]
                drugs[b] = row["Drug_B"]
                key = (a, b) if a < b else (b, a)
                level = row["Level"]
                old = pairs.get(key)
                if old is None or _RANK.get(level, 99) < _RANK.get(old, 99):
                    pairs[key] = level
    return DDInterData(drugs=drugs, pairs=pairs)


class BrandRow(NamedTuple):
    name: str
    manufacturer: str | None
    type: str | None
    pack_size_label: str | None
    composition1: str | None
    composition2: str | None
    ingredients: list[str]
    is_discontinued: bool


def _clean(s: str) -> str | None:
    s = _SPACES.sub(" ", s).strip()
    return s or None


def parse_ingredient(composition: str) -> str | None:
    """'Amoxycillin  (500mg) ' -> 'amoxycillin'. The dose is dropped."""
    return normalise_name(_PARENS.sub(" ", composition)) or None


def read_medicines(path: Path) -> Iterator[BrandRow]:
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            c1 = _clean(row["short_composition1"])
            c2 = _clean(row["short_composition2"])
            ingredients = [i for c in (c1, c2) if c and (i := parse_ingredient(c))]
            yield BrandRow(
                name=_clean(row["name"]) or "",
                manufacturer=_clean(row["manufacturer_name"]),
                type=_clean(row["type"]),
                pack_size_label=_clean(row["pack_size_label"]),
                composition1=c1,
                composition2=c2,
                ingredients=ingredients,
                is_discontinued=row["Is_discontinued"].strip().upper() == "TRUE",
            )
