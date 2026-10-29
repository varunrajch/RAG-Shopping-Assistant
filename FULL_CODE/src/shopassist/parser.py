"""Query understanding with rules: shopper message -> ParsedQuery.

  "krida ion flex football rate?"        -> brand=kridaa, line=ionflex, sub_category=Footballs, asks price
  "king size cotton bedsheet sabse sasti jo stock me ho"
                                         -> Bedsheets, bed_size=king, material=cotton, cheapest, in stock only

Names are matched against the catalogue's own brand and product-line words, with joins
("ripple flex" -> rippleflex) and fuzzy matching ("krida" -> kridaa) for misspellings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from shopassist import lexicon as lx
from shopassist.catalogue import Catalogue
from shopassist.config import MatchingSettings
from shopassist.text import clean, phrase_key, singular, to_number, tokenize

MATERIAL_KEYS = (
    "material",
    "upper_material",
    "sole_material",
    "plate_material",
    "blade_material",
    "handle_material",
)
UNIT_WORDS = set(lx.UNIT_KEYS) | {"year", "uk"}
JOIN_FILLERS = {"wala", "wali", "wale", "ka", "ki", "ke"}


@dataclass(frozen=True)
class NumericSpec:
    """A number with a unit, e.g. 5.5 l -> capacity_l == 5.5."""

    keys: tuple[str, ...]
    value: float
    at_least: bool = False
    scales: tuple[float, ...] = ()  # per key, when a key stores the quantity in another unit

    def value_for(self, key: str) -> float:
        i = self.keys.index(key)
        return self.value * (self.scales[i] if i < len(self.scales) else 1.0)


@dataclass
class NameMention:
    """A brand and / or product line named in the message, with the variant words next to it."""

    brand: str | None = None
    line: str | None = None
    model_tokens: list[str] = field(default_factory=list)
    colours: list[str] = field(default_factory=list)
    start: int = 0


@dataclass
class ParsedQuery:
    raw: str
    text: str = ""  # cleaned text, used by the regexes
    tokens: list[str] = field(default_factory=list)  # normalised tokens
    names: list[NameMention] = field(default_factory=list)
    sub_categories: tuple[str, ...] = ()
    colours: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    gender: str | None = None
    numeric: list[NumericSpec] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)  # "8-9Y", "UK 8", "XL"
    values: list[tuple[str, str]] = field(default_factory=list)  # (attribute key, catalogue value)
    booleans: list[str] = field(default_factory=list)
    model_tokens: list[str] = field(default_factory=list)
    budget_max: float | None = None
    budget_min: float | None = None
    in_stock_only: bool = False
    superlative: str | None = None  # "min" | "max"
    compare: bool = False
    asks_price: bool = False
    asks_stock: bool = False
    asks_discount: bool = False
    asked_fields: list[tuple[str, ...]] = field(default_factory=list)
    wants_list: bool = False
    refers_to_previous: bool = False
    real_brand: str | None = None
    unsold_item: str | None = None
    policy_like: bool = False
    unknown_words: list[str] = field(default_factory=list)

    @property
    def has_name(self) -> bool:
        return any(n.line or n.brand for n in self.names)

    @property
    def has_line(self) -> bool:
        return any(n.line for n in self.names)

    def summary(self) -> dict:
        """Short, JSON-friendly view for the demo's debug panel."""
        out = {
            "names": [{k: v for k, v in vars(n).items() if v and k != "start"} for n in self.names],
            "sub_categories": list(self.sub_categories),
            "colours": self.colours,
            "materials": self.materials,
            "gender": self.gender,
            "sizes": self.sizes,
            "numeric": [
                f"{'/'.join(s.keys)} {'>=' if s.at_least else '='} {s.value:g}" for s in self.numeric
            ],
            "values": [f"{k}={v}" for k, v in self.values],
            "booleans": self.booleans,
            "budget_max": self.budget_max,
            "in_stock_only": self.in_stock_only,
            "superlative": self.superlative,
            "compare": self.compare,
            "asks_price": self.asks_price,
            "asks_stock": self.asks_stock,
            "asked_fields": [list(f) for f in self.asked_fields],
            "wants_list": self.wants_list,
            "real_brand": self.real_brand,
            "unsold_item": self.unsold_item,
        }
        return {k: v for k, v in out.items() if v not in (None, False, [], ())}


