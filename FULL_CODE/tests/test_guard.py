"""The price guard must remove any amount or claim the catalogue does not back."""

from shopassist.guard import rupee_amounts, shopper_numbers
from shopassist.response import Reply, StatedFact, StatedPrice


def test_rupee_amount_detection_matches_scorer_rules():
    found = [a for a, _ in rupee_amounts("₹1,299 or Rs.499 or 2k rupees or 1299/- and 65W")]
    assert found == [1299.0, 499.0, 2000.0, 1299.0]


def test_shopper_budget_counts_but_measurements_do_not():
    nums = shopper_numbers(["65W charger 600 ke andar"])
    assert 600.0 in nums and 65.0 not in nums


def test_invented_text_price_is_removed(shared_assistant):
    reply = Reply(
        action="answer", answer_text="It costs ₹249, or ₹199 on sale.", cited_product_ids=["SKU-TEST0011"]
    )
    clean, removed = shared_assistant.guard.enforce(reply, ["quillbolt price"])
    assert "₹249" in clean.answer_text
    assert "₹199" not in clean.answer_text and "[price removed]" in clean.answer_text
    assert removed


def test_budget_typed_by_shopper_is_allowed(shared_assistant):
    reply = Reply(action="answer", answer_text="Mats under ₹600:", cited_product_ids=["SKU-TEST0004"])
    clean, removed = shared_assistant.guard.enforce(reply, ["yoga mat 600 ke andar"])
    assert clean.answer_text == "Mats under ₹600:" and removed == []


def test_structured_claims_about_uncited_or_wrong_values_are_dropped(shared_assistant):
    reply = Reply(
        action="answer",
        answer_text="x",
        cited_product_ids=["SKU-TEST0011", "SKU-NOTREAL1"],
        stated_prices=[
            StatedPrice(product_id="SKU-TEST0011", price_inr=250),
            StatedPrice(product_id="SKU-TEST0012", price_inr=249),
        ],
        stated_facts=[StatedFact(product_id="SKU-TEST0011", field="water_resistant", value=True)],
    )
    clean, removed = shared_assistant.guard.enforce(reply, [])
    assert clean.cited_product_ids == ["SKU-TEST0011"]
    assert clean.stated_prices == [] and clean.stated_facts == []
    assert len(removed) == 4


def test_policy_amounts_allowed_only_when_policy_is_cited(shared_assistant):
    text = "Free delivery from ₹499."
    with_policy, removed = shared_assistant.guard.enforce(
        Reply(action="answer", answer_text=text, cited_policy_sections=["2.1"]), []
    )
    assert with_policy.answer_text == text and not removed
    without, _ = shared_assistant.guard.enforce(Reply(action="answer", answer_text=text), [])
    assert "₹499" not in without.answer_text
