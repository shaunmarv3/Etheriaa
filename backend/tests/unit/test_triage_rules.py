"""The red-flag rule matcher (spec 4.6): rules can only raise the level."""

import pytest

from etheria.safety.triage_rules import RuleMatcher, max_level


@pytest.fixture(scope="module")
def matcher() -> RuleMatcher:
    return RuleMatcher.load()


def _ids(matcher: RuleMatcher, text: str) -> set[str]:
    return {h.id for h in matcher.match(text)}


def test_chest_pain_with_sweating_is_red(matcher: RuleMatcher) -> None:
    hits = matcher.match("I'm having chest pain and sweating right now, left arm feels heavy")
    assert "cardiac_chest_pain" in {h.id for h in hits}
    assert matcher.level("chest pain and sweating") == "RED"


def test_all_of_needs_every_group(matcher: RuleMatcher) -> None:
    ids = _ids(matcher, "I have chest pain when I cough")
    assert "cardiac_chest_pain" not in ids
    assert "chest_pain_alone" in ids
    assert matcher.level("I have chest pain when I cough") == "YELLOW"


def test_self_harm_carries_the_helpline(matcher: RuleMatcher) -> None:
    (hit,) = [h for h in matcher.match("I don't want to live anymore") if h.id == "self_harm"]
    assert hit.level == "RED"
    assert hit.helpline
    assert matcher.needs_helpline("I don't want to live anymore")


def test_phrases_match_whole_words_only(matcher: RuleMatcher) -> None:
    assert "seizure_unconscious" not in _ids(matcher, "what are the benefits of walking")
    assert "heat_stroke" not in _ids(matcher, "loose motions and I feel confused about diet")


def test_negated_phrase_does_not_fire(matcher: RuleMatcher) -> None:
    assert "meningitis_signs" not in _ids(matcher, "fever for two days but no stiff neck")
    assert "meningitis_signs" in _ids(matcher, "fever and a stiff neck since morning")


def test_a_number_alone_is_not_a_high_fever(matcher: RuleMatcher) -> None:
    assert "high_fever" not in _ids(matcher, "my sugar was 104 fasting")
    assert "high_fever" in _ids(matcher, "fever of 104 since last night")


def test_no_hit_means_no_level(matcher: RuleMatcher) -> None:
    assert matcher.level("I have a mild backache") is None


def test_max_level_only_raises() -> None:
    assert max_level("GREEN", "RED") == "RED"
    assert max_level("YELLOW", None, "GREEN") == "YELLOW"
    assert max_level(None) is None
