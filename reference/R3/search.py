"""
search.py
Hybrid search: one combined score per product
    score = W_BM25 * (BM25 score / best BM25 score) + W_EMB * cosine similarity
then the structured filters (category, colour, size, material, max price,
in stock) are applied on the catalogue table, so a product that breaks a
limit can never be shown, however well it scores.
"""
from dataclasses import dataclass

import numpy as np

import config
from index import tokenize


@dataclass
class SearchResult:
    rows: np.ndarray    # catalogue row positions, best first (only rows that pass the filters)
    score: np.ndarray   # combined score of each row
    cos: np.ndarray     # embedding similarity of each row


def _combined_scores(bm25, emb, model_embed, text):
    tokens = tokenize(text)
    bm = bm25.get_scores(tokens) if tokens else np.zeros(len(emb))
    bm_norm = bm / bm.max() if bm.max() > 0 else bm
    cos = emb @ model_embed([text])[0]
    return config.W_BM25 * bm_norm + config.W_EMB * cos, cos, bm


def filter_mask(df, filters):
    """True for every catalogue row that satisfies all the filters."""
    m = np.ones(len(df), dtype=bool)
    if filters.get("sub_category"):
        m &= (df.sub_category == filters["sub_category"]).to_numpy()
    elif filters.get("category"):
        m &= (df.category == filters["category"]).to_numpy()
    if filters.get("colour"):
        m &= (df.colour == filters["colour"]).to_numpy()
    if filters.get("material"):
        m &= (df.material == filters["material"]).to_numpy()
    if filters.get("size"):
        s = filters["size"]
        m &= df["size"].str.upper().isin([s, f"UK {s}"]).to_numpy()
    if filters.get("max_price"):
        m &= (df.price <= filters["max_price"]).to_numpy()
    if filters.get("in_stock"):
        m &= (df.stock_status != "out_of_stock").to_numpy()
    return m


def search_products(index, parsed, filters):
    score, cos, _ = _combined_scores(index.bm25, index.emb, index.embed, parsed.text)
    mask = filter_mask(index.df, filters)
    # If the shopper named a product ("AeroGlide"), only that product counts.
    if parsed.named_words:
        mask &= np.array([any(w in toks for w in parsed.named_words) for toks in index.title_tokens])
    rows = np.where(mask)[0]
    rows = rows[np.argsort(-score[rows], kind="stable")]
    return SearchResult(rows, score[rows], cos[rows])


def search_policy(index, text):
    """Policy sections ranked best first: list of (section, score, cos, bm25)."""
    # Drop filler words first ("return kitne din mein kar sakte hai" -> "return day"),
    # the English embedding model is confused by Hinglish fillers.
    text = " ".join(tokenize(text)) or text
    score, cos, bm = _combined_scores(index.policy_bm25, index.policy_emb, index.embed, text)
    order = np.argsort(-score)
    return [(index.policy[i], score[i], cos[i], bm[i]) for i in order]


def nearest_category(index, text, words=()):
    """The (category, sub_category) we sell that is close to what the shopper asked,
    or None when nothing we sell is really related (iPhone -> no suggestion).
    A category counts when it shares a word with the question ("laptop" -> Laptop Bag)
    or is close in meaning (football boots -> Sneakers)."""
    for cat, sub in index.labels:
        if set(words) & set(tokenize(sub)):
            return cat, sub
    sims = index.label_emb @ index.embed([text])[0]
    best = int(np.argmax(sims))
    return index.labels[best] if sims[best] >= config.NEAREST_MIN_SIM else None
