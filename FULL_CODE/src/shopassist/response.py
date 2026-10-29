"""Turns a Decision into the shopper-facing text plus structured citations.

Every price, stock status and attribute value is copied from the catalogue row it cites.
Templates only: wording never invents a fact, and every product sentence carries its ID.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shopassist.catalogue import Product
from shopassist.decide import Decision
from shopassist.lexicon import UNSOLD_ITEMS
from shopassist.policy import Policy

STOCK_TEXT = {
    "in_stock": "in stock",
    "low_stock": "in stock, but only a few left (low stock)",
    "out_of_stock": "currently out of stock",
}
SOLD_CATEGORIES = (
    "apparel, footwear, bags & luggage, beauty & personal care, electronics accessories, "
    "home & kitchen, small appliances, sports & fitness, stationery and toys"
)
# brands whose usual spelling is not simple title case
BRAND_SPELLING = {
    "iphone": "iPhone",
    "airpods": "AirPods",
    "boat": "boAt",
    "hp": "HP",
    "lg": "LG",
    "jbl": "JBL",
    "oneplus": "OnePlus",
    "tvs": "TVS",
    "levis": "Levi's",
}
UNIT_SUFFIX = {
    "_mm": " mm",
    "_cm": " cm",
    "_l": " L",
    "_ml": " ml",
    "_w": " W",
    "_mah": " mAh",
    "_hours": " hours",
    "_min": " minutes",
    "_g": " g",
    "_kg": " kg",
    "_in": " inch",
    "_months": " months",
    "_m": " m",
    "_ft": " ft",
}
# boolean attribute -> (how to say "true", how to say "false")
BOOL_PHRASES = {
    "dishwasher_safe": ("is dishwasher safe", "is not dishwasher safe"),
    "microwave_safe": ("is microwave safe", "is not microwave safe"),
    "induction_compatible": ("is induction compatible", "is not induction compatible"),
    "water_resistant": ("is water resistant", "is not water resistant"),
    "paraben_free": ("is paraben free", "is not paraben free"),
    "sulphate_free": ("is sulphate free", "is not sulphate free"),
    "noise_cancellation": ("has noise cancellation (ANC)", "does not have noise cancellation"),
    "has_mic": ("has a mic", "does not have a mic"),
    "auto_shutoff": ("has auto shut-off", "does not have auto shut-off"),
    "shoe_compartment": ("has a shoe compartment", "does not have a shoe compartment"),
    "laptop_compartment": ("has a laptop compartment", "does not have a laptop compartment"),
    "rfid_blocking": ("has RFID blocking", "does not have RFID blocking"),
}


class StatedPrice(BaseModel):
    product_id: str
    price_inr: int


class StatedFact(BaseModel):
    product_id: str
    field: str
    value: Any


class Reply(BaseModel):
    """One assistant turn, in the submission format plus a few fields for the demo UI."""

    action: str
    answer_text: str
    cited_product_ids: list[str] = Field(default_factory=list)
    cited_policy_sections: list[str] = Field(default_factory=list)
    stated_prices: list[StatedPrice] = Field(default_factory=list)
    stated_facts: list[StatedFact] = Field(default_factory=list)
    kind: str = ""
    matched_total: int = 0


# --------------------------------------------------------------------------------------- formatting
def rupees(amount: int | float) -> str:
    return f"₹{int(amount):,}"


def label(p: Product) -> str:
    return f"{p.title} [{p.product_id}]"


def field_name(key: str) -> str:
    for suffix in UNIT_SUFFIX:
        if key.endswith(suffix):
            return key[: -len(suffix)].replace("_", " ")
    return key.replace("_", " ")


def format_value(key: str, value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    for suffix, unit in UNIT_SUFFIX.items():
        if key.endswith(suffix):
            return f"{value}{unit}"
    return str(value)


def budget_phrase(low: float | None, high: float | None) -> str:
    """' between ₹600 and ₹800', ' under ₹800', ' above ₹600' or ''."""
    if low is not None and high is not None:
        return f" between {rupees(low)} and {rupees(high)}"
    if high is not None:
        return f" under {rupees(high)}"
    if low is not None:
        return f" above {rupees(low)}"
    return ""


def _price_stock(p: Product) -> str:
    return f"{rupees(p.price_inr)}, {STOCK_TEXT[p.stock_status]}"


class ResponseBuilder:
    def __init__(self, policy: Policy):
        self.policy = policy

    def build(self, d: Decision) -> Reply:
        builder = getattr(self, f"_{d.kind}")
        text, facts, show_prices = builder(d)
        cited = [p.product_id for p in d.products]
        prices = [
            StatedPrice(product_id=p.product_id, price_inr=p.price_inr) for p in d.products if show_prices
        ]
        return Reply(
            action=d.action,
            answer_text=text,
            cited_product_ids=cited,
            cited_policy_sections=list(d.sections),
            stated_prices=prices,
            stated_facts=facts,
            kind=d.kind,
            matched_total=d.total,
        )

    # ----------------------------------------------------------------------------------- facts
    @staticmethod
    def _stock_fact(p: Product) -> StatedFact:
        return StatedFact(product_id=p.product_id, field="stock_status", value=p.stock_status)

    def _price_facts(self, d: Decision) -> list[StatedFact]:
        facts = [self._stock_fact(p) for p in d.products]
        if d.intent.asks_discount:
            for p in d.products:
                facts += [
                    StatedFact(product_id=p.product_id, field="mrp_inr", value=p.mrp_inr),
                    StatedFact(product_id=p.product_id, field="discount_inr", value=p.discount_inr),
                ]
        return facts

    # ----------------------------------------------------------------------------------- answers
    def _lookup(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        lines = []
        for p in d.products:
            line = f"{label(p)} is {_price_stock(p)}."
            if d.intent.asks_discount:
                line += (
                    f" MRP is {rupees(p.mrp_inr)}, so the discount is {rupees(p.discount_inr)}."
                    if p.discount_inr
                    else " It is sold at MRP, with no discount."
                )
            lines.append(line)
        head = (
            ""
            if len(d.products) == 1
            else (
                f"All {d.total} matching variants have the same "
                f"{'price' if d.intent.asks_price else 'answer'}:\n"
            )
        )
        return head + "\n".join(lines), self._price_facts(d), True

    def _attribute(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        lines, facts = [], []
        for p in d.products:
            key = d.attribute.get(p.product_id)
            if not key:
                continue
            sentence, fact_value = self._attribute_sentence(p, key, d)
            lines.append(sentence)
            facts.append(StatedFact(product_id=p.product_id, field=key, value=fact_value))
        show_prices = d.intent.asks_price or d.intent.asks_stock
        if show_prices:
            lines += [f"It is {_price_stock(p)} [{p.product_id}]." for p in d.products]
            facts += [self._stock_fact(p) for p in d.products]
        return "\n".join(lines), facts, show_prices

    def _attribute_sentence(self, p: Product, key: str, d: Decision) -> tuple[str, Any]:
        value = p.value(key)
        if key == "sizes" and d.intent.asked_size:
            wanted = d.intent.asked_size
            if wanted.lower() in {str(s).lower() for s in value}:
                return f"Yes, {label(p)} is available in size {wanted}.", wanted
            return (
                f"No, {label(p)} does not come in size {wanted}; it comes in {format_value(key, value)}.",
                value,
            )
        if isinstance(value, bool):
            yes, no = BOOL_PHRASES.get(key, (f"has {field_name(key)}", f"does not have {field_name(key)}"))
            return f"{'Yes' if value else 'No'}, {label(p)} {yes if value else no}.", value
        sentence = f"{label(p)}: {field_name(key)} is {format_value(key, value)}."
        for spec in d.intent.asked_numbers:
            if key in spec.keys and isinstance(value, int | float):
                fits = value >= spec.value if spec.at_least else abs(value - spec.value) < 1e-6
                sentence = f"{'Yes' if fits else 'No'}. {sentence}"
        return sentence, value

    def _no_warranty(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        names = "; ".join(label(p) for p in d.products)
        return (
            (
                f"No brand warranty is listed for {names}. As per store policy section 3.1, a product "
                "without a listed warranty period has no brand warranty, but it is still covered by our "
                "30-day return policy (section 1)."
            ),
            [],
            False,
        )

    def _compare(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        lines = [f"- {label(p)}: {_price_stock(p)}" for p in d.products]
        cheapest = d.products[0]
        same = len({p.price_inr for p in d.products}) == 1
        verdict = (
            "They cost the same."
            if same
            else f"The cheaper one is {label(cheapest)} at {rupees(cheapest.price_inr)}."
        )
        return "Here is the comparison:\n" + "\n".join(lines) + "\n" + verdict, self._price_facts(d), True

    def _superlative(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        p = d.products[0]
        word = "cheapest" if d.intent.superlative == "min" else "most expensive"
        scope = f" of the {d.total} matching products" if d.total > 1 else ""
        return f"The {word}{scope} is {label(p)} at {_price_stock(p)}.", self._price_facts(d), True

    def _list(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        head = (
            f"I found {d.total} matching products. Here are {len(d.products)} of them:"
            if d.total > len(d.products)
            else f"I found {d.total} matching products:"
        )
        lines = [f"- {label(p)}: {_price_stock(p)}" for p in d.products]
        tail = "\nTell me a colour, size or budget to narrow it down." if d.total > len(d.products) else ""
        return head + "\n" + "\n".join(lines) + tail, self._price_facts(d), True

    def _policy(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        parts = []
        for sid in d.sections:
            s = self.policy.get(sid)
            if s:
                parts.append(f"As per our store policy, section {s.section_id} ({s.title}): {s.text}")
        return "\n".join(parts), [], False

    # ----------------------------------------------------------------------------------- clarify
    def _clarify(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        differ = self._differences(d)
        head = (
            f"I found {d.total} products that match, and they differ in {differ}, so I don't want to "
            "guess. Which one do you mean?"
        )
        lines, facts = [], [self._stock_fact(p) for p in d.products]
        for i, p in enumerate(d.products, 1):
            line = f"{i}. {label(p)}: {_price_stock(p)}"
            key = d.attribute.get(p.product_id)
            if key:
                line += f"; {field_name(key)}: {format_value(key, p.value(key))}"
                facts.append(StatedFact(product_id=p.product_id, field=key, value=p.value(key)))
            lines.append(line)
        if d.total > len(d.products):
            lines.append(f"(showing {len(d.products)} of {d.total}; tell me the colour, size or brand)")
        return head + "\n" + "\n".join(lines), facts, True

    @staticmethod
    def _differences(d: Decision) -> str:
        diffs = []
        if len({p.price_inr for p in d.products}) > 1:
            diffs.append("price")
        if len({p.stock_status for p in d.products}) > 1:
            diffs.append("stock")
        if d.attribute and len({repr(p.value(d.attribute.get(p.product_id, ""))) for p in d.products}) > 1:
            diffs.append(field_name(next(iter(d.attribute.values()))))
        return " and ".join(diffs) or "their details"

    # ----------------------------------------------------------------------------------- refusals
    def _not_sold(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        if d.reason in UNSOLD_ITEMS:
            return (
                (
                    f"I don't have that. Our store doesn't sell {UNSOLD_ITEMS[d.reason]}; we carry "
                    f"{SOLD_CATEGORIES}."
                ),
                [],
                False,
            )
        return (
            (
                "Sorry, I couldn't find that in our catalogue or store policy. I can help with product "
                f"prices, stock, features and store policies for {SOLD_CATEGORIES}."
            ),
            [],
            False,
        )

    def _real_brand(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        brand = BRAND_SPELLING.get(d.reason, d.reason.title())
        return (
            f"I don't have that. We don't carry {brand} products; our catalogue has only our store brands.",
            [],
            False,
        )

    def _no_match(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        what = d.reason or "that"
        budget = budget_phrase(d.filters.budget_min, d.filters.budget_max) if d.filters else ""
        return (
            (
                f"I don't have that. No product in our catalogue matches {what}{budget}. "
                "Try a different colour, size or budget."
            ),
            [],
            False,
        )

    def _unknown_fact(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        asked = ", ".join(field_name(f[0]) for f in d.intent.asked_fields) or "that"
        names = "; ".join(label(p) for p in d.products)
        return (
            (
                f"Sorry, the catalogue doesn't say this ({asked}) for {names}, so I can't confirm it "
                "and don't want to guess."
            ),
            [],
            False,
        )

    def _policy_gap(self, d: Decision) -> tuple[str, list[StatedFact], bool]:
        return (
            (
                "I don't have that information. Our store policy doesn't cover this, so I can't promise "
                "it. Customer support can help (chat, email or phone, 9 AM to 9 PM)."
            ),
            [],
            False,
        )
