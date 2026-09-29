"""What the medicine tools tell the model about a name (spec 4.5): each product
behind an ambiguous name, and same-name products with other ingredients."""

from etheria.graph.tools import _medicine_evidence
from etheria.knowledge.resolver import BrandVariant, Resolution
from etheria.safety.stream_guard import StreamGuard


def _hits(text: str) -> list[str]:
    guard = StreamGuard(max_chars=100_000, max_wait_s=float("inf"))
    guard.feed(text)
    guard.flush()
    return guard.hits


def test_ambiguous_name_says_what_each_product_contains() -> None:
    r = Resolution(
        query="Brufen",
        status="ambiguous",
        candidates=["Brufen 400 Tablet", "Brufen MR Soft Gelatin Capsule"],
        shared_ingredients=["Ibuprofen"],
        variants=[
            BrandVariant(brands=["Brufen 400 Tablet"], ingredients=["ibuprofen"]),
            BrandVariant(
                brands=["Brufen MR Soft Gelatin Capsule"], ingredients=["ibuprofen", "tizanidine"]
            ),
        ],
    )
    text = _medicine_evidence("Brufen", r, "resolve_medicine").text
    assert "Brufen MR Soft Gelatin Capsule (ibuprofen + tizanidine)" in text
    assert "all of them contain Ibuprofen, which was checked" in text
    assert "not checked" in text
    assert _hits(text) == []


def test_matched_brand_names_same_name_products_with_other_ingredients() -> None:
    r = Resolution(
        query="Telma 40",
        status="resolved",
        matched_brand="Telma 40 Tablet",
        ingredients=["Telmisartan"],
        variants=[
            BrandVariant(
                brands=["Telma H Tablet"], ingredients=["hydrochlorothiazide", "telmisartan"]
            )
        ],
        more_variants=4,
    )
    text = _medicine_evidence("Telma 40", r, "check_interactions").text
    assert text.startswith("Telma 40 contains Telmisartan (brand Telma 40 Tablet)")
    assert "Telma H Tablet (hydrochlorothiazide + telmisartan)" in text
    assert "and 4 more combinations" in text
    assert "Only the ingredients of Telma 40 Tablet were checked" in text
    assert _hits(text) == []


def test_matched_brand_without_variants_is_one_line() -> None:
    r = Resolution(
        query="Dolo 650", status="resolved", matched_brand="Dolo 650 Tablet", ingredients=["X"]
    )
    assert (
        _medicine_evidence("Dolo 650", r, "t").text == "Dolo 650 contains X (brand Dolo 650 Tablet)"
    )
