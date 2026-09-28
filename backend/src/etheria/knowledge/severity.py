"""DDInter severity levels, most severe first. Where two sources disagree on a
pair, the more severe level wins: safety favours the higher level."""

SEVERITY_ORDER = ("Major", "Moderate", "Minor", "Unknown")
_RANK = {level: i for i, level in enumerate(SEVERITY_ORDER)}


def rank(level: str) -> int:
    """0 is the most severe; unknown labels sort last."""
    return _RANK.get(level, len(SEVERITY_ORDER))
