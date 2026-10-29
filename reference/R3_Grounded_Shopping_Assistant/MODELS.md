# R3 — Recommended models (small, open licence, offline, CPU-friendly)

The PS (problem statement) promises "a small embedding model and a small instruct model, pre-cached for offline use".

- An **embedding model** turns text into a list of numbers, so that similar texts get similar numbers.
- An **instruct model** (here a small LLM, a large language model) follows instructions and writes text, like a chat AI.

These are our recommendations. Organisers may also host mirrors (extra download copies) of the same files.

**Rules:**

1. **You do not have to use them.** A pure retrieval + rules system is allowed (code that finds products and applies rules, with no AI model).
2. Whatever you use, it must run offline during judging.
3. You must state its licence.

All facts below (repo IDs, licences, file sizes, pinned commits) were checked on the Hugging Face API on 2026-10-21. A pinned revision is a fixed version of the files, so everyone downloads exactly the same model.

| Role | Hugging Face repo (pinned revision) | Licence | Download size | Notes |
|---|---|---|---|---|
| **Embedding (default)** | [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) @ `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | Apache-2.0 | ~92 MB | 384-dim (each text becomes 384 numbers). Very fast on CPU. It is English-centric, so Hinglish words like "kitne ka" carry little meaning for it. Combine it with keyword / character n-gram matching (matching short runs of letters). |
| Embedding (multilingual, optional) | [`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) @ `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` | Apache-2.0 | ~480 MB | 50+ languages. Romanised Hindi (Hinglish) is **not** an advertised strength, so test it on the dev set before relying on it. |
| **Instruct LLM (default)** | [`Qwen/Qwen2.5-1.5B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) @ `91cad51170dc346986eccefdc2dd33a9da36ead9`, file `qwen2.5-1.5b-instruct-q4_k_m.gguf` | Apache-2.0 | 1.12 GB | GGUF is the model file format used by llama.cpp (this file is 4-bit compressed). Runs on CPU with `llama-cpp-python` / `llama.cpp` / Ollama in ~2 GB RAM. |
| Instruct LLM (low-RAM) | [`Qwen/Qwen2.5-0.5B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) @ `9217f5db79a29953eb74d5343926648285ec7e67`, file `qwen2.5-0.5b-instruct-q4_k_m.gguf` | Apache-2.0 | 0.49 GB | Faster and weaker. Fine for rewriting a grounded answer, weak at reasoning. |

**Licence trap:** `Qwen/Qwen2.5-3B-Instruct` (and its GGUF) is **not** Apache-2.0. It uses the *Qwen Research License* (non-commercial / research use only). The 0.5B, 1.5B and 7B Qwen2.5 instruct models are Apache-2.0. If you choose another model, check its licence yourself.

## Download (once, while you have internet)

Run these commands from your problem folder (the folder with `README.md`). On Mac/Linux, type `python3` instead of `python`.

**Step 1 (optional): install `huggingface_hub`.** The script falls back to plain HTTPS without it.

```
pip install huggingface_hub
```

If `pip` is not recognised, use `python -m pip install huggingface_hub` instead.

**Step 2: run ONE of these three commands.** Files go into `./models`.

**Option A, default:** MiniLM embedding + Qwen2.5-1.5B GGUF (~1.2 GB).

```
python download_models.py
```

**Option B, small:** MiniLM + Qwen2.5-0.5B GGUF (~0.6 GB).

```
python download_models.py --set small
```

**Option C, all:** everything in the table (~2.2 GB).

```
python download_models.py --set all
```

**Step 3: load the models in your code.** Files land in `models/<repo_name>/`.

- Load the embedding with `SentenceTransformer("models/all-MiniLM-L6-v2")`.
- Load the LLM with e.g. `llama_cpp.Llama(model_path="models/Qwen2.5-1.5B-Instruct-GGUF/qwen2.5-1.5b-instruct-q4_k_m.gguf", n_ctx=4096)`.

## Hard-won advice

- **Never let the LLM produce a price or product ID on its own.** Retrieve products, decide the action, and pass the LLM only the facts it may use. Copy prices from the catalogue into `stated_prices` with code, not with the model. Each hallucinated price (a price not taken from the catalogue) costs −3 on that question.
- A small model is good at *wording* and bad at *arithmetic and counting*. Do filtering, cheapest/most-expensive and clarify-vs-answer decisions in code.
- Report latency (time per answer) and tokens per query honestly (`latency_ms`, `tokens_in`, `tokens_out`). Judges look at cost.
