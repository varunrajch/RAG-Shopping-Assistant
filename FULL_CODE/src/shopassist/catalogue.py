"""Catalogue loading. The catalogue is the single source of truth for every product fact."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOP_FIELDS = (
    "price_inr",
    "mrp_inr",
    "stock_status",
    "rating",
    "review_count",
    "brand",
    "category",
    "sub_category",
    "title",
)
STOCK_STATUSES = ("in_stock", "low_stock", "out_of_stock")
# words that follow the product-line word in a title and still belong to the model name
LINE_SUFFIXES = {"plus", "classic", "luxe", "edit", "weave", "pro", "max", "mini", "lite"}
_CAMEL_RE = re.compile(r"[A-Z][a-z]+|[A-Z]+(?![a-z])|\d+")


class CatalogueError(Exception):
    """Raised when the catalogue file is missing or malformed."""


@dataclass(frozen=True, eq=False)
class Product:
    """One sellable variant (each colour / size / pack is its own product).

    eq=False: products are unique catalogue rows, so identity is equality and they can be hashed."""

    product_id: str
    title: str
    brand: str
    category: str
    sub_category: str
    description: str
    attributes: dict[str, Any]
    price_inr: int
    mrp_inr: int
    stock_status: str
    rating: float | None
    review_count: int
    line: str = ""  # product-line word, lower case ("vistaair")
    model_tokens: frozenset[str] = field(default_factory=frozenset)  # "plus", "900", "s3" ...

    @property
    def discount_inr(self) -> int:
        return self.mrp_inr - self.price_inr

    @property
    def colour(self) -> str | None:
        return self.attributes.get("colour")

    def value(self, field_name: str) -> Any:
        """Catalogue value of a column or attribute key; None when the catalogue does not know it."""
        if field_name == "discount_inr":
            return self.discount_inr
        if field_name in TOP_FIELDS:
            return getattr(self, field_name)
        return self.attributes.get(field_name)


def camel_parts(word: str) -> list[str]:
    """'VistaAir' -> ['vista', 'air'];  'S3' -> ['s', '3']."""
    return [p.lower() for p in _CAMEL_RE.findall(word)] or [word.lower()]


def _line_and_model(title: str, brand: str) -> tuple[str, frozenset[str]]:
    words = title.split()
    if len(words) < 2 or words[0] != brand:
        return "", frozenset()
    line = words[1].lower()
    model = set()
    for w in words[2:4]:
        lw = w.lower()
        # model numbers like "900", "200", "S3" and suffixes like "Plus" are part of the name
        if lw in LINE_SUFFIXES or re.fullmatch(r"[a-z]?\d{1,4}[a-z]?", lw):
            model.add(lw)
        else:
            break
    return line, frozenset(model)


def _product_from_row(row: dict[str, Any]) -> Product:
    rating = row.get("rating")
    line, model = _line_and_model(row["title"], row["brand"])
    return Product(
        product_id=str(row["product_id"]),
        title=str(row["title"]),
        brand=str(row["brand"]),
        category=str(row["category"]),
        sub_category=str(row["sub_category"]),
        description=str(row.get("description") or ""),
        attributes=dict(row.get("attributes") or {}),
        price_inr=int(row["price_inr"]),
        mrp_inr=int(row["mrp_inr"]),
        stock_status=str(row["stock_status"]),
        rating=float(rating) if rating is not None else None,
        review_count=int(row.get("review_count") or 0),
        line=line,
        model_tokens=model,
    )


@dataclass
class Catalogue:
    products: list[Product]

    def __post_init__(self) -> None:
        self.by_id: dict[str, Product] = {p.product_id: p for p in self.products}
        self.sub_categories: set[str] = {p.sub_category for p in self.products}
        self.brands: set[str] = {p.brand.lower() for p in self.products}
        self.lines: set[str] = {p.line for p in self.products if p.line}

    def __len__(self) -> int:
        return len(self.products)

    def get(self, product_id: str) -> Product | None:
        return self.by_id.get(product_id)

    def values_of(self, key: str) -> set[str]:
        """All distinct string values of an attribute key (lower case)."""
        out: set[str] = set()
        for p in self.products:
            v = p.attributes.get(key)
            if isinstance(v, str):
                out.add(v.lower())
        return out


def load_catalogue(path: Path) -> Catalogue:
    """Read catalogue.jsonl (one product per line, `attributes` nested)."""
    if not path.is_file():
        raise CatalogueError(
            f"Catalogue not found at {path}. Copy the pack's data/ files into FULL_CODE/data/."
        )
    products = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                products.append(_product_from_row(json.loads(line)))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise CatalogueError(f"{path.name} line {line_no} is malformed: {exc}") from exc
    if not products:
        raise CatalogueError(f"{path} contains no products.")
    return Catalogue(products)
