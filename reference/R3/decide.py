"""
decide.py
Chooses what kind of reply to give. Only three outcomes are possible:
  answer   - one clear match, the cheapest match, a list the shopper asked for,
             or a policy section that covers the question
  clarify  - several close matches that differ on price or a key attribute;
             we list up to 3 options with IDs and ask which one
  refuse   - "I don't have that" when the catalogue or the policy does not
             support an answer, with the nearest category we do sell
"""
from dataclasses import dataclass, field

import config
from search import nearest_category, search_policy


@dataclass
class Decision:
    kind: str                                    # answer | clarify | refuse
    mode: str                                    # single | list | cheapest | options | policy |
                                                 # not_sold | no_match | policy_missing
    rows: list = field(default_factory=list)     # catalogue row positions to show
    sections: list = field(default_factory=list) # policy sections to quote
    total: int = 0                               # how many products matched
    nearest: tuple = None                        # (category, sub_category) we do sell
    differ_on: list = field(default_factory=list)
    refine: tuple = None                         # (attribute, values) to ask about when clarifying


def decide_policy(index, parsed):
    section, _, cos, bm = search_policy(index, parsed.text)[0]
    # No shared words, or too far in meaning: the policy does not cover it.
    if bm <= 0 or cos < config.POLICY_MIN_COS:
        return Decision("refuse", "policy_missing")
    return Decision("answer", "policy", sections=[section])


def decide_product(index, parsed, filters, result):
    df = index.df
    no_category = not filters.get("category")

    # Words we do not sell ("iphone", "laptop") and no category: refuse.
    if no_category and parsed.unknown_words and not parsed.named_words:
        return Decision("refuse", "not_sold", nearest=nearest_category(index, parsed.original,
                                                                parsed.unknown_words))
    # The language model guessed the category: double check the meaning is close.
    if parsed.category_from_llm and (len(result.rows) == 0 or result.cos[0] < config.LLM_RELEVANCE_MIN):
        return Decision("refuse", "not_sold", nearest=nearest_category(index, parsed.original,
                                                                parsed.unknown_words))

    rows, n = list(result.rows), len(result.rows)
    if n == 0:
        return Decision("refuse", "no_match", nearest=nearest_category(index, parsed.text))

    if parsed.wants_cheapest:
        prices = df.price.to_numpy()[rows]
        return Decision("answer", "cheapest", rows=[rows[int(prices.argmin())]], total=n)
    if parsed.wants_list:
        return Decision("answer", "list", rows=rows[:config.MAX_LIST_ITEMS], total=n)
    if n == 1 or result.score[0] - result.score[1] >= config.CLEAR_MATCH_MARGIN:
        return Decision("answer", "single", rows=[rows[0]], total=n)

    options = _pick_options(df, rows[:20])
    differ = [c for c in ["price", "brand", "material", "colour", "size"]
              if df.iloc[options][c].nunique() > 1]
    return Decision("clarify", "options", rows=options, total=n, differ_on=differ,
                    refine=_refine_question(df, rows))


def _pick_options(df, rows):
    """From the top matches pick the cheapest, a middle one and the dearest,
    so the options clearly differ on price."""
    by_price = sorted(rows, key=lambda r: df.price.iat[r])
    if len(by_price) <= config.MAX_CLARIFY_OPTIONS:
        return by_price
    picks = [by_price[0], by_price[len(by_price) // 2], by_price[-1]]
    return list(dict.fromkeys(picks))


def _refine_question(df, rows):
    """The attribute that best splits the matches (e.g. material), with its most
    common values, so the clarifying question can offer real choices."""
    matches = df.iloc[rows]
    for attr in ["material", "colour", "brand", "size"]:
        values = matches[attr].value_counts().index[:4].tolist()
        if len(values) > 1:
            return attr, values
    return None
