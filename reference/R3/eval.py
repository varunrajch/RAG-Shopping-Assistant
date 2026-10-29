"""
eval.py
Runs every test question through the assistant and reports:
  groundedness          share of replies whose every price, ID and stock fact matches
                        the cited catalogue row or policy section
  invented prices       rupee amounts not backed by a cited row (counted separately)
  refusal accuracy      expected "refuse" -> did refuse
  clarification accuracy expected "clarify" -> did ask
  answer hit rate       expected "answer" -> an expected product ID / policy section is cited
  latency               median and p95 in ms
  tokens                average input and output tokens per query

Multi turn questions share one session memory per conversation.
Output: results/eval_results.csv and results/summary.json

Run:  python eval.py          (USE_LLM=0 python eval.py for template replies only)
"""
import json
import re

import numpy as np
import pandas as pd

import config
from assistant import ShoppingAssistant
from memory import SessionMemory
from reply import ID_RE, POLICY_CITE_RE, PRICE_RE, STOCK_LABEL


def amounts(text):
    return [int((a or b).replace(",", "")) for a, b in PRICE_RE.findall(text)]


def check_grounded(reply, catalogue, policy, budget):
    """Check a reply line by line against the catalogue and policy.
    Returns (problems, invented_price_count)."""
    problems, invented = [], 0
    for line in reply.splitlines():
        ids = ID_RE.findall(line)
        sections = POLICY_CITE_RE.findall(line)
        for pid in ids:
            if pid not in catalogue.index:
                problems.append(f"unknown id {pid}")
        for sid in sections:
            if sid not in policy:
                problems.append(f"unknown policy section {sid}")
        # every rupee amount must be the price of a product cited on the same line,
        # an amount from a cited policy section, or the shopper's own budget
        allowed = {int(catalogue.at[p, "price"]) for p in ids if p in catalogue.index}
        for sid in sections:
            allowed |= set(amounts(policy.get(sid, "")))
        if budget:
            allowed.add(int(budget))
        for value in amounts(line):
            if value not in allowed:
                invented += 1
                problems.append(f"invented price {value}")
        # a stock claim must match the row
        if len(ids) == 1 and ids[0] in catalogue.index:
            truth = STOCK_LABEL[catalogue.at[ids[0], "stock_status"]]
            for label in STOCK_LABEL.values():
                if label in line and label != truth:
                    problems.append(f"wrong stock for {ids[0]}")
        # a fact line (bullet, numbered option or quote) must end with a citation
        if re.match(r"^\s*(- |\d+\. |> )", line) and not (ids or sections):
            problems.append("fact without citation")
    return problems, invented


def main():
    questions = json.loads(config.TEST_QUESTIONS_PATH.read_text(encoding="utf-8"))
    bot = ShoppingAssistant()
    catalogue = bot.index.df.set_index("product_id")
    policy = {s["id"]: s["text"] for s in bot.index.policy}

    rows, memory, conversation = [], SessionMemory(), None
    for q in questions:
        if q["conversation"] is None or q["conversation"] != conversation:
            memory = SessionMemory()  # a fresh session for every new conversation
        conversation = q["conversation"]
        r = bot.ask(q["query"], memory)

        cited = [c for _, c in r["citations"]]
        problems, invented = check_grounded(r["reply"], catalogue, policy,
                                            r["filters"].get("max_price"))
        expected = q["expected_ids"] or ([q["expected_policy"]] if q["expected_policy"] else [])
        rows.append({
            "id": q["id"], "type": q["type"], "query": q["query"],
            "expected": q["expected"], "decision": r["decision"],
            "correct_decision": r["decision"] == q["expected"],
            "hit": bool(set(cited) & set(expected)) if q["expected"] == "answer" else None,
            "grounded": not problems, "invented_prices": invented,
            "problems": "; ".join(problems), "cited": " ".join(cited),
            "latency_ms": r["latency_ms"], "tokens_in": r["tokens_in"],
            "tokens_out": r["tokens_out"], "llm_called": r["llm_called"],
            "reply": r["reply"],
        })

    df = pd.DataFrame(rows)

    def accuracy(label):
        part = df[df.expected == label]
        return round(float(part.correct_decision.mean()), 3) if len(part) else None

    answers = df[df.expected == "answer"]
    summary = {
        "questions": len(df),
        "llm_model": config.LLM_MODEL if df.llm_called.any() else "none (template replies)",
        "groundedness": round(float(df.grounded.mean()), 3),
        "invented_prices": int(df.invented_prices.sum()),
        "replies_with_invented_price": int((df.invented_prices > 0).sum()),
        "refusal_accuracy": accuracy("refuse"),
        "clarification_accuracy": accuracy("clarify"),
        "answer_hit_rate": round(float(answers.hit.astype(bool).mean()), 3),
        "decision_accuracy": round(float(df.correct_decision.mean()), 3),
        "latency_median_ms": round(float(np.median(df.latency_ms)), 1),
        "latency_p95_ms": round(float(np.percentile(df.latency_ms, 95)), 1),
        "avg_tokens_in": round(float(df.tokens_in.mean()), 1),
        "avg_tokens_out": round(float(df.tokens_out.mean()), 1),
        "llm_call_rate": round(float(df.llm_called.mean()), 3),
        "by_type": df.groupby("type").correct_decision.mean().round(3).to_dict(),
    }

    config.RESULTS_DIR.mkdir(exist_ok=True)
    df.to_csv(config.RESULTS_DIR / "eval_results.csv", index=False)
    (config.RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    print("\n=== Evaluation summary ===")
    for k, v in summary.items():
        print(f"{k:30s} {v}")
    wrong = df[~df.correct_decision | (df.hit == False) | ~df.grounded]  # noqa: E712
    if len(wrong):
        print("\nQuestions to look at:")
        print(wrong[["id", "query", "expected", "decision", "hit", "problems"]].to_string(index=False))
    print(f"\nSaved {config.RESULTS_DIR / 'eval_results.csv'} and summary.json")


if __name__ == "__main__":
    main()
