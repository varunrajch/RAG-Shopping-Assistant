"""
index.py
Builds the two search indexes over the catalogue and the policy:
  1. BM25   - keyword index (finds exact words like "AeroGlide" or "kurta")
  2. Embeddings with MiniLM - meaning index (finds "jogging shoes" for "running shoes")
The policy document is split into its numbered sections (R1, S2, W1 ...) and
indexed the same way.

Embeddings take about a minute to compute on a CPU, so they are cached in
data/index/ and rebuilt only when the catalogue or policy file changes.

Run:  python index.py   (optional, the app builds the index on first start)
"""
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

import config

# Common words that carry no meaning for search (English + Hinglish fillers).
STOPWORDS = set("""
a an the is are am was were be been of in on at to for from with by and or but not no
i me my we our you your it its this that these those there here what which who whom how
much many do does did have has had can could will would should shall may might must
please pls want need looking look find get give show tell about any some something
one ones price cost costs rate rs inr rupee rupees colour color material size available
sell selling buy offer also just only really very same like than more less item items
product products thing things kind type please hi hello hey already said told mentioned
hai hain kya ka ki ke ko mein me mai main mujhe chahiye wala wali wale kaunsa kaunsi kaun
sa se kar sakte sakta sakti do de dena dikhao dikha bata batao kitna kitne kitni aur bhi
ek koi kuch tha thi the hu hoon ho let us policy which when where why
""".split())


def singular(token):
    """Very small plural remover: shoes -> shoe, sarees -> saree, kurtas -> kurta."""
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text, drop_stopwords=True):
    """Lower case words and numbers, plurals removed, stop words removed."""
    tokens = [singular(t) for t in re.findall(r"[a-z0-9]+", str(text).lower())]
    if drop_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


def product_text(row):
    """The text we index for one product."""
    return (f"{row.title}. {row.description} Category: {row.category}, {row.sub_category}. "
            f"Brand {row.brand}. Colour {row.colour}. Material {row.material}.")


def split_policy(markdown):
    """Split policy.md into sections. A section starts with '## R1. Title'."""
    sections = []
    for block in re.split(r"^## ", markdown, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        sec_id, _, title = heading.partition(".")
        sections.append({"id": sec_id.strip(), "title": title.strip(),
                         "text": " ".join(body.split())})
    return sections


@dataclass
class Index:
    df: pd.DataFrame                 # the catalogue table
    model: object                    # sentence transformers model
    bm25: BM25Okapi                  # keyword index over products
    emb: np.ndarray                  # product embeddings (normalised), shape (n, 384)
    title_tokens: list               # set of title words per product
    policy: list                     # policy sections [{id, title, text}]
    policy_bm25: BM25Okapi
    policy_emb: np.ndarray
    labels: list                     # (category, sub_category) pairs we sell
    label_emb: np.ndarray            # embeddings of those labels, for "nearest category"
    vocab: set = field(default_factory=set)        # every title word
    name_words: set = field(default_factory=set)   # brand and model words ("stridex", "aeroglide")
    rare_words: set = field(default_factory=set)   # model words found in <= 3 products

    def embed(self, texts):
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def _cached_embeddings(model, texts, name, source_files):
    """Load embeddings from disk if the source files have not changed, else compute."""
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = "|".join(f"{p}:{p.stat().st_mtime_ns}:{p.stat().st_size}" for p in source_files)
    stamp += f"|{config.EMBED_MODEL}|{len(texts)}"
    npy, stamp_file = config.INDEX_DIR / f"{name}.npy", config.INDEX_DIR / f"{name}.stamp"
    if npy.exists() and stamp_file.exists() and stamp_file.read_text() == stamp:
        return np.load(npy)
    print(f"Computing {len(texts)} embeddings for {name} (first run only)...")
    emb = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=True)
    np.save(npy, emb)
    stamp_file.write_text(stamp)
    return emb


def load_index():
    from sentence_transformers import SentenceTransformer  # slow import, so done here

    df = pd.read_csv(config.CATALOGUE_PATH, dtype={"size": str})
    model = SentenceTransformer(config.EMBED_MODEL, device="cpu")

    # products
    texts = [product_text(r) for r in df.itertuples()]
    bm25 = BM25Okapi([tokenize(t) for t in texts])
    emb = _cached_embeddings(model, texts, "products", [config.CATALOGUE_PATH])
    title_tokens = [set(tokenize(t, drop_stopwords=False)) for t in df.title]

    # words that name a product (brand or model) rather than describe it
    descriptive = set()
    for col in ["colour", "material", "category", "sub_category"]:
        for value in df[col].unique():
            descriptive |= set(tokenize(value, drop_stopwords=False))
    vocab = set().union(*title_tokens)
    name_words = vocab - descriptive
    doc_freq = pd.Series([w for toks in title_tokens for w in toks]).value_counts()
    rare_words = {w for w in name_words if doc_freq[w] <= config.RARE_TOKEN_MAX_DF}

    # policy sections
    policy = split_policy(config.POLICY_PATH.read_text(encoding="utf-8"))
    policy_texts = [f"{s['title']}. {s['text']}" for s in policy]
    policy_bm25 = BM25Okapi([tokenize(t) for t in policy_texts])
    policy_emb = _cached_embeddings(model, policy_texts, "policy", [config.POLICY_PATH])

    # category labels, used to suggest the nearest thing we do sell
    labels = sorted(set(zip(df.category, df.sub_category)))
    label_emb = model.encode([f"{sub} ({cat})" for cat, sub in labels], normalize_embeddings=True)

    return Index(df, model, bm25, emb, title_tokens, policy, policy_bm25, policy_emb,
                 labels, label_emb, vocab, name_words, rare_words)


if __name__ == "__main__":
    idx = load_index()
    print(f"Indexed {len(idx.df)} products and {len(idx.policy)} policy sections "
          f"({', '.join(s['id'] for s in idx.policy)}).")
    print(f"Product name words: {len(idx.name_words)}, rare model names: {sorted(idx.rare_words)}")
