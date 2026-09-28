from etheria.knowledge.resolver import AMBIGUOUS, NO_MATCH, pick_candidate

P = ("paracetamol",)
IBU_P = ("ibuprofen", "paracetamol")


def test_no_candidates() -> None:
    assert pick_candidate([]) == NO_MATCH


def test_below_the_similarity_floor_is_no_match() -> None:
    assert pick_candidate([("Dolo 650 Tablet", 0.44, P)]) == NO_MATCH


def test_single_candidate_above_the_floor() -> None:
    assert pick_candidate([("Dolo 650 Tablet", 0.56, P)]) == ("Dolo 650 Tablet", P)


def test_close_candidates_with_the_same_ingredients_are_not_ambiguous() -> None:
    # Pack sizes and strengths of one product differ in name, not in ingredients.
    cands = [("Dolo 650 Tablet", 0.60, P), ("Dolo 500 Tablet", 0.58, P), ("Combiflam", 0.48, IBU_P)]
    assert pick_candidate(cands) == ("Dolo 650 Tablet", P)


def test_different_ingredients_within_the_lead_are_ambiguous() -> None:
    cands = [("Tramazac 50", 0.60, ("tramadol",)), ("Tramazax 50", 0.55, ("sertraline",))]
    assert pick_candidate(cands) == AMBIGUOUS


def test_a_clear_lead_over_a_different_product_wins() -> None:
    cands = [("Dolo 650 Tablet", 0.70, P), ("Dolokind Plus", 0.59, IBU_P)]
    assert pick_candidate(cands) == ("Dolo 650 Tablet", P)


def test_lead_is_measured_against_the_best_of_the_other_group() -> None:
    cands = [
        ("A", 0.80, P),
        ("B", 0.79, P),
        ("C", 0.72, IBU_P),  # 0.08 behind the top: ambiguous
    ]
    assert pick_candidate(cands) == AMBIGUOUS
