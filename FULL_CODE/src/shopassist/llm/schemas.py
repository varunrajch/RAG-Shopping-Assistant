"""Validation of LLM output before the rules engine uses it."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError

MAX_REWRITE_CHARS = 200
_UNSAFE = re.compile(r"[<>{}`]|https?://|sku-", re.IGNORECASE)


class RewriteHint(BaseModel):
    # the model's own translation; it helps the model choose but is never used as data
    meaning: str | None = Field(default=None, max_length=MAX_REWRITE_CHARS * 2)
    rewritten_query: str | None = Field(default=None, max_length=MAX_REWRITE_CHARS)
    sub_category: str | None = None


def validated_rewrite(data: dict | None, allowed: set[str]) -> RewriteHint | None:
    """The LLM's rewrite, only if it has the expected shape, a known product type (or none), and plain text.

    The rewrite is never shown to the shopper; it only goes back through the rules engine."""
    if data is None:
        return None
    try:
        hint = RewriteHint.model_validate(data)
    except ValidationError:
        return None
    if hint.sub_category is not None and hint.sub_category not in allowed:
        hint.sub_category = None
    if hint.rewritten_query is not None:
        text = " ".join(hint.rewritten_query.split())
        hint.rewritten_query = text if text and not _UNSAFE.search(text) else None
    if hint.rewritten_query is None and hint.sub_category is None:
        return None
    return hint
