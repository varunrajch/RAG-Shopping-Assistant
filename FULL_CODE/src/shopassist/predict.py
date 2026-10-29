"""Batch mode: answer every question in a questions CSV and write the submission JSONL."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from shopassist.assistant import ShoppingAssistant

logger = logging.getLogger(__name__)
REQUIRED_COLUMNS = {"question_id", "conversation_id", "turn", "question_text"}


class QuestionFileError(Exception):
    """Raised when the questions CSV is missing or has the wrong columns."""


def read_questions(path: Path) -> list[dict[str, str]]:
    """Rows sorted so each conversation's turns are answered in order."""
    if not path.is_file():
        raise QuestionFileError(f"Questions file not found: {path}")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise QuestionFileError(f"{path.name} is missing columns: {sorted(missing)}")
        rows = list(reader)
    for row in rows:
        if not row["turn"].strip().isdigit():
            raise QuestionFileError(f"Bad turn number {row['turn']!r} for {row['question_id']}")
    return sorted(rows, key=lambda r: (r["conversation_id"], int(r["turn"])))


def predict(assistant: ShoppingAssistant, questions: Path, out: Path) -> int:
    """Write one submission line per question. Returns the number of lines written."""
    rows = read_questions(questions)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            result = assistant.ask(row["question_text"], conversation_id=row["conversation_id"])
            line = {
                "question_id": row["question_id"],
                **result.reply.model_dump(
                    include={
                        "action",
                        "answer_text",
                        "cited_product_ids",
                        "cited_policy_sections",
                        "stated_prices",
                        "stated_facts",
                    }
                ),
                "latency_ms": result.latency_ms,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
            }
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    logger.info("wrote %d predictions to %s", len(rows), out)
    return len(rows)
