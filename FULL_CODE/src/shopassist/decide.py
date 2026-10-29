"""The decision step: answer, clarify or refuse (README section 6), made entirely in code.

answer   one product (or all matches share what was asked), a superlative, a comparison,
         a "show me" list, a grounded "no", or a policy sub-section
clarify  the shopper means ONE product, several match, and they differ in what was asked
refuse   nothing we sell matches, or the catalogue / policy does not contain the fact
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from shopassist import lexicon as lx
from shopassist.catalogue import Catalogue, Product
from shopassist.config import DecisionSettings
from shopassist.filters import Filters, apply, matches
from shopassist.parser import NameMention, NumericSpec, ParsedQuery
from shopassist.policy import Policy
from shopassist.policy_router import route_policy
from shopassist.text import singular

WARRANTY_SECTION = "3.1"


@dataclass(frozen=True)
class Intent:
    """What the shopper wants to know; kept between turns so 'lavender wali' inherits 'kitne ki hai'."""

    asks_price: bool = False
    asks_stock: bool = False
    asks_discount: bool = False
    asked_fields: tuple[tuple[str, ...], ...] = ()
    superlative: str | None = None
    explicit_list: bool = False
    asked_size: str | None = None
    asked_numbers: tuple[NumericSpec, ...] = ()

    @classmethod
    def from_query(cls, q: ParsedQuery) -> Intent:
        asked_keys = {k for fields in q.asked_fields for k in fields}
        return cls(
            asks_price=q.asks_price,
            asks_stock=q.asks_stock,
            asks_discount=q.asks_discount,
            asked_fields=tuple(q.asked_fields),
            superlative=q.superlative,
            explicit_list=bool(lx.EXPLICIT_LIST_RE.search(q.text)) or bool(q.budget_max),
            asked_size=q.sizes[0] if q.sizes and ("sizes",) in q.asked_fields else None,
            asked_numbers=tuple(s for s in q.numeric if set(s.keys) & asked_keys),
        )

    @property
    def is_empty(self) -> bool:
        return not (
            self.asks_price
            or self.asks_stock
            or self.asks_discount
            or self.asked_fields
            or self.superlative
            or self.explicit_list
        )

    @property
    def wants_one(self) -> bool:
        """The shopper asks about one product (its price, stock, a feature), not for a list."""
        return (
            bool(self.asks_price or self.asks_stock or self.asks_discount or self.asked_fields)
            and not self.explicit_list
        )

    @property
    def skip_filter_keys(self) -> set[str]:
        return {k for fields in self.asked_fields for k in fields}

    def without_filtered_questions(self, filters: Filters) -> Intent:
        """In a request without a product name, '2000 watt' or 'IPX7 wala' is a filter, not a question."""
        keys = {k for s in filters.numeric for k in s.keys} | {k for k, _ in filters.values}
        keys |= set(filters.booleans)
        kept = tuple(f for f in self.asked_fields if not set(f) & keys)
        if kept == self.asked_fields:
            return self
        return Intent(**{**vars(self), "asked_fields": kept, "asked_numbers": ()})


@dataclass
class ConversationState:
    """Per-conversation memory used to interpret follow-up turns."""

    filters: Filters | None = None
    candidate_ids: list[str] = field(default_factory=list)
    intent: Intent | None = None
    texts: list[str] = field(default_factory=list)  # every shopper message so far


@dataclass
class Decision:
    action: str  # answer | clarify | refuse
    kind: str  # lookup, attribute, compare, superlative, list, clarify,
    # policy, no_warranty, not_sold, real_brand, no_match,
    # unknown_fact, policy_gap
    products: list[Product] = field(default_factory=list)
    sections: tuple[str, ...] = ()
    intent: Intent = field(default_factory=Intent)
    attribute: dict[str, str] = field(default_factory=dict)  # product_id -> attribute key answered
    total: int = 0  # how many products matched
    filters: Filters | None = None
    reason: str = ""  # word shown in a refusal ("iphone", "Nike")
    candidates: list[Product] = field(default_factory=list)  # remembered for follow-up turns


class Decider:
    def __init__(self, catalogue: Catalogue, policy: Policy, settings: DecisionSettings):
        self.catalogue = catalogue
        self.policy = policy
        self.settings = settings

    # ------------------------------------------------------------------------------------- entry
    def decide(self, q: ParsedQuery, state: ConversationState) -> Decision:
        intent = Intent.from_query(q)
        if q.real_brand:
            return Decision("refuse", "real_brand", reason=q.real_brand, intent=intent)
        if q.policy_like and not q.has_line:
            route = route_policy(q.text, self.policy)
            if route and route.gap:
                return Decision("refuse", "policy_gap", intent=intent)
            if route:
                return Decision("answer", "policy", sections=route.sections, intent=intent)
        if self.is_followup(q, state):
            return self._refine(q, intent, state)
        if q.unsold_item and not q.sub_categories:
            return Decision("refuse", "not_sold", reason=q.unsold_item, intent=intent)
        if not q.sub_categories and not q.has_name:
            return Decision("refuse", "not_sold", intent=intent)
        if q.has_line:
            return self._named(q, intent)
        filters = Filters.from_query(q)
        if state.filters and q.sub_categories and state.candidate_ids:
            filters = state.filters.carried_to_new_topic().refined_by(filters)
        matched = apply(self.catalogue.products, filters)
        return self._choose(matched, intent.without_filtered_questions(filters), filters)

    def is_followup(self, q: ParsedQuery, state: ConversationState) -> bool:
        """A turn refines the previous results only if it reads like a refinement: it points back
        ("inme"), adds a product constraint ("lavender wali", "3 litre wala"), or is a bare budget /
        question with no new item in it. "smart watch under 3000" after a bottle search is a new topic."""
        if not state.candidate_ids or q.has_line:
            return False
        if q.refers_to_previous:
            return True
        if q.sub_categories:
            return False
        if q.colours or q.materials or q.numeric or q.values or q.booleans or q.sizes or q.gender:
            return True
        if q.unsold_item or q.unknown_words:
            return False
        return q.has_name or q.budget_max is not None or not Intent.from_query(q).is_empty

    # ------------------------------------------------------------------------------------- follow-up
    def _refine(self, q: ParsedQuery, intent: Intent, state: ConversationState) -> Decision:
        """Apply this turn's constraints to the products the previous turn found."""
        if intent.is_empty and state.intent:
            intent = Intent(
                **{
                    **vars(state.intent),
                    "asked_numbers": intent.asked_numbers,
                    "asked_size": intent.asked_size or state.intent.asked_size,
                }
            )
        elif state.intent and not (intent.explicit_list or intent.wants_one or intent.superlative):
            intent = Intent(**{**vars(intent), "explicit_list": state.intent.explicit_list})
        pool = [p for p in (self.catalogue.get(i) for i in state.candidate_ids) if p]
        new = Filters.from_query(q)
        new.sub_categories = ()
        matched = apply(pool, new)
        merged = (state.filters or Filters()).refined_by(new)
        return self._choose(matched, intent.without_filtered_questions(new), merged)

    # ------------------------------------------------------------------------------------- named
    def _named(self, q: ParsedQuery, intent: Intent) -> Decision:
        mentions = [m for m in q.names if m.line]
        groups = [self._resolve(m, q, intent, single=len(mentions) == 1) for m in mentions]
        products = list(dict.fromkeys(p for g in groups for p in g))
        if not products:
            return Decision(
                "refuse",
                "no_match",
                intent=intent,
                reason=" ".join(filter(None, [mentions[0].brand, mentions[0].line, *q.colours])),
            )
        if q.compare and len(products) >= 2:
            ranked = sorted(products, key=lambda p: (p.price_inr, p.product_id))
            return Decision(
                "answer",
                "compare",
                products=ranked[: self.settings.max_cited_products],
                intent=intent,
                total=len(products),
                candidates=products,
            )
        return self._choose(products, intent, None)

    def _resolve(self, m: NameMention, q: ParsedQuery, intent: Intent, single: bool) -> list[Product]:
        """Variants of a named product line, narrowed by what the shopper said about them."""
        pool = self._line_products(m)
        pool = _soft(pool, lambda p: p.sub_category in q.sub_categories, bool(q.sub_categories))
        pool = _soft(pool, lambda p: set(m.model_tokens) <= p.model_tokens, bool(m.model_tokens))
        colours = m.colours or (q.colours if single else [])
        if colours and any(p.colour for p in pool):
            pool = [p for p in pool if (p.colour or "").lower() in colours]
        specs = [s for s in q.numeric if s not in intent.asked_numbers]
        hard = Filters(numeric=[s for s in specs if any(k in p.attributes for p in pool for k in s.keys)])
        pool = [p for p in pool if matches(p, hard)]
        soft = Filters(materials=q.materials, gender=q.gender, values=q.values)
        return _soft(pool, lambda p: matches(p, soft), not soft.is_empty())

    def _line_products(self, m: NameMention) -> list[Product]:
        def same_line(p: Product) -> bool:
            return not m.line or singular(p.line) == m.line

        def same_brand(p: Product) -> bool:
            return not m.brand or singular(p.brand.lower()) == m.brand

        pool = [p for p in self.catalogue.products if same_line(p) and same_brand(p)]
        if not pool and m.brand:  # the brand was probably misheard; trust the product-line word
            pool = [p for p in self.catalogue.products if same_line(p)]
        return pool

    # ------------------------------------------------------------------------------------- choose
    def _choose(self, matched: list[Product], intent: Intent, filters: Filters | None) -> Decision:
        """Pick the action for a set of matching products."""
        total = len(matched)
        if not matched:
            return Decision(
                "refuse",
                "no_match",
                intent=intent,
                filters=filters,
                reason=filters.describe() if filters else "",
            )
        if intent.superlative:
            if intent.superlative == "min":
                best = min(matched, key=lambda p: (p.price_inr, p.stock_status == "out_of_stock"))
            else:
                best = max(matched, key=lambda p: (p.price_inr, p.stock_status != "out_of_stock"))
            return Decision(
                "answer",
                "superlative",
                products=[best],
                intent=intent,
                total=total,
                filters=filters,
                candidates=matched,
            )
        if len(matched) == 1:
            return self._single(matched[0], intent, filters, matched)
        if not intent.wants_one:
            shown = _sorted_for_display(matched)[: self.settings.max_list_items]
            return Decision(
                "answer",
                "list",
                products=shown,
                intent=intent,
                total=total,
                filters=filters,
                candidates=matched,
            )
        return self._one_of_many(matched, intent, filters)

    def _single(
        self, p: Product, intent: Intent, filters: Filters | None, candidates: list[Product]
    ) -> Decision:
        if not intent.asked_fields:
            return Decision(
                "answer",
                "lookup",
                products=[p],
                intent=intent,
                total=1,
                filters=filters,
                candidates=candidates,
            )
        key = self._answer_key(p, intent)
        if key is None:
            return self._unknown_fact([p], intent, filters, candidates)
        return Decision(
            "answer",
            "attribute",
            products=[p],
            intent=intent,
            total=1,
            filters=filters,
            attribute={p.product_id: key},
            candidates=candidates,
        )

    def _one_of_many(self, matched: list[Product], intent: Intent, filters: Filters | None) -> Decision:
        """Several products match one request: answer if they agree on what was asked, else clarify."""
        keys = {p.product_id: self._answer_key(p, intent) for p in matched} if intent.asked_fields else {}
        if intent.asked_fields and all(k is None for k in keys.values()):
            return self._unknown_fact(matched, intent, filters, matched)

        def asked_value(p: Product) -> tuple:
            out: list = []
            if intent.asks_price or intent.asks_discount or not (intent.asked_fields or intent.asks_stock):
                out += [p.price_inr, p.mrp_inr if intent.asks_discount else 0]
            if intent.asks_stock:
                out.append(p.stock_status)
            if intent.asked_fields:
                key = keys[p.product_id]
                out.append(repr(p.value(key)) if key else None)
            return tuple(out)

        if len({asked_value(p) for p in matched}) == 1:
            cited = _sorted_for_display(matched)[: self.settings.max_same_answer_citations]
            kind = "attribute" if intent.asked_fields else "lookup"
            return Decision(
                "answer",
                kind,
                products=cited,
                intent=intent,
                total=len(matched),
                filters=filters,
                attribute={k: v for k, v in keys.items() if v},
                candidates=matched,
            )
        options = _spread(matched, self.settings.max_clarify_options)
        return Decision(
            "clarify",
            "clarify",
            products=options,
            intent=intent,
            total=len(matched),
            filters=filters,
            attribute={k: v for k, v in keys.items() if v},
            candidates=matched,
        )

    def _unknown_fact(
        self, products: list[Product], intent: Intent, filters: Filters | None, candidates: list[Product]
    ) -> Decision:
        cited = products[: self.settings.max_same_answer_citations]
        if any("warranty_months" in f for f in intent.asked_fields):
            # policy 3.1: no warranty period listed means no brand warranty -- a grounded answer
            return Decision(
                "answer",
                "no_warranty",
                products=cited,
                sections=(WARRANTY_SECTION,),
                intent=intent,
                total=len(products),
                filters=filters,
                candidates=candidates,
            )
        return Decision(
            "refuse",
            "unknown_fact",
            products=cited,
            intent=intent,
            total=len(products),
            filters=filters,
            candidates=candidates,
        )

    @staticmethod
    def _answer_key(p: Product, intent: Intent) -> str | None:
        for fields in intent.asked_fields:
            for f in fields:
                if p.value(f) is not None:
                    return f
        return None


def _soft(pool: list[Product], keep: Callable[[Product], bool], active: bool) -> list[Product]:
    """Narrow only if something survives: a soft preference, not a hard constraint."""
    if not active:
        return pool
    narrowed = [p for p in pool if keep(p)]
    return narrowed or pool


def _sorted_for_display(products: list[Product]) -> list[Product]:
    return sorted(products, key=lambda p: (p.stock_status == "out_of_stock", p.price_inr, p.product_id))


def _spread(products: list[Product], limit: int) -> list[Product]:
    """Up to `limit` options across the price range, so a clarifying list shows real differences."""
    ranked = sorted(products, key=lambda p: (p.price_inr, p.product_id))
    if len(ranked) <= limit:
        return ranked
    step = (len(ranked) - 1) / (limit - 1)
    return [ranked[round(i * step)] for i in range(limit)]
