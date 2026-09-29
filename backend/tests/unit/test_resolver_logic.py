from etheria.knowledge.resolver import (
    AMBIGUOUS,
    MAX_VARIANTS,
    NO_MATCH,
    family_variants,
    group_variants,
    pick_candidate,
)

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


# ---- brand variants (spec 4.5): say what each product behind a name contains ----

TELMISARTAN = ("telmisartan",)
TELMA_FAMILY = [
    ("Telma 40 Tablet", TELMISARTAN),
    ("Telma 80 Tablet", TELMISARTAN),
    ("Telma-AM H 40 Tablet", ("amlodipine", "telmisartan")),
    ("Telma-AM Tablet", ("amlodipine", "telmisartan")),
    ("Telma 80-H Tablet", ("hydrochlorothiazide", "telmisartan")),
    ("Telma H Tablet", ("hydrochlorothiazide", "telmisartan")),
]


def test_family_variants_name_each_other_ingredient_set_plainest_first() -> None:
    variants, more = family_variants("Telma 40", TELMISARTAN, TELMA_FAMILY)
    assert [(v.brands, v.ingredients) for v in variants] == [
        (["Telma H Tablet"], ["hydrochlorothiazide", "telmisartan"]),
        (["Telma-AM Tablet"], ["amlodipine", "telmisartan"]),
    ]
    assert more == 0


def test_family_variants_empty_when_every_product_has_the_same_ingredients() -> None:
    family = [("Dolo 650 Tablet", P), ("Dolo 500 Tablet", P)]
    assert family_variants("Dolo 650", P, family) == ([], 0)


def test_family_variants_are_capped_and_count_the_rest() -> None:
    family = [(f"Zed {i} Tablet", (f"drug{i}",)) for i in range(MAX_VARIANTS + 3)]
    variants, more = family_variants("Zed", ("other",), family)
    assert (len(variants), more) == (MAX_VARIANTS, 3)


def test_group_variants_one_entry_per_ingredient_set() -> None:
    close = [
        ("Brufen 400 Tablet", ("ibuprofen",)),
        ("Brufen MR Soft Gelatin Capsule", ("ibuprofen", "tizanidine")),
        ("Brufen 600 Tablet", ("ibuprofen",)),
    ]
    assert [(v.brands, v.ingredients) for v in group_variants(close)] == [
        (["Brufen 400 Tablet", "Brufen 600 Tablet"], ["ibuprofen"]),
        (["Brufen MR Soft Gelatin Capsule"], ["ibuprofen", "tizanidine"]),
    ]
