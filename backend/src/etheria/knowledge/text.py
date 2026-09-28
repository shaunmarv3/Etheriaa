"""Name normalisation shared by the seeder and the knowledge services, so a name
is keyed the same way when it is loaded and when it is looked up."""

import re
import unicodedata

_SPACES = re.compile(r"\s+")

# British / Indian spellings -> the US spelling DDInter uses.
_SPELLING = [
    (re.compile(r"sulph"), "sulf"),
    (re.compile(r"\baluminium\b"), "aluminum"),
]

# Salt and ester words, stripped only from the end of an ingredient
# ("metoprolol succinate" -> "metoprolol"). Measured on 2026-09-28: 38% of
# ingredient mentions in the Indian dataset miss DDInter as written, many of
# them only because of the salt.
_SALTS = frozenset(
    """hydrochloride hcl hydrobromide maleate succinate tartrate bitartrate oxalate medoxomil
    proxetil axetil propionate dipropionate furoate valerate besylate besilate mesylate
    mesilate citrate sulfate phosphate acetate fumarate bromide sodium disodium potassium
    calcium magnesium diethylamine trihydrate dihydrate monohydrate anhydrous decanoate
    gluconate lactate pamoate embonate estolate ethylsuccinate stearate""".split()
)


def normalise_name(s: str) -> str:
    return _SPACES.sub(" ", unicodedata.normalize("NFKC", s).casefold()).strip()


def _spelling(s: str) -> str:
    for pattern, repl in _SPELLING:
        s = pattern.sub(repl, s)
    return s


def _strip_salts(s: str) -> str:
    words = s.split(" ")
    while len(words) > 1 and words[-1] in _SALTS:
        words.pop()
    return " ".join(words)


def ingredient_candidates(ingredient: str) -> list[str]:
    """Names to try for one ingredient, most specific first. `a/b` means the
    label lists alternative names for the same ingredient."""
    out: list[str] = []
    for alt in normalise_name(ingredient).split("/"):
        alt = alt.strip()
        if not alt:
            continue
        us = _spelling(alt)  # DDInter's spelling first
        for cand in (us, alt, _strip_salts(us)):
            if cand not in out:
                out.append(cand)
    return out
