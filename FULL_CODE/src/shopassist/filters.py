"""Structured product filters. All filtering, counting and min/max is done here in code, never by an LLM."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from shopassist.catalogue import Product
from shopassist.parser import MATERIAL_KEYS, NumericSpec, ParsedQuery
from shopassist.text import singular

KIDS_GENDERS = {"kids", "boys", "girls", "unisex"}


@dataclass
class Filters:
    """Constraints a product must satisfy. Empty fields mean 'no constraint'."""

    sub_categories: tuple[str, ...] = ()
    brands: list[str] = field(default_factory=list)
    colours: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    gender: str | None = None
    numeric: list[NumericSpec] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    values: list[tuple[str, str]] = field(default_factory=list)
    booleans: list[str] = field(default_factory=list)
    budget_max: float | None = None
    budget_min: float | None = None
    in_stock_only: bool = False

    @classmethod
    def from_query(cls, q: ParsedQuery, skip_keys: Iterable[str] = ()) -> Filters:
        """Filters stated in this message. Numbers that answer the question itself are skipped
        ("does a 15.6 inch laptop fit?" asks about fits_laptop_upto_in, it does not filter by it)."""
        skip = set(skip_keys)
        return cls(
            sub_categories=q.sub_categories,
            brands=[n.brand for n in q.names if n.brand and not n.line],
            colours=list(q.colours),
            materials=list(q.materials),
            gender=q.gender,
            numeric=[s for s in q.numeric if not set(s.keys) & skip],
            sizes=[] if "sizes" in skip else list(q.sizes),
            values=list(q.values),
            booleans=[b for b in q.booleans if b not in skip],
            budget_max=q.budget_max,
            budget_min=q.budget_min,
            in_stock_only=q.in_stock_only,
        )

    def refined_by(self, newer: Filters) -> Filters:
        """Constraints from a follow-up turn are added; a new value of the same kind replaces the old."""
        return Filters(
            sub_categories=newer.sub_categories or self.sub_categories,
            brands=newer.brands or self.brands,
            colours=newer.colours or self.colours,
            materials=newer.materials or self.materials,
            gender=newer.gender or self.gender,
            numeric=_merge_numeric(self.numeric, newer.numeric),
            sizes=newer.sizes or self.sizes,
            values=_merge_values(self.values, newer.values),
            booleans=list(dict.fromkeys(self.booleans + newer.booleans)),
            budget_max=newer.budget_max if newer.budget_max is not None else self.budget_max,
            budget_min=newer.budget_min if newer.budget_min is not None else self.budget_min,
            in_stock_only=self.in_stock_only or newer.in_stock_only,
        )

    def carried_to_new_topic(self) -> Filters:
        """What survives when the shopper switches product type: budget, material and who it is for."""
        return Filters(
            materials=self.materials,
            gender=self.gender,
            budget_max=self.budget_max,
            budget_min=self.budget_min,
        )

    def is_empty(self) -> bool:
        return self == Filters()

    def describe(self) -> str:
        """Plain words for the reply, e.g. 'cotton Kurtas for men' (budgets are added by the caller)."""
        parts = [
            f"{s.value:g} {s.keys[0].rsplit('_', 1)[-1] if '_' in s.keys[0] else s.keys[0]}"
            for s in self.numeric
        ]
        parts += [*self.colours, *self.materials]
        parts += [v for _, v in self.values]
        parts += [" or ".join(self.sub_categories[:3])] if self.sub_categories else ["products"]
        text = " ".join(str(p) for p in parts if p)
        if self.gender:
            text += f" for {self.gender}"
        if self.in_stock_only:
            text += " that are in stock"
        return text


def _merge_numeric(old: list[NumericSpec], new: list[NumericSpec]) -> list[NumericSpec]:
    new_keys = {k for s in new for k in s.keys}
    return [s for s in old if not set(s.keys) & new_keys] + new


def _merge_values(old: list[tuple[str, str]], new: list[tuple[str, str]]) -> list[tuple[str, str]]:
    new_keys = {k for k, _ in new}
    return [kv for kv in old if kv[0] not in new_keys] + new


# ------------------------------------------------------------------------------------------ matching
def _equal(a: object, b: float) -> bool:
    try:
        return abs(float(a) - b) < 1e-6  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def numeric_ok(p: Product, spec: NumericSpec) -> bool:
    for key in spec.keys:
        v = p.attributes.get(key)
        if v is None or isinstance(v, bool):
            continue
        try:
            wanted = spec.value_for(key)
            if (float(v) >= wanted) if spec.at_least else _equal(v, wanted):
                return True
        except (TypeError, ValueError):
            continue
    return False


def size_ok(p: Product, size: str) -> bool:
    return size.lower() in {str(s).lower() for s in p.attributes.get("sizes") or []}


def gender_ok(p: Product, gender: str) -> bool:
    g = p.attributes.get("gender")
    if gender == "kids":
        return g in KIDS_GENDERS if g else "Kids" in p.sub_category
    return g == gender


def material_ok(p: Product, materials: list[str]) -> bool:
    wanted = {m.lower() for m in materials}
    return any(str(p.attributes.get(k, "")).lower() in wanted for k in MATERIAL_KEYS)


def values_ok(p: Product, values: list[tuple[str, str]]) -> bool:
    by_key: dict[str, set[str]] = {}
    for k, v in values:
        by_key.setdefault(k, set()).add(v.lower())
    return all(str(p.attributes.get(k, "")).lower() in vs for k, vs in by_key.items())


def matches(p: Product, f: Filters) -> bool:
    checks = (
        not f.sub_categories or p.sub_category in f.sub_categories,
        not f.brands or singular(p.brand.lower()) in f.brands,
        not f.colours or (p.colour or "").lower() in f.colours,
        not f.materials or material_ok(p, f.materials),
        not f.gender or gender_ok(p, f.gender),
        all(numeric_ok(p, s) for s in f.numeric),
        all(size_ok(p, s) for s in f.sizes),
        not f.values or values_ok(p, f.values),
        all(p.attributes.get(b) is True for b in f.booleans),
        f.budget_max is None or p.price_inr <= f.budget_max,
        f.budget_min is None or p.price_inr >= f.budget_min,
        not f.in_stock_only or p.stock_status != "out_of_stock",
    )
    return all(checks)


def relevant(f: Filters, pool: list[Product]) -> Filters:
    """Drop soft constraints no product in the pool could even have (a stray attribute word), so they
    do not empty the result. Numbers with units, material, budget and stock always apply, and colour
    whenever the products have colours:
    '10 litre toaster' must find nothing rather than every toaster."""
    keys = {k for p in pool for k in p.attributes}
    has_gender = "gender" in keys or any("Kids" in p.sub_category for p in pool)
    return replace(
        f,
        sizes=f.sizes if "sizes" in keys else [],
        values=[(k, v) for k, v in f.values if k in keys],
        booleans=[b for b in f.booleans if b in keys],
        gender=f.gender if has_gender else None,
        # "cream" is a colour for kurtas but not for sunscreen, which has no colours at all
        colours=f.colours if "colour" in keys else [],
    )


def apply(pool: list[Product], f: Filters) -> list[Product]:
    """Products from the pool that satisfy the (relevant part of the) filters."""
    base = [p for p in pool if not f.sub_categories or p.sub_category in f.sub_categories]
    f = relevant(f, base)
    return [p for p in base if matches(p, f)]
