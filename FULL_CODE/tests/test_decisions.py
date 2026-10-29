"""Answer / clarify / refuse rules (README section 6) on the synthetic fixture store."""


def ask(assistant, text, conversation="c"):
    return assistant.ask(text, conversation_id=conversation).reply


def test_single_product_answer_states_catalogue_price_and_stock(assistant):
    r = ask(assistant, "Chargit QuillBolt red earphones kitne ke")
    assert r.action == "answer"
    assert r.cited_product_ids == ["SKU-TEST0011"]
    assert [(p.product_id, p.price_inr) for p in r.stated_prices] == [("SKU-TEST0011", 249)]
    assert "₹249" in r.answer_text


def test_variants_with_same_price_are_answered_not_clarified(assistant):
    r = ask(assistant, "chargit quillbolt earphones price")
    assert r.action == "answer"
    assert set(r.cited_product_ids) == {"SKU-TEST0011", "SKU-TEST0012"}


def test_variants_that_differ_in_price_need_clarification(assistant):
    r = ask(assistant, "krida ion flex football rate?")
    assert r.action == "clarify"
    assert set(r.cited_product_ids) == {"SKU-TEST0005", "SKU-TEST0006"}
    assert {p.price_inr for p in r.stated_prices} == {559, 519}


def test_follow_up_turn_narrows_previous_candidates(assistant):
    first = ask(assistant, "strikeforce vistaair yoga mat kitne ki hai", "conv")
    assert first.action == "clarify"
    second = ask(assistant, "lavender wali", "conv")
    assert second.action == "answer"
    assert second.cited_product_ids == ["SKU-TEST0002"]
    facts = {(f.field, f.value) for f in second.stated_facts}
    assert ("stock_status", "out_of_stock") in facts


def test_multi_turn_budget_and_material_carry_over(assistant):
    ask(assistant, "6 mm yoga mat chahiye", "mt")
    r = ask(assistant, "TPE wali 600 ke andar", "mt")
    assert r.action == "answer" and r.cited_product_ids == ["SKU-TEST0004"]


def test_superlative_respects_in_stock_request(assistant):
    r = ask(assistant, "yoga mat sabse sasti jo stock me ho")
    assert r.cited_product_ids == ["SKU-TEST0004"]  # cheapest overall that is not out of stock


def test_false_attribute_is_a_grounded_no(assistant):
    r = ask(assistant, "Sootli DuneTrek 26 cm kadai induction pe chalegi?")
    assert r.action == "answer"
    assert r.stated_facts[0].field == "induction_compatible" and r.stated_facts[0].value is False


def test_true_attribute_answer(assistant):
    r = ask(assistant, "yatrik vega dash brown duffel me shoe compartment hai?")
    assert r.action == "answer" and r.stated_facts[0].value is True


def test_missing_attribute_is_refused_not_guessed(assistant):
    r = ask(assistant, "Trailnest DriftAir pink running shoe water resistant hai?")
    assert r.action == "refuse"
    assert r.stated_facts == []


def test_missing_warranty_means_no_warranty_per_policy(assistant):
    r = ask(assistant, "trekora nimbus wave cabin trolley pe warranty hai kya")
    assert r.action == "answer"
    assert r.cited_policy_sections == ["3.1"]


def test_listed_warranty_is_answered(assistant):
    r = ask(assistant, "pavana zephyr fusion toaster warranty kitni hai")
    assert r.action == "answer"
    assert (r.stated_facts[0].field, r.stated_facts[0].value) == ("warranty_months", 24)


def test_out_of_catalogue_and_real_brands_are_refused(assistant):
    for text in ("redmi note 13 price", "silver payal dikhao", "maggi noodles 12 pack", "nike running shoes"):
        r = ask(assistant, text, text)
        assert r.action == "refuse", text
        assert r.cited_product_ids == [] and r.stated_prices == []


def test_no_product_satisfies_constraints(assistant):
    assert ask(assistant, "10 litre toaster hai?").action == "refuse"


def test_policy_question_cites_sub_section(assistant):
    r = ask(assistant, "earbuds ki seal khol di, return ho jayega?")
    assert r.action == "answer" and r.cited_policy_sections == ["6.2"]


def test_policy_gap_is_refused(assistant):
    assert ask(assistant, "credit card pe EMI milega?").action == "refuse"


def test_list_request_cites_only_matching_products(assistant):
    r = ask(assistant, "6 mm yoga mat dikhao")
    assert r.action == "answer"
    assert set(r.cited_product_ids) == {"SKU-TEST0003", "SKU-TEST0004"}


def test_discount_question_states_discount_fact(assistant):
    r = ask(assistant, "pavana zephyr fusion toaster pe kitna discount hai")
    fields = {f.field: f.value for f in r.stated_facts}
    assert fields["discount_inr"] == 0 and fields["mrp_inr"] == 1499


def test_new_unrelated_question_is_not_treated_as_follow_up(assistant):
    ask(assistant, "6 mm yoga mat dikhao", "topic")
    r = ask(assistant, "smart watch under 3000", "topic")
    assert r.action == "refuse" and r.cited_product_ids == []
    assert ask(assistant, "airpods jaisa kuch hai?", "topic").action == "refuse"


def test_colour_word_is_ignored_for_products_without_colours(assistant):
    r = ask(assistant, "teal toaster dikhao")  # toasters in the fixture are white; 'teal' rules them out
    assert r.action == "refuse"
    r = ask(assistant, "pink kadai dikhao", "k")  # kadais have no colour attribute at all
    assert r.action == "answer" and r.cited_product_ids == ["SKU-TEST0009"]