class Vocabulary:
    """Words the catalogue itself uses, so the parser recognises names, colours and materials."""

    def __init__(self, catalogue: Catalogue, settings: MatchingSettings):
        self.settings = settings
        self.brands = {singular(b) for b in catalogue.brands}
        self.lines = {singular(p.line) for p in catalogue.products if p.line}
        self.model_tokens = {t for p in catalogue.products for t in p.model_tokens}
        # product lines named with an ordinary word ("Hawa", "Dhoop") rather than a coined one ("VistaAir")
        self.plain_lines = {
            singular(p.line) for p in catalogue.products if re.fullmatch(r"[A-Z][a-z]+", p.title.split()[1])
        }
        self.colours = {c.lower() for c in (p.colour for p in catalogue.products) if c}
        self.materials = self._phrases(catalogue, MATERIAL_KEYS)
        self.values = self._phrases(catalogue, lx.VALUE_KEYS, skip=lx.VALUE_STOPLIST | self.colours)
        self.aliases = {phrase_key(k, lx.WORD_FIX): v for k, v in lx.SUBCATEGORY_ALIASES.items()}
        self.names = sorted(self.brands | self.lines)
        generic = set(lx.STOPWORDS) | self.colours | set(lx.GENDER_WORDS) | UNIT_WORDS
        for key in list(self.aliases) + list(self.materials) + list(self.values):
            generic.update(key)
        generic.update(t for v in lx.WORD_FIX.values() for t in v.split())
        # a catalogue name word is never "generic", even if it is also an ordinary word
        self.generic = generic - self.names_set

    @property
    def names_set(self) -> set[str]:
        return self.brands | self.lines

    @staticmethod
    def _phrases(catalogue: Catalogue, keys: tuple[str, ...], skip: set[str] | None = None) -> dict:
        out: dict[tuple[str, ...], set[tuple[str, str]]] = {}
        for p in catalogue.products:
            for key in keys:
                v = p.attributes.get(key)
                if isinstance(v, str) and v.lower() not in (skip or set()):
                    out.setdefault(phrase_key(v), set()).add((key, v))
        return out

    def match_name(self, tokens: list[str], fuzzy: bool = True) -> str | None:
        """Exact (or, if allowed, fuzzy) match of a joined token sequence to a brand or product-line word."""
        joined = "".join(tokens)
        if not joined.isalpha():
            return None
        if joined in self.names_set:
            return joined
        if not fuzzy or len(joined) < self.settings.fuzzy_min_token_len:
            return None
        # a fuzzy join must not swallow an ordinary word at its edge ("quillbolt red" is not a name)
        if tokens[0] in self.generic or tokens[-1] in self.generic:
            return None
        best = process.extractOne(
            joined, self.names, scorer=fuzz.ratio, score_cutoff=self.settings.fuzzy_name_cutoff
        )
        return best[0] if best else None


