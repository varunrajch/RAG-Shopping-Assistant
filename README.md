# TEAM-001450 · R3: The Conversational Shopping Assistant That Doesn't Lie

A grounded product-discovery chat assistant for Saffron Retail Group's 5,000-product catalogue. Every fact it states is copied from the catalogue or the store policy and carries a product ID or policy-section citation. It never invents a price.

Team **Tech Titans** · Problem **R3 (Retail)**

## What it does

Shoppers ask short, misspelt, often Hinglish questions ("krida ion flex football rate?", "TPE wali 600 ke andar"). For each message the assistant picks one action:

| Action | When | Example |
|---|---|---|
| **answer** | one product matches, or all matches agree on what was asked; a cheapest/costliest question; a comparison; a "show me" list; a grounded "no" (`induction_compatible: false`); a policy question | "Sootli DuneTrek 26 cm kadai induction pe chalegi?" → "No … [SKU-I09A3NWE]" |
| **clarify** | the shopper means *one* product, several match, and they differ in what was asked | "green running shoes kitne ke hai" → lists the options with prices and asks which one |
| **refuse** | the store doesn't sell it, or the catalogue/policy doesn't contain the fact | "redmi note 13 price" → "I don't have that." |

Users: shoppers on saffronretail.example. In the web demo ("Shopping Assistant") every answer shows its sources automatically: the cited catalogue rows (price, MRP, stock, attributes) or policy text appear in the Sources panel beside the chat, and clicking a product ID in the reply jumps to its row. The demo also shows the reasoning behind each decision and a live latency and token-cost panel.

**Results** (official `evaluate.py`, dev set of 40 questions):

| | Ours | Baseline |
|---|---|---|
| Primary score | **1.000** | 0.73 |
| Action accuracy | 1.000 | |
| Hallucinated prices | **0** | 0 |
| Mean / p95 latency | ~1 ms / ~1.5 ms | |
| LLM tokens per query | 0 (submission generated offline) | 0 |

The dev set is small and its product lines differ from the test set's, so treat the dev score as a sanity check, not a promise. The test-set predictions are in `submission/R3_predictions.jsonl`.

## How to run

The quickest way to start the chatbot is in [`FULL_CODE/COMMANDS.md`](FULL_CODE/COMMANDS.md). Example questions for every behaviour (answer, clarify, policy, refusal, multi-turn) are in [`FULL_CODE/questions.md`](FULL_CODE/questions.md). The short version:

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.11 automatically).

```bash
cd FULL_CODE
uv sync                                   # install the locked dependencies (uv.lock)
cp .env.example .env                      # then paste your Groq key (optional LLM fallback)
```

**Data:** copy the problem pack's `data/` files (`catalogue.jsonl`, `catalogue.csv`, `policy.md`, `questions_*.csv`, `questions_dev_truth.jsonl`) into `FULL_CODE/data/`. That folder is git-ignored and never committed. No models need downloading.

```bash
# web demo: http://127.0.0.1:8000
uv run python main.py serve

# terminal chat
uv run python main.py chat

# test-set submission file
uv run python main.py predict --questions data/questions_test.csv --out ../submission/R3_predictions.jsonl

# dev-set score with the organisers' scorer
uv run python main.py predict --questions data/questions_dev.csv --out reports/R3_dev_predictions.jsonl
uv run python scripts/evaluate.py --submission reports/R3_dev_predictions.jsonl \
    --truth data/questions_dev_truth.jsonl --data-dir data --out reports/dev_score.json --details

# latency and token-cost report per query
uv run python main.py report --predictions ../submission/R3_predictions.jsonl
```

