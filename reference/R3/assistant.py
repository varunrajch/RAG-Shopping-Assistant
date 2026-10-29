"""
assistant.py
Connects the modules for one chat turn and logs every query:

  message -> parse.py -> memory.py -> search.py -> decide.py -> reply.py -> reply

Each query is written to logs/queries.jsonl with latency in ms, input and
output tokens, and whether the language model was called.
"""
import json
import time
from datetime import datetime

import config
from decide import decide_policy, decide_product
from index import load_index
from llm import LocalLLM
from parse import parse_query
from reply import build_reply
from search import search_products


class ShoppingAssistant:
    def __init__(self):
        self.index = load_index()
        self.llm = LocalLLM()

    def ask(self, query, memory):
        start = time.perf_counter()
        self.llm.reset_counters()
        llm = self.llm if self.llm.available() else None

        parsed = parse_query(query, self.index, llm)
        if parsed.is_policy:
            filters = {}
            decision = decide_policy(self.index, parsed)
        else:
            filters = memory.apply(parsed)
            result = search_products(self.index, parsed, filters)
            decision = decide_product(self.index, parsed, filters, result)
        text, citations, removed = build_reply(decision, query, filters, self.index, llm)

        out = {
            "query": query,
            "reply": text,
            "decision": decision.kind,
            "mode": decision.mode,
            "citations": citations,
            "filters": {k: v for k, v in filters.items() if v},
            "parsed": parsed.as_dict(),
            "memory": memory.as_dict(),
            "matches": decision.total,
            "differ_on": decision.differ_on,
            "removed_by_check": removed,
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "tokens_in": self.llm.tokens_in,
            "tokens_out": self.llm.tokens_out,
            "llm_called": self.llm.called,
        }
        self._log(out)
        return out

    def _log(self, out):
        config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        keep = ["query", "decision", "mode", "filters", "latency_ms", "tokens_in",
                "tokens_out", "llm_called", "removed_by_check"]
        line = {"time": datetime.now().isoformat(timespec="seconds"), **{k: out[k] for k in keep}}
        with open(config.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # Quick command line chat: python assistant.py
    from memory import SessionMemory
    bot, mem = ShoppingAssistant(), SessionMemory()
    print("Type a question (empty line to quit).")
    while q := input("> ").strip():
        r = bot.ask(q, mem)
        print(r["reply"], f"\n  [{r['decision']} | {r['latency_ms']} ms | llm={r['llm_called']}]\n")
