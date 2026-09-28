"""Numbers, reference ranges and flags, computed by code (spec 5.6). The model
copies text; this module decides what the text means. Anything it cannot
parse becomes `unknown`, never a guess."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

Flag = Literal["low", "normal", "high", "unknown"]
Sex = Literal["male", "female"]

# Plain digits, or digit groups separated by commas (Indian lakh grouping
# "1,50,000" as well as "12,500"), with an optional decimal part.
_NUMBER = re.compile(r"^(?:\d+|\d{1,3}(?:,\d{2})*,\d{3}|\d{1,3},\d{3})(?:\.\d+)?$")
_NUM = r"\d[\d,]*(?:\.\d+)?"
_DASH = r"\s*(?:-|–|—|to)\s*"

_BETWEEN = re.compile(rf"^({_NUM}){_DASH}({_NUM})$", re.IGNORECASE)
_UPPER = re.compile(rf"^(<=|≤|<|upto|up\s+to)\s*({_NUM})$", re.IGNORECASE)
_LOWER = re.compile(rf"^(>=|≥|>)\s*({_NUM})$", re.IGNORECASE)
_SEX_PART = re.compile(
    rf"\b(male|female|m|f)\b\s*[:\-]?\s*({_NUM}{_DASH}{_NUM}|(?:<=|≤|<|>=|≥|>)\s*{_NUM})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RefRange:
    low: Decimal | None
    high: Decimal | None
    low_inclusive: bool
    high_inclusive: bool


def parse_number(s: str) -> Decimal | None:
    s = s.strip()
    if not _NUMBER.match(s):
        return None
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def _simple_range(text: str) -> RefRange | None:
    text = " ".join(text.split())
    if m := _BETWEEN.match(text):
        low, high = parse_number(m.group(1)), parse_number(m.group(2))
        if low is None or high is None or low > high:
            return None
        return RefRange(low, high, True, True)
    if m := _UPPER.match(text):
        high = parse_number(m.group(2))
        if high is None:
            return None
        return RefRange(None, high, True, m.group(1) != "<")
    if m := _LOWER.match(text):
        low = parse_number(m.group(2))
        if low is None:
            return None
        return RefRange(low, None, m.group(1) != ">", True)
    return None


def parse_range(text: str | None, sex: Sex | None) -> RefRange | None:
    if not text or not text.strip():
        return None
    parts = {m.group(1).lower()[0]: m.group(2) for m in _SEX_PART.finditer(text)}
    if "m" in parts and "f" in parts:
        if sex is None:
            return None
        return _simple_range(parts[sex[0]])
    return _simple_range(text)


def compute_flag(value: Decimal | None, rng: RefRange | None) -> Flag:
    if value is None or rng is None:
        return "unknown"
    if rng.low is not None and (value < rng.low or (value == rng.low and not rng.low_inclusive)):
        return "low"
    if rng.high is not None and (
        value > rng.high or (value == rng.high and not rng.high_inclusive)
    ):
        return "high"
    return "normal"
