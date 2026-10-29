"""Latency and token-cost report per query (problem statement deliverable 5)."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from shopassist.config import LLMSettings


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    k = (len(ordered) - 1) * pct / 100
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def summarise(rows: list[dict], llm: LLMSettings) -> dict:
    lat = [float(r["latency_ms"]) for r in rows]
    t_in = [int(r["tokens_in"]) for r in rows]
    t_out = [int(r["tokens_out"]) for r in rows]
    cost = [
        (i * llm.cost_per_million_in + o * llm.cost_per_million_out) / 1_000_000
        for i, o in zip(t_in, t_out, strict=True)
    ]
    actions: dict[str, int] = {}
    for r in rows:
        actions[r["action"]] = actions.get(r["action"], 0) + 1
    return {
        "queries": len(rows),
        "latency_ms": {
            "mean": round(statistics.fmean(lat), 2) if lat else 0.0,
            "p50": round(_percentile(lat, 50), 2),
            "p95": round(_percentile(lat, 95), 2),
            "max": round(max(lat, default=0.0), 2),
        },
        "tokens": {
            "mean_in": round(statistics.fmean(t_in), 1) if t_in else 0.0,
            "mean_out": round(statistics.fmean(t_out), 1) if t_out else 0.0,
            "total_in": sum(t_in),
            "total_out": sum(t_out),
            "queries_using_llm": sum(1 for i in t_in if i),
        },
        "cost_usd": {
            "per_query_mean": round(statistics.fmean(cost), 8) if cost else 0.0,
            "per_1000_queries": round(sum(cost) / max(len(rows), 1) * 1000, 4),
        },
        "actions": actions,
    }


def latency_report(path: Path, llm: LLMSettings) -> str:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    s = summarise(rows, llm)
    lines = [
        f"Latency / cost report for {path.name} ({s['queries']} queries)",
        f"  latency ms   mean {s['latency_ms']['mean']}  p50 {s['latency_ms']['p50']}  "
        f"p95 {s['latency_ms']['p95']}  max {s['latency_ms']['max']}",
        f"  tokens       mean in {s['tokens']['mean_in']}  mean out {s['tokens']['mean_out']}  "
        f"(LLM used on {s['tokens']['queries_using_llm']} queries)",
        f"  cost (USD)   per query {s['cost_usd']['per_query_mean']}  per 1000 queries "
        f"{s['cost_usd']['per_1000_queries']}",
        f"  actions      {s['actions']}",
    ]
    return "\n".join(lines)
