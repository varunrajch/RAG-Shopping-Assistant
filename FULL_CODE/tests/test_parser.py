"""Query understanding: Hinglish, misspelt names, units and budgets."""

import pytest

from shopassist.text import clean, singular, tokenize


@pytest.fixture()
def parse(shared_assistant):
    return shared_assistant.parser.parse


def test_misspelt_and_split_names_match_catalogue(parse):
    q = parse("krida ion flex football rate?")
    assert q.names[0].brand == "kridaa"
    assert q.names[0].line == "ionflex"
    assert q.sub_categories == ("Footballs",)
    assert q.asks_price


def test_joined_line_name_and_colour(parse):
    q = parse("ironnest ripple flex blue yoga mat kitne ki")
    assert q.names[0].line == "rippleflex"
    assert q.colours == ["blue"]
    assert q.names[0].colours == ["blue"]


@pytest.mark.parametrize(
    ("text", "budget"),
    [
        ("TPE wali 600 ke andar", 600.0),
        ("yoga mat under 2k", 2000.0),
        ("mat 1,499 se kam", 1499.0),
        ("budget 900 hai", 900.0),
    ],
)
def test_budget_phrases(parse, text, budget):
    assert parse(text).budget_max == budget


def test_units_become_numeric_filters(parse):
    q = parse("6 mm yoga mat chahiye")
    assert [(s.keys[0], s.value) for s in q.numeric] == [("thickness_mm", 6.0)]
    assert q.budget_max is None


def test_size_question_but_not_cabin_size(parse):
    assert ("sizes",) in parse("set 8-9 saal ke bacche ka size milega?").asked_fields
    assert ("sizes",) not in parse("cabin size trolley bag ka price").asked_fields


def test_superlative_stock_filter_and_compare(parse):
    q = parse("yoga mat sabse sasti jo stock me ho")
    assert q.superlative == "min" and q.in_stock_only and not q.asks_stock
    c = parse("chargit quillbolt red ya blue earphones kaunsa sasta")
    assert c.compare and c.colours == ["red", "blue"]


def test_out_of_catalogue_signals(parse):
    assert parse("nike running shoes hai kya").real_brand == "nike"
    q = parse("silver payal dikhao")
    assert q.unsold_item == "payal" and not q.sub_categories


def test_attribute_questions_map_to_catalogue_keys(parse):
    assert ("thickness_mm",) in parse("vistaair mat kitni moti hai").asked_fields
    assert ("induction_compatible",) in parse("dunetrek kadai induction pe chalegi?").asked_fields
    assert ("charging_time",) in parse("earbuds full charge hone me kitna time").asked_fields


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("shoes", "shoe"),
        ("kurtas", "kurta"),
        ("boxes", "box"),
        ("plus", "plus"),
        ("glass", "glass"),
        ("batteries", "battery"),
    ],
)
def test_singular(word, expected):
    assert singular(word) == expected


def test_clean_and_tokenize_edge_cases():
    assert tokenize("") == []
    assert tokenize("100ml IPX7 8-9 saal") == ["100", "ml", "ipx7", "8-9", "saal"]
    assert "2000" in clean("under 2k")
    assert "449000" not in clean("₹449 k andar")  # 'k' only means thousand when attached


def test_litres_also_match_millilitre_attributes(parse):
    spec = parse("1 litre bottle").numeric[0]
    assert spec.value_for("capacity_l") == 1.0 and spec.value_for("capacity_ml") == 1000.0


def test_water_words_only_mean_water_resistance_when_asked_that_way(parse):
    water = ("water_resistance_rating", "water_resistant")
    assert water in parse("speaker paani me chalega?").asked_fields
    assert water not in parse("pani peene ki bottle 1 litre wali").asked_fields
    assert parse("airpods jaisa kuch hai?").real_brand == "airpods"


def test_material_word_becomes_product_type_when_nothing_else_names_one(parse):
    assert parse("cheap iron for pressing clothes").sub_categories == ("Irons",)


def test_everyday_word_that_is_also_a_brand_is_not_a_product_name(parse):
    q = parse("pair se maarne wali kridaa cheez")  # 'kridaa' is a brand, the rest is not understood
    assert q.names == [] and "kridaa" in q.unknown_words
    assert parse("kridaa football price").names[0].brand == "kridaa"  # with a product type it is a brand