class QueryParser:
    def __init__(self, vocab: Vocabulary):
        self.vocab = vocab

    def parse(self, message: str) -> ParsedQuery:
        text = clean(message)
        tokens = self._normalised_tokens(message)
        q = ParsedQuery(raw=message, text=text, tokens=tokens)
        used = [False] * len(tokens)
        self._budget(q, used)
        self._names(q, used)
        self._numbers(q, used)
        q.materials = [v for _, v in self._take_phrases(tokens, used, self.vocab.materials)]
        q.values = self._alias_values(tokens, used)
        q.sub_categories = self._sub_categories(tokens, used)
        if not q.sub_categories:
            self._material_as_product_type(q)
        self._colours_gender(q, used)
        q.values += self._take_phrases(tokens, used, self.vocab.values)
        self._intent(q)
        q.unknown_words = [
            t
            for t, u in zip(tokens, used, strict=True)
            if not u and t not in self.vocab.generic and not t[0].isdigit() and len(t) > 2
        ]
        self._drop_coincidental_name(q)
        return q

    # ---------------------------------------------------------------------------------- tokens
    @staticmethod
    def _normalised_tokens(message: str) -> list[str]:
        out: list[str] = []
        for tok in tokenize(message):
            tok = lx.WORD_FIX.get(tok, tok)
            out.extend(singular(t) for t in tok.split())
        return out

    # ---------------------------------------------------------------------------------- budget
    def _budget(self, q: ParsedQuery, used: list[bool]) -> None:
        for rx in lx.BUDGET_RES:
            m = rx.search(q.text)
            if m:
                q.budget_max = float(m.group(1))
                break
        m = lx.MIN_BUDGET_RE.search(q.text)
        if m:
            q.budget_min = float(m.group(1) or m.group(2))
        for value in (q.budget_max, q.budget_min):
            if value is None:
                continue
            for i, t in enumerate(q.tokens):
                if to_number(t) == value and not used[i]:
                    used[i] = True
                    break

    # ---------------------------------------------------------------------------------- names
    def _names(self, q: ParsedQuery, used: list[bool]) -> None:
        tokens, max_join = q.tokens, self.vocab.settings.max_join_tokens
        current: NameMention | None = None
        i = 0
        while i < len(tokens):
            hit, k = self._name_at(tokens, used, i, max_join)
            if not hit:
                i += 1
                continue
            for j in range(i, i + k):
                used[j] = True
            is_brand = hit in self.vocab.brands and not (
                current and current.brand and not current.line and hit in self.vocab.lines
            )
            if current is None or (is_brand and current.brand) or (not is_brand and current.line):
                current = NameMention(start=i)
                q.names.append(current)
            if is_brand:
                current.brand = hit
            else:
                current.line = hit
            i += k
            # model words right after the line ("900", "s3", "plus") belong to the name
            while (
                i < len(tokens)
                and not used[i]
                and tokens[i] in self.vocab.model_tokens
                and (i + 1 >= len(tokens) or tokens[i + 1] not in UNIT_WORDS)
            ):
                current.model_tokens.append(tokens[i])
                used[i] = True
                i += 1
        q.model_tokens = [t for n in q.names for t in n.model_tokens]

    def _name_at(self, tokens: list[str], used: list[bool], i: int, max_join: int) -> tuple[str | None, int]:
        """Longest exact match first; fuzzy matching only if no exact match starts here."""
        for fuzzy in (False, True):
            for k in range(min(max_join, len(tokens) - i), 0, -1):
                if any(used[i : i + k]):
                    continue
                hit = self.vocab.match_name(tokens[i : i + k], fuzzy=fuzzy)
                if hit:
                    return hit, k
        return None, 0

    # ---------------------------------------------------------------------------------- numbers
    def _numbers(self, q: ParsedQuery, used: list[bool]) -> None:
        tokens = q.tokens
        for i, tok in enumerate(tokens):
            if used[i]:
                continue
            nxt = self._next_word(tokens, used, i)
            prev = tokens[i - 1] if i > 0 else ""
            if re.fullmatch(r"\d+-\d+", tok) and nxt and tokens[nxt] == "year":
                q.sizes.append(f"{tok}Y")
                used[i] = used[nxt] = True
                continue
            value = to_number(tok)
            if value is None:
                continue
            if prev == "uk":
                q.sizes.append(f"UK {tok}")
                used[i] = used[i - 1] = True
            elif prev in lx.PREFIX_UNITS or (i > 1 and f"{tokens[i - 2]} {prev}" in lx.PREFIX_UNITS):
                unit = prev if prev in lx.PREFIX_UNITS else f"{tokens[i - 2]} {prev}"
                q.numeric.append(NumericSpec(lx.PREFIX_UNITS[unit], value))
                used[i] = True
            elif nxt is not None and tokens[nxt] in lx.UNIT_KEYS:
                unit = tokens[nxt]
                keys = lx.UNIT_KEYS[unit]
                scales = tuple(lx.UNIT_SCALE.get((unit, k), 1.0) for k in keys)
                at_least = bool(set(keys) & lx.AT_LEAST_KEYS)
                q.numeric.append(NumericSpec(keys, value, at_least=at_least, scales=scales))
                used[i] = used[nxt] = True

    @staticmethod
    def _next_word(tokens: list[str], used: list[bool], i: int) -> int | None:
        """Index of the next word, skipping 'wala' / 'ka' fillers ("20 wala pack")."""
        j = i + 1
        while j < len(tokens) and tokens[j] in JOIN_FILLERS:
            j += 1
        return j if j < len(tokens) and not used[j] else None

    # ---------------------------------------------------------------------------------- phrases
    @staticmethod
    def _take_phrases(tokens: list[str], used: list[bool], table: dict) -> list:
        """Longest-first phrase lookup; marks matched tokens as used."""
        found: list = []
        longest = max((len(k) for k in table), default=0)
        i = 0
        while i < len(tokens):
            for k in range(min(longest, len(tokens) - i), 0, -1):
                key = tuple(tokens[i : i + k])
                if key in table and not any(used[i : i + k]):
                    hits = table[key]
                    found.extend(sorted(hits) if isinstance(hits, set) else [hits])
                    for j in range(i, i + k):
                        used[j] = True
                    i += k - 1
                    break
            i += 1
        return found

    def _drop_coincidental_name(self, q: ParsedQuery) -> None:
        """Brand and line names include everyday Hindi words ("khilona" = toy, "hawa" = air, "dhoop" = sun).
        A lone such word in a message that is otherwise unrecognised is not a product name."""
        if len(q.names) != 1 or q.sub_categories or not q.unknown_words:
            return
        n = q.names[0]
        lone_brand = bool(n.brand) and not n.line
        lone_plain_line = bool(n.line) and not n.brand and n.line in self.vocab.plain_lines
        if lone_brand or lone_plain_line:
            q.unknown_words.append(n.brand or n.line)
            q.colours = [c for c in q.colours if c not in n.colours]
            q.names = []
            q.model_tokens = []

    def _material_as_product_type(self, q: ParsedQuery) -> None:
        """'iron' is a material in "iron tawa" but the product in "cheap iron for clothes"."""
        for m in list(q.materials):
            subs = self.vocab.aliases.get(phrase_key(m))
            if subs:
                q.sub_categories = tuple(subs)
                q.materials.remove(m)
                return

    def _alias_values(self, tokens: list[str], used: list[bool]) -> list[tuple[str, str]]:
        """'teddy bear' names a product type (Soft Toys) and an attribute value (animal=teddy bear)."""
        found = []
        for key in self.vocab.aliases:
            if key in self.vocab.values and _contains(tokens, used, key):
                found.extend(sorted(self.vocab.values[key]))
        return found

    def _sub_categories(self, tokens: list[str], used: list[bool]) -> tuple[str, ...]:
        found = self._take_phrases(tokens, used, self.vocab.aliases)
        subs: list[str] = []
        for group in found:
            subs.extend(s for s in group if s not in subs)
        # the most specific phrase wins: "laptop bag backpack" -> Backpacks
        if len(found) > 1:
            common = set(found[0]).intersection(*map(set, found[1:]))
            if common:
                return tuple(s for s in subs if s in common)
            return tuple(found[-1]) if len(found[-1]) < len(found[0]) else tuple(found[0])
        return tuple(subs)

    def _colours_gender(self, q: ParsedQuery, used: list[bool]) -> None:
        for i, t in enumerate(q.tokens):
            if used[i]:
                continue
            if t in self.vocab.colours:
                q.colours.append(t)
                used[i] = True
                mention = self._mention_before(q.names, i)
                if mention:
                    mention.colours.append(t)
            elif t in lx.GENDER_WORDS and q.gender is None:
                q.gender = lx.GENDER_WORDS[t]
                used[i] = True
            elif t in {"xs", "s", "m", "l", "xl", "xxl", "xxxl"} and i > 0 and q.tokens[i - 1] == "size":
                q.sizes.append(t.upper())
                used[i] = True

    @staticmethod
    def _mention_before(names: list[NameMention], index: int) -> NameMention | None:
        before = [n for n in names if n.start <= index]
        return before[-1] if before else None

    # ---------------------------------------------------------------------------------- intent
    def _intent(self, q: ParsedQuery) -> None:
        t = q.text
        q.asked_fields = [fields for rx, fields in lx.ATTRIBUTE_QUESTIONS if rx.search(t)]
        q.asks_discount = bool(lx.DISCOUNT_RE.search(t))
        price_phrase = re.search(r"\bkitn[eai]y?\s+(ka|ki|ke|me|mein|mai|mei)\b", t)
        q.asks_price = bool(
            lx.PRICE_RE.search(t)
            or price_phrase
            or q.asks_discount
            or (lx.HOW_MUCH_RE.search(t) and not q.asked_fields)
        )
        q.in_stock_only = bool(lx.STOCK_FILTER_RE.search(t))
        q.asks_stock = bool(lx.STOCK_RE.search(t)) and not q.in_stock_only
        if lx.CHEAPEST_RE.search(t):
            q.superlative = "min"
        elif lx.COSTLIEST_RE.search(t):
            q.superlative = "max"
        several = len(q.names) > 1 or len(q.colours) > 1
        q.compare = bool(
            several
            and (
                re.search(r"\b(vs|versus|compare)\b", t)
                or (lx.COMPARE_RE.search(t) and (lx.CHEAPER_RE.search(t) or "which" in t or "kaun" in t))
            )
        )
        if q.compare and not re.search(r"\bsabse\b", t):
            q.superlative = q.superlative or "min"
        q.wants_list = bool(lx.LIST_RE.search(t))
        q.refers_to_previous = bool(lx.FOLLOWUP_SET_RE.search(t))
        q.booleans = [key for rx, key in lx.BOOLEAN_FILTERS if rx.search(t)]
        q.policy_like = bool(lx.POLICY_TRIGGER_RE.search(t))
        q.real_brand = next((w for w in re.findall(r"[a-z0-9]+", t) if w in lx.REAL_BRANDS), None)
        q.unsold_item = next((w for w in q.tokens if w in lx.UNSOLD_ITEMS), None)


def _contains(tokens: list[str], used: list[bool], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    return any(
        tuple(tokens[i : i + n]) == phrase and not any(used[i : i + n]) for i in range(len(tokens) - n + 1)
    )
