"""The batch writer must produce a file the official scorer accepts."""

import json
import sys
from pathlib import Path

import pytest

from shopassist.predict import QuestionFileError, predict, read_questions

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "store"
sys.path.insert(0, str(SCRIPTS))
import evaluate  # noqa: E402  (the organisers' scorer, unchanged)


def test_predictions_pass_official_format_validation(assistant, tmp_path):
    out = tmp_path / "pred.jsonl"
    assert predict(assistant, FIXTURES / "questions.csv", out) == 5
    rows = evaluate.load_jsonl(out, "submission")
    validated = evaluate.validate_submission(rows)
    assert set(validated) == {"Q-T1", "Q-T2", "Q-T3", "Q-T4", "Q-T5"}
    for line in out.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        assert obj["latency_ms"] >= 0 and obj["tokens_in"] == 0


def test_turns_are_answered_in_conversation_order(tmp_path):
    csv_path = tmp_path / "q.csv"
    csv_path.write_text(
        "question_id,conversation_id,turn,question_text\nB,C1,2,lavender wali\nA,C1,1,vistaair mat price\n",
        encoding="utf-8",
    )
    assert [r["question_id"] for r in read_questions(csv_path)] == ["A", "B"]


def test_bad_question_file_is_reported(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,text\n1,hello\n", encoding="utf-8")
    with pytest.raises(QuestionFileError):
        read_questions(bad)
    with pytest.raises(QuestionFileError):
        read_questions(tmp_path / "missing.csv")
