"""Last line of defence against invented prices and citations.

Re-checks a Reply with the same rules the scorer uses (README 8.2): every rupee amount in the text
must be the price / MRP / discount of a cited product, a policy amount (when policy is cited) or a
number the shopper typed. Anything else is removed and logged, never shown.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from shopassist.catalogue import Catalogue
from shopassist.response import Reply

logger = logging.getLogger(__name__)

_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
CURRENCY_RE = re.compile(
    r"(?:₹|₨|\brs|\binr|\brup(?:ee|ees|aye|aiye|aiya|eya|iya|ye|yon)\b)[\s.:\-]*([0-9][0-9,]*(?:\.[0-9]+)?)"
    r"(k(?![a-z]))?|([0-9][0-9,]*(?:\.[0-9]+)?)(k(?![a-z]))?\s*(?:/-|rs\b\.?|inr\b|rup[aei]\w*)",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(
    r"([0-9][0-9,]*(?:\.[0-9]+)?)(k(?![a-z]))?(\s*(?:w|watt|mm|cm|inch|in|l|ltr|litre|"
    r"liter|ml|kg|g|mah|pcs|pieces?|gb|ton|saal|years?|y|spf|x|tc)\b)?",
    re.IGNORECASE,
)
POLICY_AMOUNT_RE = re.compile(r"₹\s?([0-9][0-9,]*)")
TOLERANCE = 0.5


def _num(digits: str, k: str | None) -> float:
    value = float(digits.replace(",", ""))
    return value * 1000 if k else value


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").translate(_DEVANAGARI)


def rupee_amounts(text: str) -> list[tuple[float, str]]:
    """(amount, matched text) for every rupee amount written in the text."""
    out = []
    for m in CURRENCY_RE.finditer(_normalise(text)):
        digits, k = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        out.append((_num(digits, k), m.group(0)))
    return out


def shopper_numbers(texts: list[str]) -> set[float]:
    """Budget-like numbers the shopper typed (measurements such as '65W' do not count)."""
    nums: set[float] = set()
    for t in texts:
        for m in NUMBER_RE.finditer(_normalise(t)):
            if m.group(3):
                continue
            try:
                nums.update({_num(m.group(1), m.group(2)), _num(m.group(1), None)})
            except ValueError:
                continue
    return nums


def policy_amounts(policy_markdown: str) -> set[float]:
    return {_num(m.group(1), None) for m in POLICY_AMOUNT_RE.finditer(policy_markdown)}


class PriceGuard:
    def __init__(self, catalogue: Catalogue, policy_money: set[float]):
        self.catalogue = catalogue
        self.policy_money = policy_money

    def allowed(self, reply: Reply, conversation: list[str]) -> set[float]:
        amounts = shopper_numbers(conversation)
        if reply.cited_policy_sections:
            amounts |= self.policy_money
        for pid in reply.cited_product_ids:
            p = self.catalogue.get(pid)
            if p:
                amounts |= {p.price_inr, p.mrp_inr, p.discount_inr}
        return amounts

    def enforce(self, reply: Reply, conversation: list[str]) -> tuple[Reply, list[str]]:
        """Return a reply with every unsupported price or citation removed, plus what was removed."""
        removed: list[str] = []
        cited = [pid for pid in dict.fromkeys(reply.cited_product_ids) if self.catalogue.get(pid)]
        removed += [f"unknown product {pid}" for pid in reply.cited_product_ids if pid not in cited]
        cited_set = set(cited)
        prices = []
        for sp in reply.stated_prices:
            p = self.catalogue.get(sp.product_id)
            if p and sp.product_id in cited_set and abs(sp.price_inr - p.price_inr) <= TOLERANCE:
                prices.append(sp)
            else:
                removed.append(f"stated price {sp.product_id}={sp.price_inr}")
        facts = []
        for sf in reply.stated_facts:
            p = self.catalogue.get(sf.product_id)
            if p and sf.product_id in cited_set and p.value(sf.field) is not None:
                facts.append(sf)
            else:
                removed.append(f"stated fact {sf.product_id}.{sf.field}")
        clean = reply.model_copy(
            update={"cited_product_ids": cited, "stated_prices": prices, "stated_facts": facts}
        )
        allowed = self.allowed(clean, conversation)
        text = clean.answer_text
        for amount, raw in rupee_amounts(text):
            if not any(abs(amount - a) <= TOLERANCE for a in allowed):
                text = text.replace(raw, "[price removed]")
                removed.append(f"text amount {raw!r}")
        if removed:
            logger.warning("guard removed unsupported claims: %s", removed)
        return clean.model_copy(update={"answer_text": text}), removed
