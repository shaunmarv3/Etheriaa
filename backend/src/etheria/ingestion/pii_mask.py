"""PII masking (spec 5.4). Applied before any text reaches an LLM or the
index. Regex-based and deterministic. Age and sex are kept because reference
ranges depend on them. `counts` records how many of each kind were masked,
never the values."""

import re
from collections import Counter
from dataclasses import dataclass

# Verhoeff tables (dihedral group D5): Aadhaar's last digit is a Verhoeff checksum.
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(digits: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


@dataclass(frozen=True)
class MaskResult:
    text: str
    counts: dict[str, int]


# Labels at the start of a line (so "Test Name" column headers survive).
_NAME_LABELS = r"patient\s*name|name|referred\s*by|ref\.?\s*by|consultant"
_ID_LABELS = r"uhid|mrn|patient\s*id|lab\s*no\.?|lab\s*id|sample\s*id|reg(?:istration)?\.?\s*no\.?"
_SEP = r"[ \t]*[:\-.][ \t]*|[ \t]+"
# A value runs until the end of the line or a column gap (a tab or 2+ spaces):
# reports print two fields per line ("Patient Name: X      Age/Sex: 34 Y / Male").
_VALUE = r"([^\s](?:[^\t\n\r ]| (?! ))*)"
_LABELLED_NAME = re.compile(rf"(?im)^([ \t]*(?:{_NAME_LABELS})(?:{_SEP})){_VALUE}")
_LABELLED_ID = re.compile(rf"(?im)^([ \t]*(?:{_ID_LABELS})(?:{_SEP})){_VALUE}")
_ADDRESS = re.compile(rf"(?im)^([ \t]*address[ \t]*[:\-][ \t]*){_VALUE}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_AADHAAR = re.compile(r"(?<!\d)(\d{4})[ \-]?(\d{4})[ \-]?(\d{4})(?!\d)")
_PHONE = re.compile(r"(?<![\d+])(?:\+91[ \-]?|0)?[6-9]\d{4}[ \-]?\d{5}(?!\d)")


def mask_pii(text: str) -> MaskResult:
    counts: Counter[str] = Counter()

    def labelled(kind: str, token: str):
        def sub(m: re.Match[str]) -> str:
            counts[kind] += 1
            return m.group(1) + token

        return sub

    text = _LABELLED_NAME.sub(labelled("name", "[NAME]"), text)
    text = _LABELLED_ID.sub(labelled("id", "[ID]"), text)
    text = _ADDRESS.sub(labelled("address", "[ADDRESS]"), text)

    def email(m: re.Match[str]) -> str:
        counts["email"] += 1
        return "[EMAIL]"

    text = _EMAIL.sub(email, text)

    def aadhaar(m: re.Match[str]) -> str:
        if not verhoeff_valid("".join(m.groups())):
            return m.group(0)
        counts["aadhaar"] += 1
        return "[AADHAAR]"

    text = _AADHAAR.sub(aadhaar, text)

    def phone(m: re.Match[str]) -> str:
        counts["phone"] += 1
        return "[PHONE]"

    text = _PHONE.sub(phone, text)
    return MaskResult(text=text, counts=dict(counts))
