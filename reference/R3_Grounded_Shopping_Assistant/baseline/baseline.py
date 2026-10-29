#!/usr/bin/env python3
"""R3 baseline: keyword / TF-IDF retrieval + hand-written rules. No LLM, no internet.

    python baseline/baseline.py --questions data/questions_dev.csv  --out submission/R3_dev_predictions.jsonl
    python baseline/baseline.py --questions data/questions_test.csv --out submission/R3_predictions.jsonl

It is deliberately simple (and has obvious weaknesses — beat it!):
  * policy questions are routed by keywords to one policy section;
  * a short list of "things we don't sell" triggers a refusal;
  * products are retrieved by IDF-weighted word overlap with title/brand/sub-category/attributes;
  * if several products tie for the best match and have different prices -> clarify, else answer with the top one;
  * every price it states is copied from the catalogue, so it never hallucinates a price.
It needs only Python >= 3.9, numpy and pandas.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

STOP = set("""a an the is are was of for to in on me se ka ki ke hai h hain kya kitne kitna kitni kaunsa kaunsi konsa konsi
wala wali wale price rate batao bata do pls please plz hi aur ya or and with i my mujhe chahiye milega milegi hoga ho
kar sakte sakti abhi ok toh to bhi jo ye yeh woh wo inme isme what which how much cost costs of available stock""".split())
SYNONYMS = {"tshirt": "t-shirt", "tshirts": "t-shirt", "facewash": "face wash", "powerbank": "power bank",
            "ladies": "women", "mens": "men", "shoe": "shoes", "litre": "l", "liter": "l", "ltr": "l"}
# Only the category words README says the store does NOT sell (phones, laptops, TVs, groceries, medicines, jewellery,
# vehicles) plus the PS's own "iphone" example. Nothing specific to individual questions.
OUT_OF_CATALOGUE = {"iphone", "phone", "phones", "smartphone", "laptop", "laptops", "tv", "television", "grocery", "groceries",
                    "medicine", "medicines", "jewellery", "gold", "car", "cars", "vehicle", "bike"}
POLICY_RULES = [  # (regex, section) — first match wins; keywords are the policy.md headings
    (r"restocking", "1.2"), (r"refund", "1.5"), (r"exchange", "1.6"), (r"\bcod\b|cash on delivery", "4.2"),
    (r"delivery charge|shipping charge", "2.1"), (r"international|outside india", "2.3"), (r"cancel", "5.1"),
    (r"warranty", "3.1"), (r"\bgst\b", "7.1"), (r"coupon", "7.3"), (r"price match", "7.4"), (r"return", "1.1"),
]
ATTR_RULES = [  # (regex, attribute key)
    (r"waterproof|water resistant", "water_resistant"), (r"dishwasher", "dishwasher_safe"), (r"induction", "induction_compatible"),
    (r"paraben", "paraben_free"), (r"noise cancel", "noise_cancellation"), (r"weight", "weight_g"), (r"battery", "battery_life_hours"),
]
SUPER_CHEAP = re.compile(r"sasta|sasti|cheapest|lowest|kam price|sabse kam")
SUPER_COSTLY = re.compile(r"mehenga|mehnga|costliest|most expensive|sabse zyada price")
BROWSE = re.compile(r"dikhao|dikha|show|options|under|andar|se kam|chahiye")
STOCK_Q = re.compile(r"stock|available|milega|milegi")


def tokens(text: str) -> list:
    text = text.lower().replace("-", " ")
    out = []
    for w in re.findall(r"[a-z0-9.]+", text):
        w = w.strip(".")
        w = SYNONYMS.get(w, w)
        if w and w not in STOP:
            out.extend(w.split())
    return out


class Index:
    def __init__(self, cat: pd.DataFrame):
        self.cat = cat
        self.docs = []
        for r in cat.itertuples(index=False):
            attrs = json.loads(r.attributes)
            vals = []
            for v in attrs.values():
                vals.extend(v if isinstance(v, list) else [v])
            self.docs.append(set(tokens(f"{r.title} {r.brand} {r.sub_category} " + " ".join(str(v) for v in vals))))
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str):
        q = set(tokens(query))
        scores = [sum(self.idf.get(t, 0.0) for t in q if t in d) for d in self.docs]
        return pd.Series(scores, index=self.cat.index).sort_values(ascending=False, kind="mergesort")


def rupee(x: float) -> str:
    return f"₹{int(x):,}"


def respond(text: str, history: list, cat: pd.DataFrame, index: Index) -> dict:
    low = text.lower()
    out = {"action": "refuse", "answer_text": "Sorry, I don't have that information in our catalogue.",
           "cited_product_ids": [], "cited_policy_sections": [], "stated_prices": [], "stated_facts": []}
    toks = set(tokens(low))
    laptop_ok = re.search(r"laptop (bag|sleeve|backpack|wala)|backpack", low)
    if (toks & OUT_OF_CATALOGUE) and not (laptop_ok and toks & OUT_OF_CATALOGUE == {"laptop"}):
        return out
    for rx, sec in POLICY_RULES:
        if re.search(rx, low) and not re.search(r"[A-Z][a-z]+[A-Z]", text):
            out.update(action="answer", cited_policy_sections=[sec],
                       answer_text=f"As per our store policy (section {sec}), please see the policy for details.")
            return out
    query = " ".join(history[-2:] + [text]) if len(text.split()) <= 5 and history else text
    scores = index.search(query)
    top = scores.iloc[0]
    if top < 4.0:
        return out
    tied = scores[scores >= top - 1e-9]
    near = scores[scores >= 0.8 * top]
    for rx, key in ATTR_RULES:
        if re.search(rx, low):
            r = cat.loc[tied.index[0]]
            attrs = json.loads(r.attributes)
            if key not in attrs:
                out.update(cited_product_ids=[r.product_id],
                           answer_text=f"The catalogue doesn't say this for {r.title} ({r.product_id}).")
                return out
            out.update(action="answer", cited_product_ids=[r.product_id],
                       stated_facts=[{"product_id": r.product_id, "field": key, "value": attrs[key]}],
                       answer_text=f"{r.title} ({r.product_id}): {key.replace('_', ' ')} = {attrs[key]}.")
            return out
    if SUPER_CHEAP.search(low) or SUPER_COSTLY.search(low):
        pool = cat.loc[near.index]
        r = pool.loc[pool.price_inr.idxmin()] if SUPER_CHEAP.search(low) else pool.loc[pool.price_inr.idxmax()]
        out.update(action="answer", cited_product_ids=[r.product_id],
                   stated_prices=[{"product_id": r.product_id, "price_inr": int(r.price_inr)}],
                   answer_text=f"{r.title} ({r.product_id}) at {rupee(r.price_inr)}.")
        return out
    if BROWSE.search(low) and not re.search(r"kitne|price|rate", low):
        pool = cat.loc[near.index[:5]]
        out.update(action="answer", cited_product_ids=list(pool.product_id),
                   stated_prices=[{"product_id": p, "price_inr": int(v)} for p, v in zip(pool.product_id, pool.price_inr)],
                   answer_text="Some options: " + "; ".join(f"{t} ({p}) {rupee(v)}" for t, p, v in zip(pool.title, pool.product_id, pool.price_inr)))
        return out
    if len(tied) >= 2 and cat.loc[tied.index, "price_inr"].nunique() > 1:
        pool = cat.loc[tied.index[:5]]
        out.update(action="clarify", cited_product_ids=list(pool.product_id),
                   answer_text="I found several matching products: " + "; ".join(f"{t} ({p})" for t, p in zip(pool.title, pool.product_id)) + ". Which one do you mean?")
        return out
    r = cat.loc[tied.index[0]]
    facts = [{"product_id": r.product_id, "field": "stock_status", "value": r.stock_status}] if STOCK_Q.search(low) else []
    out.update(action="answer", cited_product_ids=[r.product_id], stated_facts=facts,
               stated_prices=[{"product_id": r.product_id, "price_inr": int(r.price_inr)}],
               answer_text=f"{r.title} ({r.product_id}) costs {rupee(r.price_inr)} and is {r.stock_status.replace('_', ' ')}.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(DATA / "questions_test.csv"))
    ap.add_argument("--out", default="submission/R3_predictions.jsonl")
    args = ap.parse_args()
    cat = pd.read_csv(DATA / "catalogue.csv", dtype={"product_id": str})
    index = Index(cat)
    qs = pd.read_csv(args.questions, dtype=str).sort_values(["conversation_id", "turn"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    history: dict = {}
    with open(args.out, "w", encoding="utf-8") as f:
        for r in qs.itertuples(index=False):
            t0 = time.perf_counter()
            res = respond(r.question_text, history.get(r.conversation_id, []), cat, index)
            history.setdefault(r.conversation_id, []).append(r.question_text)
            res = {"question_id": r.question_id, **res, "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                   "tokens_in": 0, "tokens_out": 0}
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(f"wrote {len(qs)} predictions to {args.out}")


if __name__ == "__main__":
    main()
