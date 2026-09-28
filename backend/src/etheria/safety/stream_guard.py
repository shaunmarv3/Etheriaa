"""StreamGuard (spec 4.6, "While"): deterministic rules applied to each
generated sentence before it reaches the user.

Text is buffered to a sentence end, 200 characters or 400 ms, whichever comes
first, and each released segment goes through `apply_rules`:
1. dosing instructions -> "Dosing should come from your doctor or pharmacist."
2. "you have X" -> "this may be consistent with X"
3. "safe to combine" / "no interaction" -> the not-found wording
4. 911 / 999 -> 112

The rules are patterns, so they are a backstop, not a proof: the eval measures
what gets through (spec 4.6, known limitation)."""

import re
import time
from collections.abc import Callable

from etheria.safety.texts import DOSE_REPLACEMENT, NOT_FOUND_WORDING

_I = re.IGNORECASE

_UNITS = r"(?:mg|mcg|µg|ug|g|gm|gms|grams?|ml|iu|units?)"
# An amount, but not a lab unit (mg/dL) and not a product name's strength
# ("Crocin 1000mg Tablet"): those are followed by a slash or a dosage form.
_FORM = r"(?:tablets?|tabs?|capsules?|caps?|syrup|suspension|injection|gel|cream|drops?|sachets?)"
_AMOUNT = re.compile(rf"\b\d+(?:[.,]\d+)?\s?{_UNITS}\b(?!\s*/)(?!\s+{_FORM}\b)", _I)
_NUM = r"(?:\d+(?:\.\d+)?(?:\s*-\s*\d+)?|one|two|three|four|five|half|1/2)"
_COUNT = re.compile(
    rf"\b{_NUM}\s+(?:tablets?|tabs?|pills?|capsules?|caps?|teaspoons?|tsp|tablespoons?|"
    r"spoons?|drops?|puffs?|sachets?|injections?)\b",
    _I,
)
_FREQ = re.compile(
    r"\b(?:once|twice|thrice|(?:\d+|one|two|three|four|five|six)\s+times)\s+"
    r"(?:a|per|each|every)\s+day\b"
    r"|\bevery\s+\d+(?:\s*(?:-|to)\s*\d+)?\s*(?:hours?|hrs?)\b"
    r"|\b(?:daily|per\s+day|a\s+day|at\s+night|at\s+bedtime)\b",
    _I,
)
_FREQ_ABBR = re.compile(r"\b(?:OD|BD|BID|TDS|TID|QID|QDS|HS|SOS)\b")
_INTAKE = re.compile(
    # not a bare "max": it is part of brand names ("Cold & Flu Max")
    r"\b(?:take|taking|takes|dose|dosage|doses|give|given|swallow|chew|maximum|"
    r"up\s+to|no\s+more\s+than|at\s+a\s+time)\b",
    _I,
)
_TAKE_N = re.compile(r"\btake\s+(?:\d+|one|two|three|half)\b", _I)

_DIAG = re.compile(
    r"\byou\s+(?:have\s+been\s+diagnosed\s+with|are\s+diagnosed\s+with|are\s+suffering\s+from|"
    r"(?:definitely|clearly|probably|most\s+likely)\s+have|have)\s+"
    r"(?!(?:been|to|any|no|not|had|taken|mentioned|noticed|already|told|shared|uploaded|some|"
    r"questions?|symptoms?|a\s+history)\b)",
    _I,
)
_CONDITIONAL = re.compile(
    r"\b(?:if|when|whether|unless|since|because|while|do|does|did|as|that|in\s+case|and|or)\s+$",
    _I,
)

_SAFE = [
    re.compile(p, _I)
    for p in (
        r"\b(?:completely\s+|perfectly\s+|totally\s+|generally\s+)?safe\s+to\s+"
        r"(?:take|combine|use|have|mix|give)\b",
        r"\bsafe\s+(?:together|combination)\b",
        r"\bcan\s+(?:be\s+)?safely\s+(?:be\s+)?(?:take|taken|combine|combined|use|used)\b",
        r"\bno\s+(?:known\s+|significant\s+|major\s+)?(?:drug\s+)?interactions?\b",
        r"\b(?:does|do)(?:\s+not|n't)\s+interact\b",
        r"\b(?:won't|will\s+not)\s+interact\b",
    )
]
_SAFE_NEGATED = re.compile(r"(?:\bnot|n't|\bnever|\bun)\s*(?:\w+\s+){0,1}$", _I)
# The not-found framing the product rules ask for: "no interaction is recorded in
# the sources", "that does not mean it is safe", "confirm with a pharmacist".
_FRAMED = re.compile(
    r"does\s*n[o']t\s+mean|not\s+mean|confirm\s+with|not\s+a\s+(?:guarantee|clearance)"
    r"|\bno\s+interactions?\b.{0,60}?\b(?:recorded|found|listed|documented)\b",
    _I,
)

