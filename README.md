# The Conversational Shopping Assistant That Doesn't Lie

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

**1. Install (first time only)**

```bash
cd FULL_CODE
uv sync
```

Put the problem pack's data files in `FULL_CODE/data/`. To use the LLM fallback, add your Groq key to
`FULL_CODE/.env` (copy `.env.example`); without a key the chatbot still works.

**2. Start**

```bash
cd FULL_CODE
uv run python main.py serve
```

**3. Open**

| What | Link |
|---|---|
| Chatbot | http://127.0.0.1:8000/ |
| FastAPI endpoints (interactive docs) | http://127.0.0.1:8000/api/docs#/ |

Questions to try, by category: [`FULL_CODE/questions.md`](FULL_CODE/questions.md). The same steps are in [`FULL_CODE/COMMANDS.md`](FULL_CODE/COMMANDS.md).

**Run the tests:** `cd FULL_CODE && uv run pytest` (71 tests)

**Results** (measured with the organisers' `evaluate.py` and our latency report):

| Metric | Value |
|---|---|
| Dev score (40 questions) | **1.000** (baseline 0.73) |
| Action accuracy | 1.000 |
| Grounded answers | 100% |
| Hallucinated prices | **0** |
| Test-set predictions | 150 questions: 82 answer, 30 clarify, 38 refuse |
| Latency per query | mean 0.9 ms, p95 1.6 ms |
| LLM tokens / cost per query | 0 / $0 (submission generated offline) |
| LLM fallback, when used | about 900 tokens, about 0.5 s, about $0.0001 per query |

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
