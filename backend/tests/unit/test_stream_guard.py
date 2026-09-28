"""StreamGuard (spec 4.6 "While"): deterministic rules on each generated sentence."""

from etheria.safety.stream_guard import StreamGuard, apply_rules
from etheria.safety.texts import DOSE_REPLACEMENT, NOT_FOUND_WORDING


def _stream(tokens: list[str], guard: StreamGuard | None = None) -> str:
    g = guard or StreamGuard()
    out: list[str] = []
    for t in tokens:
        out += g.feed(t)
    out += g.flush()
    return "".join(out)


def test_dose_sentence_is_replaced() -> None:
    text, hits = apply_rules("Take 2 tablets twice a day after food. ")
    assert text == DOSE_REPLACEMENT + " "
    assert hits == ["dose"]


def test_amount_with_frequency_is_a_dose() -> None:
    text, _ = apply_rules("Paracetamol 650 mg every 6 hours usually helps.")
    assert text == DOSE_REPLACEMENT


def test_lab_values_are_not_doses() -> None:
    for s in (
        "Your haemoglobin is 9.1 g/dL, below the range of 12-15 g/dL.",
        "Post-prandial glucose was 250 mg/dL on the report.",
        "Dolo 650 contains paracetamol.",
        "Wash the wound with soap and running water for 15 minutes.",
    ):
        assert apply_rules(s) == (s, []), s


def test_diagnosis_phrasing_is_softened() -> None:
    text, hits = apply_rules("You have dengue fever.")
    assert text == "This may be consistent with dengue fever."
    assert hits == ["diagnosis"]
    text, _ = apply_rules("It looks like you are suffering from migraine.")
    assert text == "It looks like this may be consistent with migraine."


def test_conditional_you_have_is_left_alone() -> None:
    for s in (
        "If you have chest pain, call 112.",
        "Do you have a fever as well?",
        "Tell your doctor if you have been taking warfarin.",
    ):
        assert apply_rules(s) == (s, []), s


def test_guard_rewrites_safe_claims() -> None:
    for s in (
        "These two are safe to take together.",
        "There is no interaction between them.",
        "Crocin does not interact with Telma.",
    ):
        text, hits = apply_rules(s)
        assert text == NOT_FOUND_WORDING, s
        assert hits == ["safe_claim"]


def test_cautions_and_not_found_framing_survive() -> None:
    for s in (
        "It is not safe to take ibuprofen with low platelets without a doctor's advice.",
        NOT_FOUND_WORDING,
        "No interaction is recorded in DDInter, but that does not mean it is safe.",
    ):
        assert apply_rules(s) == (s, []), s


def test_foreign_emergency_numbers_become_112() -> None:
    assert apply_rules("Call 911 immediately.") == ("Call 112 immediately.", ["foreign_number"])
    assert apply_rules("Dial 999 now.")[0] == "Dial 112 now."


def test_stream_releases_at_sentence_ends() -> None:
    g = StreamGuard()
    assert g.feed("Rest well") == []
    assert g.feed(". Drink") == ["Rest well. "]
    assert g.flush() == ["Drink"]


def test_decimal_point_is_not_a_sentence_end() -> None:
    g = StreamGuard()
    assert g.feed("Hb is 9.") == []
    assert g.feed("1 g/dL. ") == ["Hb is 9.1 g/dL. "]


def test_dose_split_across_tokens_is_caught() -> None:
    out = _stream(["Rest. You can ", "take 2 tab", "lets twice ", "a day. Drink water."])
    assert out == "Rest. " + DOSE_REPLACEMENT + " Drink water."


def test_long_text_without_punctuation_flushes_at_200_chars() -> None:
    g = StreamGuard(max_chars=200)
    released = g.feed("word " * 50)
    assert released and all(len(s) <= 200 for s in released)
    assert "".join(released + g.flush()) == "word " * 50


def test_wait_limit_releases_partial_text() -> None:
    now = [0.0]
    g = StreamGuard(max_wait_s=0.4, clock=lambda: now[0])
    assert g.feed("Some words") == []
    now[0] = 0.5
    assert g.feed(" more") == ["Some words "]


def test_hits_are_recorded() -> None:
    g = StreamGuard()
    _stream(["You have typhoid. Call 911."], g)
    assert g.hits == ["diagnosis", "foreign_number"]


def test_product_names_with_strengths_are_not_doses() -> None:
    s = (
        "Crocin could be any of Crocin 1000mg Tablet, Crocin Advance Tablet, "
        "Crocin Cold & Flu Max Tablet; all of them contain Acetaminophen [1]."
    )
    assert apply_rules(s) == (s, [])
    assert apply_rules("Dolo 650 Tablet and Calpol 500mg Tablet both contain paracetamol.")[1] == []


def test_a_strength_with_an_instruction_is_still_a_dose() -> None:
    assert apply_rules("Take one Crocin 500mg Tablet every 6 hours.")[1] == ["dose"]
    assert apply_rules("The maximum is 4000 mg a day.")[1] == ["dose"]


def test_a_recorded_in_the_sources_statement_is_not_a_safe_claim() -> None:
    for s in (
        "No interaction is recorded between paracetamol and telmisartan in the sources I checked.",
        "No interaction was found in DDInter for this pair.",
    ):
        assert apply_rules(s) == (s, []), s
    assert apply_rules("There is no known interaction between them.")[1] == ["safe_claim"]
