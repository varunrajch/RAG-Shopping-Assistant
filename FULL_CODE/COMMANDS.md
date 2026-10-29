# How to run the chatbot

## First time only

Open a terminal and run:

```bash
cd ~/Desktop/Varun/RAG-Shopping-Assistant/FULL_CODE
uv sync
```

Make sure the problem pack's data files are in `FULL_CODE/data/`, and that your Groq key is in `FULL_CODE/.env`
after `GROQ_API_KEY=` (the key is optional; without it the chatbot still works, just without the LLM fallback).

## Every time

```bash
cd ~/Desktop/Varun/RAG-Shopping-Assistant/FULL_CODE
uv run python main.py serve
```

Then open in your browser:

| What | Link |
|---|---|
| The chatbot | **http://127.0.0.1:8000** |
| FastAPI endpoints (interactive docs, try every endpoint) | **http://127.0.0.1:8000/api/docs** |

To stop the chatbot, press **Ctrl + C** in the terminal.

Questions to try are in [`questions.md`](questions.md).

## API endpoints

| Method | Endpoint | What it does |
|---|---|---|
| POST | `/api/chat` | Ask a question. Body: `{"conversation_id": "demo1", "message": "6 mm yoga mat chahiye"}` |
| POST | `/api/reset` | Start a new conversation. Body: `{"conversation_id": "demo1"}` |
| GET | `/api/product/{product_id}` | One catalogue row, e.g. `/api/product/SKU-LIF2LAV2` |
| GET | `/api/policy/{section_id}` | One policy section, e.g. `/api/policy/1.1` |
| GET | `/api/metrics` | Latency, tokens and cost for this session, plus the dev score |
| GET | `/health` | Returns `{"status": "ok"}` when the server is running |

In the docs page, click an endpoint → **Try it out** → **Execute**.

## If something goes wrong

**"address already in use"**: the chatbot is already running somewhere. Free the port, then start it again:

```bash
lsof -ti :8000 | xargs kill
```

**"uv: command not found"**: open a new terminal window (your `~/.zshrc` already adds `uv` to the path), or run
`export PATH="$HOME/.local/bin:$PATH"` once in the current window.
