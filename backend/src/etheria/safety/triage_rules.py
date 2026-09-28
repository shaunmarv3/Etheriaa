"""Applies the red-flag rule table (spec 4.6) to a message.

Phrases match whole words, case-insensitively. A phrase directly preceded by a
negation ("no stiff neck", "not suicidal") does not count. Rules can only
raise the triage level: the node takes the higher of the rules and the model."""

import re
from dataclasses import dataclass
from typing import Literal

from etheria.safety.red_flags import RedFlagRule, load_rules

Level = Literal["GREEN", "YELLOW", "RED"]
_ORDER: dict[str, int] = {"GREEN": 0, "YELLOW": 1, "RED": 2}
_NEGATION = re.compile(r"\b(?:no|not|without|never|denies|deny)\s+(?:\w+\s+)?$")


def max_level(*levels: Level | None) -> Level | None:
    present = [lv for lv in levels if lv is not None]
    return max(present, key=_ORDER.__getitem__) if present else None


@dataclass(frozen=True)
class RuleHit:
    id: str
    level: Level
    category: str
    helpline: bool


def _pattern(phrase: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in phrase.lower().split()]
    return re.compile(r"(?<![\w'])" + r"\s+".join(words) + r"(?![\w'])")


class RuleMatcher:
    def __init__(self, rules: list[RedFlagRule]) -> None:
        self._rules = rules
        self._compiled = {
            p: _pattern(p)
            for r in rules
            for p in [*r.any_of, *(p for group in r.all_of for p in group)]
        }

    @classmethod
    def load(cls) -> "RuleMatcher":
        return cls(load_rules())

    def _found(self, phrase: str, text: str) -> bool:
        for m in self._compiled[phrase].finditer(text):
            if not _NEGATION.search(text[: m.start()]):
                return True
        return False

    def match(self, text: str) -> list[RuleHit]:
        t = text.lower().replace("’", "'")
        hits = []
        for r in self._rules:
            fired = any(self._found(p, t) for p in r.any_of) or (
                bool(r.all_of) and all(any(self._found(p, t) for p in g) for g in r.all_of)
            )
            if fired:
                hits.append(RuleHit(r.id, r.level, r.category, r.helpline == "tele_manas"))
        return hits

    def level(self, text: str) -> Level | None:
        return max_level(*(h.level for h in self.match(text)))

    def needs_helpline(self, text: str) -> bool:
        return any(h.helpline for h in self.match(text))
