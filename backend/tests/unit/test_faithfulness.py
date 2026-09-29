"""Faithfulness scoring (RAGAS method): claims are split, checked by number,
and a claim the verifier skips counts as unsupported."""

from graph_fakes import FakeModels

from etheria.graph.faithfulness import Check, Claims, Faithfulness, Verification, faithfulness


async def test_score_is_supported_over_all_claims() -> None:
    models = FakeModels(
        structured={
            "audit": [
                Claims(claims=["TSH is 7.8", "TSH above 4.2 is high", "Levothyroxine is safe"]),
                Verification(
                    checks=[
                        Check(number=1, supported=True),
                        Check(number=2, supported=True),
                        Check(number=3, supported=False, note="not in the context"),
                    ]
                ),
            ]
        }
    )
    f = await faithfulness(models, "What is my TSH?", "reply", "TSH 7.8 (0.4-4.2)")
    assert f.score == 2 / 3
    assert [v.claim for v in f.unsupported] == ["Levothyroxine is safe"]


async def test_a_skipped_claim_is_unsupported() -> None:
    models = FakeModels(
        structured={
            "audit": [
                Claims(claims=["a", "b"]),
                Verification(checks=[Check(number=1, supported=True)]),
            ]
        }
    )
    f = await faithfulness(models, "q", "reply", "ctx")
    assert f.score == 0.5
    assert f.unsupported[0].note == "not checked by the verifier"


async def test_no_claims_has_no_score() -> None:
    models = FakeModels(structured={"audit": [Claims(claims=[])]})
    f = await faithfulness(models, "thanks", "You're welcome.", "ctx")
    assert f.score is None
    assert models.calls["audit"] == 1
    assert Faithfulness().unsupported == []
