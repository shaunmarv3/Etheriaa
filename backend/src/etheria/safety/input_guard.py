"""input_guard (spec 4.3): length limit, prompt-injection heuristics and the
red-flag pre-scan. It blocks abuse only, never medical content, and never an
emergency: when the pre-scan says RED the turn goes on, whatever else it says."""

import re

from pydantic import BaseModel

from etheria.safety.triage_rules import Level, RuleMatcher, max_level

MAX_CHARS = 4000

_INJECTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bignore\s+(?:all\s+|any\s+|your\s+|the\s+)*(?:previous|prior|above|earlier)\s+"
        r"(?:instructions|rules|prompts?)",
        r"\bdisregard\s+(?:all\s+|your\s+|the\s+)*(?:previous|prior|above)?\s*(?:instructions|rules)",
        r"\byou\s+are\s+now\s+(?:a|an|my|the)\b",
        r"\byou\s+are\s+a\s+doctor\s+now\b",
        r"\bact\s+as\s+(?:a|an|my)\s+(?:doctor|physician|pharmacist)\b",
        r"\b(?:reveal|show|print|repeat)\s+(?:your\s+|the\s+)?system\s+prompt",
        r"\bdeveloper\s+mode\b",
        r"\bjailbreak\b",
        # Added in M7 after an injection corpus (tests/security/test_injection_corpus.py).
        r"\bforget\s+(?:all\s+|your\s+|the\s+|previous\s+|prior\s+)*(?:instructions|rules|prompts?)",
        r"\bignore\s+(?:everything|anything|all)\s+(?:above|before|previous|prior)",
        r"\b(?:override|bypass)\s+(?:your\s+|the\s+|all\s+)*(?:safety\s+)?"
        r"(?:rules|instructions|guidelines|restrictions|filters?)",
        r"\b(?:pretend|roleplay|role-play)\s+(?:to\s+be\s+|you\s+are\s+|as\s+)?(?:a|an|my)\s+"
        r"(?:doctor|physician|pharmacist)",
        r"\bnew\s+instructions\s*:",
        r"(?:^|\n)\s*system\s*:",
        r"<\s*/?\s*system\s*>",
        r"\b(?:hidden|secret|original)\s+(?:instructions|prompt|rules)\b",
        r"\bdo\s+anything\s+now\b",
    )
]


class GuardResult(BaseModel):
    blocked: bool = False
    reason: str | None = None
    rule_ids: list[str] = []
    rule_level: Level | None = None
    helpline: bool = False


def check(message: str, matcher: RuleMatcher) -> GuardResult:
    hits = matcher.match(message)
    result = GuardResult(
        rule_ids=[h.id for h in hits],
        rule_level=max_level(*(h.level for h in hits)),
        helpline=any(h.helpline for h in hits),
    )
    if result.rule_level == "RED":
        return result
    if len(message) > MAX_CHARS:
        return result.model_copy(update={"blocked": True, "reason": "too_long"})
    if any(p.search(message) for p in _INJECTION):
        return result.model_copy(update={"blocked": True, "reason": "prompt_injection"})
    return result
