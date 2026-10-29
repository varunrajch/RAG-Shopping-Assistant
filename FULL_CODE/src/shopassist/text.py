"""Text normalisation shared by the query parser and the catalogue vocabulary.

Queries and catalogue words go through the same functions, so both sides of a comparison
look alike: lower case, standard digits, no thousands separators, simple singular nouns.
"""

from __future__ import annotations

import re
import unicodedata

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?-\d+|\d+(?:\.\d+)?|[a-z]+\d*[a-z0-9]*")
_NO_SINGULAR = {
    "plus",
    "canvas",
    "glass",
    "dress",
    "brass",
    "less",
    "series",
    "lens",
    "bus",
    "gas",
    "yes",
    "this",
    "his",
    "has",
    "was",
    "is",
    "us",
    "abs",
    "pcs",
    "jeans",
    "chess",
    "kids",
    "mens",
    "ladies",
    "womens",
    "boys",
    "girls",
    "news",
    "ios",
    "atlas",
    "pass",
    "class",
}


def clean(text: str) -> str:
    """Unicode-normalise and lower-case; expand '2k' and drop thousands separators."""
    t = unicodedata.normalize("NFKC", text or "").translate(_DEVANAGARI_DIGITS).lower()
    t = t.replace("₹", " rs ").replace("’", "'")
    t = re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", t)  # 1,499 -> 1499
    # "2k" -> 2000 only when the k is attached, as the scorer does ("449 k andar" is 449)
    t = re.sub(r"\b(\d+(?:\.\d+)?)k\b", lambda m: str(int(float(m.group(1)) * 1000)), t)
    return t


def singular(token: str) -> str:
    """Tiny plural remover: shoes -> shoe, kurtas -> kurta, boxes -> box."""
    if token in _NO_SINGULAR or len(token) <= 3 or not token.isalpha():
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("xes", "ches", "shes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Words and numbers. '100ml' -> ['100', 'ml'];  'ipx7' stays one token;  '8-9' stays one token."""
    return _TOKEN_RE.findall(clean(text))


def to_number(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def phrase_key(phrase: str, fix: dict[str, str] | None = None) -> tuple[str, ...]:
    """Normalised token tuple for a lexicon phrase, so it can be matched against query tokens."""
    out: list[str] = []
    for tok in tokenize(phrase):
        tok = (fix or {}).get(tok, tok)
        out.extend(singular(t) for t in tok.split())
    return tuple(out)