**Environment variables** (see `FULL_CODE/.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `none` (config) / `groq` (`.env.example`) | `none` = fully offline rules engine; `groq` = call the LLM only when the rules cannot understand a message |
| `GROQ_API_KEY` | – | only read when `LLM_PROVIDER=groq`; never logged and never sent to the browser |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Groq model name |
| `DATA_DIR` | `data` | where the pack's files live |
| `QUERY_LOG_PATH` | `logs/queries.jsonl` | per-query log (latency, tokens, action) |

All other settings (fuzzy-match threshold, citation limits, timeouts, token costs, CORS, rate limit) live in `FULL_CODE/config.yaml`.

## How to run the tests

```bash
cd FULL_CODE && uv run pytest
```

There are 62 tests. They run on a small synthetic store in `tests/fixtures/store/`, so they don't need the pack data, and every LLM call is mocked. They cover parsing (Hinglish, misspellings, units, budgets), the answer/clarify/refuse rules, multi-turn memory, the price guard, the official submission format, the LLM fallback and validation, and the API. Lint and format: `uv run ruff check . && uv run ruff format --check .`.

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

| Folder / file | Role |
|---|---|
| `FULL_CODE/main.py` | single entry point: `serve`, `chat`, `predict`, `report` |
| `FULL_CODE/src/shopassist/` | core logic, independent of the web framework (catalogue, policy, parser, filters, decide, response, guard, assistant, report) |
| `FULL_CODE/src/shopassist/llm/` | optional Groq client (fallback only), prompts and output validation |
| `FULL_CODE/api/app.py` | FastAPI routes: `/api/chat` (reply + its sources), `/api/product/{id}`, `/api/policy/{id}`, `/api/metrics`, `/health` |
| `FULL_CODE/web/` | static chat UI and SVG logo (HTML/CSS/JS, renders text with `textContent` only) |
| `FULL_CODE/scripts/evaluate.py` | the organisers' official scorer, unchanged |
| `FULL_CODE/config.yaml` | all thresholds, limits and model settings |
| `submission/R3_predictions.jsonl` | test-set predictions |

**Design choice:** a small model is good at wording and bad at arithmetic, counting and remembering prices. So decisions, filtering, min/max and every number are done in code. That makes each query cost about 1 ms and 0 tokens, and it makes a hallucinated price structurally impossible: the guard would remove one even if a bug produced it.

## AI usage

- **In the app, rules first:** every message is handled by a deterministic retrieval and rules engine. The submission file was produced with `LLM_PROVIDER=none` (fully offline, 0 tokens), so it is reproducible without network access.
- **LLM fallback (`LLM_PROVIDER=groq`):** the Groq API with `openai/gpt-oss-20b` (configurable, `reasoning_effort: low`). It is called **only** when the rules refuse because they did not understand the message: no product type or name was recognised, or nothing matched while unknown words remained. It is never called when the rules are sure: real brands we don't carry, unsold items, missing attributes, policy gaps, or any answer or clarification.
  - It returns JSON `{"rewritten_query", "sub_category"}`, validated with Pydantic. The product type must be one of the catalogue's 91 sub-categories, and the rewrite is limited to 200 characters of plain text.
  - The rewrite is never shown to the shopper. It goes back through the same parser and decision rules, so every price, stock value and product ID still comes from the catalogue, and the guard still checks every amount. If the retry is still a refusal, the original refusal is kept.
  - Example: "bread garam karne wali machine kitne ki" → "What is the price of a toaster?" → the rules list toasters and ask which one. That took about 900 tokens and 0.5 s, roughly $0.0001.
  - Shopper text is passed as delimited data with an instruction to ignore embedded instructions. Calls have an 8 s timeout, bounded retries with back-off, and a 60 s circuit-breaker. With no key, a bad key or Groq down, the app silently runs rules-only. Tokens come from the API's `usage` field and are reported per query with a cost estimate.
- **AI coding assistant:** Claude Code (Anthropic) helped write and review code, tests and documentation. Every team member reviewed the code and can explain it.

## Pre-built and third-party code

- **Written before Day 1, for this hackathon:** our Round 1 prototype (a Streamlit app on a self-generated catalogue). Round 2 reuses its *design*: the parse → memory → search → decide → reply → guard pipeline, the idea of a price guard, and some Hinglish word mappings. The code was rewritten for the real catalogue schema, policy numbering and scorer.
- **Provided by the organisers:** `FULL_CODE/scripts/evaluate.py` (unchanged, used for scoring and in a format test) and the problem pack's data (not committed).
- **Open-source libraries** (versions pinned in `FULL_CODE/uv.lock`): FastAPI, Uvicorn, Pydantic, httpx, rapidfuzz, PyYAML, python-dotenv, NumPy and pandas (for the scorer); pytest, ruff and pip-audit for development. All are MIT, BSD or Apache-2.0 licensed.
- No templates or copied snippets beyond the above. Our code is under the MIT licence (`LICENSE`).

## Limitations

- **Rules and lexicon coverage.** Hinglish words, product-type aliases and question patterns are hand-written. A phrasing nobody anticipated (a new slang word for a product type, or an unusual way to ask about an attribute) can lead to a refusal or a less specific answer. The LLM fallback helps with unrecognised wording, but it adds about 0.5 s and needs network access.
- **Names.** Fuzzy name matching is tuned to a single threshold (`fuzzy_name_cutoff: 85`). A very badly misspelt brand ("sonic" for Sonique) is ignored, and the product line alone is then used.
- **Clarify vs answer** follows the README rule ("differ in what was asked"). When the hidden truth expects a different reading of an ambiguous question, we lose that question's action credit.
- **"Missing ≠ false"** is respected, so many attribute questions are correctly refused. A shopper may find "the catalogue doesn't say" unhelpful, even though it is honest.
- **The demo server** keeps conversation memory in process (up to 1,000 conversations) with a simple in-memory rate limiter. A production deployment would need a shared store and real authentication.
- **The dev score of 1.000** is on 40 questions. The 150 test questions target different product lines, so expect a lower test score.

Next steps: learn aliases from shopper logs, add a multilingual embedding fallback for unknown product types, and add a feedback button that flags wrong answers for review.
