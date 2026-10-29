# R3: The Conversational Shopping Assistant That Doesn't Lie

**Team:** Tech Titans (TEAM-001450)

**Problem ID:** R3 (Retail)

## Summary

A shopping chatbot that answers only from the product catalogue and store policy, cites a product ID or policy section for every fact, asks which product is meant when several match, and says "I don't have that" instead of guessing. It never invents a price.

## Business context

Retailers everywhere are adding chatbots to their online stores, and many of them confidently invent products, prices and return rules. A wrong price or a made-up policy is not a cosmetic bug: the retailer may be held to it, and shoppers stop trusting the store. Saffron Retail Group (a fictional Indian omnichannel retailer) wants an assistant on its online store that shoppers can rely on.

## Problem statement

Build a grounded product-discovery assistant over a fixed catalogue of 5,000 products and a store policy. It must:

- answer short, misspelt, often Hinglish shopper questions;
- cite a product ID or policy section for every factual claim;
- ask a short clarifying question when more than one product matches and they differ in what was asked;
- refuse when the store doesn't sell the item or the catalogue or policy doesn't contain the answer;
- report latency and token cost per query.

## Solution built

A rules-first assistant. Code makes every decision and copies every fact from the catalogue. An LLM is used only as a fallback when the rules can't understand a message.

| Action | When | Example |
|---|---|---|
| **answer** | one match, or all matches agree; cheapest; comparison; list; policy | "Chargit QuillBolt red earphones kitne ke" |
| **clarify** | several products match and differ in what was asked | "green running shoes kitne ke hai" |
| **refuse** | not sold, other brand, fact not in catalogue, policy gap | "redmi note 13 price" |

- **Grounded by design:** prices, stock and attributes come straight from the catalogue row that is cited. A final guard removes any ₹ amount not backed by a cited product, the policy, or the shopper's own budget.
- **Built for Indian shoppers:** Hinglish, misspellings and split names ("krida ion flex" → Kridaa IonFlex) are understood, and budget, colour and material carry over between turns.
- **Web demo:** a chat UI with a Sources panel showing the cited catalogue rows or policy text, the reasoning behind each decision, and latency and token cost per query.
- **Tools and technologies:** Python 3.11 (uv), FastAPI, Pydantic, rapidfuzz, HTML/CSS/JavaScript, Groq API (`openai/gpt-oss-20b`), pytest, ruff.

**Results** (official `evaluate.py`, 40 dev questions): primary score **1.000** (baseline 0.73), **0** hallucinated prices, about **1 ms** per query, **0** tokens. Test-set predictions: `submission/R3_predictions.jsonl`.

## Architecture

```
shopper message
   │
   ▼
parser.py ──── vocabulary built from the catalogue itself: brands, product lines, colours, materials,
   │           attribute values; joins "ripple flex"→RippleFlex, fuzzy "krida"→Kridaa (rapidfuzz)
   │           + lexicon.py: Hinglish/misspellings, product-type aliases, question patterns, units, budgets
   ▼
decide.py ──── policy question? → policy_router.py (sub-section or "policy gap")
   │           follow-up turn?  → apply the new constraints to the previous turn's products (memory)
   │           named product?   → its variants, narrowed by colour / size / pack
   │           generic request? → filters.py (sub-category, colour, material, gender, units, budget, stock)
   │           then: answer · clarify (variants differ in the asked field) · refuse
   │
   ├── rules refused because they did not understand the message (and LLM_PROVIDER=groq)?
   │      → LLM rewrites it in catalogue words → parser → decide again (rules still decide everything)
   ▼
response.py ── templates; every price / stock / attribute copied from the cited catalogue row;
   │           stated_prices and stated_facts use exact catalogue field names
   ▼
guard.py ───── re-checks with the scorer's rules: every ₹ amount must be a cited product's price/MRP/discount,
   │           a policy amount (if policy is cited) or the shopper's own budget; anything else is removed
   ▼
reply + latency_ms + tokens + cost
```

## How to run

- **Start the chatbot:** see [`FULL_CODE/COMMANDS.md`](FULL_CODE/COMMANDS.md)
- **Questions to try**, by category (answer, clarify, policy, refusal, multi-turn, LLM): see [`FULL_CODE/questions.md`](FULL_CODE/questions.md)

```bash
cd FULL_CODE
uv sync                          # install locked dependencies
cp .env.example .env             # optional: add GROQ_API_KEY for the LLM fallback
uv run python main.py serve      # chatbot at http://127.0.0.1:8000, API docs at /api/docs
```

Put the problem pack's `data/` files in `FULL_CODE/data/` (git-ignored). No models need downloading.

**Environment variables** (`FULL_CODE/.env.example`): `LLM_PROVIDER` (`groq` or `none`), `GROQ_API_KEY`, and optionally `LLM_MODEL` and `DATA_DIR`. Other settings live in `FULL_CODE/config.yaml`.

**Submission file, dev score and latency/cost report:**

```bash
LLM_PROVIDER=none uv run python main.py predict --questions data/questions_test.csv --out ../submission/R3_predictions.jsonl
uv run python main.py predict --questions data/questions_dev.csv --out reports/R3_dev_predictions.jsonl
uv run python scripts/evaluate.py --submission reports/R3_dev_predictions.jsonl --truth data/questions_dev_truth.jsonl --data-dir data
uv run python main.py report --predictions ../submission/R3_predictions.jsonl
```

**Tests** (71 tests on a small synthetic store, LLM calls mocked):

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## AI usage

- **Runtime:** rules first. The Groq LLM (`openai/gpt-oss-20b`) is called only when the rules can't understand a message. It rewrites the message in catalogue words, the output is validated with Pydantic, and the rules then decide again. It never produces a price, stock value or product ID. It has timeouts, retries and rate-limit handling, and falls back to rules-only when unavailable. The submission was generated offline (`LLM_PROVIDER=none`).
- **Coding assistant:** Claude Code (Anthropic) helped write and review code, tests and docs. The team reviewed all code and can explain it.

## Pre-built and third-party code

- **Before Day 1, for this hackathon:** our Round 1 prototype. Its pipeline design and price-guard idea were reused, and the code was rewritten for the real data.
- **Organisers:** `FULL_CODE/scripts/evaluate.py` (unchanged) and the data pack (not committed).
- **Open-source libraries:** FastAPI, Uvicorn, Pydantic, httpx, rapidfuzz, PyYAML, python-dotenv, NumPy, pandas, pytest, ruff and pip-audit, with versions pinned in `FULL_CODE/uv.lock` (MIT, BSD or Apache-2.0). Our code is MIT-licensed (`LICENSE`).

## Limitations

- The Hinglish lexicon and question patterns are hand-written, so unusual phrasing can be refused. The LLM fallback helps, but needs network access and adds about 0.5 s.
- Very badly misspelt brand names are ignored, and the product line alone is then used.
- Ambiguous questions follow the README's clarify rule, which may differ from the hidden test answers.
- Conversation memory and rate limiting are in-memory (demo scale, no authentication).
- The dev score is on 40 questions. Expect a lower score on the 150 test questions.