_CALL = re.compile(r"\b(?:call|dial|ring|phone|emergency)\b", _I)
_SPLIT = re.compile(r"^(\s*(?:[-*]\s+|\d+[.)]\s+)?)(.*?)(\s*)$", re.S)


def _is_dose(s: str) -> bool:
    if _TAKE_N.search(s):
        return True
    quantity = _AMOUNT.search(s) or _COUNT.search(s)
    return bool(quantity) and bool(_FREQ.search(s) or _FREQ_ABBR.search(s) or _INTAKE.search(s))


def _is_safe_claim(s: str) -> bool:
    if _FRAMED.search(s):
        return False
    for p in _SAFE:
        for m in p.finditer(s):
            if not _SAFE_NEGATED.search(s[: m.start()]):
                return True
    return False


def _soften_diagnosis(body: str) -> str:
    def repl(m: re.Match[str]) -> str:
        before = body[: m.start()]
        if _CONDITIONAL.search(before):
            return m.group(0)
        lead = "This" if not before.strip() else "this"
        return f"{lead} may be consistent with "

    return _DIAG.sub(repl, body)


def apply_rules(text: str) -> tuple[str, list[str]]:
    """Guard one segment. Returns the guarded text and the names of the rules that fired."""
    prefix, body, suffix = _SPLIT.match(text).groups()  # type: ignore[union-attr]
    if not body:
        return text, []
    if _is_dose(body):
        return prefix + DOSE_REPLACEMENT + suffix, ["dose"]
    if _is_safe_claim(body):
        return prefix + NOT_FOUND_WORDING + suffix, ["safe_claim"]
    hits = []
    softened = _soften_diagnosis(body)
    if softened != body:
        hits.append("diagnosis")
        body = softened
    numbers = re.sub(r"\b911\b", "112", body)
    if _CALL.search(numbers):
        numbers = re.sub(r"\b999\b", "112", numbers)
    if numbers != body:
        hits.append("foreign_number")
        body = numbers
    return prefix + body + suffix, hits


_BOUNDARY = re.compile(r"(?<!\d)[.!?]+[\"')\]]*\s+|\n+")


class StreamGuard:
    def __init__(
        self,
        max_chars: int = 200,
        max_wait_s: float = 0.4,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_chars = max_chars
        self.max_wait_s = max_wait_s
        self._clock = clock
        self._buf = ""
        self._since: float | None = None
        self.hits: list[str] = []

    def _release(self, segment: str) -> str:
        guarded, hits = apply_rules(segment)
        self.hits += hits
        return guarded

    def _cut_at_space(self, limit: int) -> int:
        cut = self._buf.rfind(" ", 0, limit)
        return cut + 1 if cut >= 0 else 0

    def feed(self, token: str) -> list[str]:
        if not token:
            return []
        if not self._buf:
            self._since = self._clock()
        self._buf += token
        out = []
        while m := _BOUNDARY.search(self._buf):
            out.append(self._release(self._buf[: m.end()]))
            self._buf = self._buf[m.end() :]
        while len(self._buf) >= self.max_chars:
            cut = self._cut_at_space(self.max_chars) or self.max_chars
            out.append(self._release(self._buf[:cut]))
            self._buf = self._buf[cut:]
        if self._buf and self._since is not None and self._clock() - self._since >= self.max_wait_s:
            cut = self._cut_at_space(len(self._buf))
            if cut:
                out.append(self._release(self._buf[:cut]))
                self._buf = self._buf[cut:]
        if out:
            self._since = self._clock() if self._buf else None
        return out

    def flush(self) -> list[str]:
        if not self._buf:
            return []
        out = [self._release(self._buf)]
        self._buf, self._since = "", None
        return out
