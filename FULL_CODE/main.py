"""Single entry point.

uv run python main.py predict --questions data/questions_test.csv --out ../submission/R3_predictions.jsonl
uv run python main.py chat                 # chat in the terminal
uv run python main.py serve                # web demo on http://127.0.0.1:8000
uv run python main.py report --predictions ../submission/R3_predictions.jsonl
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from shopassist.assistant import ShoppingAssistant  # noqa: E402
from shopassist.catalogue import CatalogueError  # noqa: E402
from shopassist.config import get_settings  # noqa: E402
from shopassist.policy import PolicyError  # noqa: E402
from shopassist.predict import QuestionFileError, predict  # noqa: E402
from shopassist.report import latency_report  # noqa: E402

logger = logging.getLogger("shopassist")


def _chat(assistant: ShoppingAssistant) -> None:
    print("Ask the store assistant (empty line to quit).")
    while True:
        try:
            message = input("> ").strip()
        except EOFError:
            break
        if not message:
            break
        result = assistant.ask(message, conversation_id="cli")
        print(result.reply.answer_text)
        print(
            f"  [{result.reply.action} | {result.latency_ms} ms | tokens {result.tokens_in}/"
            f"{result.tokens_out}]\n"
        )


def _serve() -> None:
    import uvicorn

    sys.path.insert(0, str(HERE))
    settings = get_settings()
    uvicorn.run("api.app:app", host=settings.api.host, port=settings.api.port, log_level="info")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="R3 grounded shopping assistant")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("predict", help="answer a questions CSV and write submission JSONL")
    p.add_argument("--questions", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    sub.add_parser("chat", help="interactive chat in the terminal")
    sub.add_parser("serve", help="run the web demo")
    r = sub.add_parser("report", help="latency and token-cost report for a predictions file")
    r.add_argument("--predictions", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.command == "serve":
        _serve()
        return 0
    if args.command == "report":
        print(latency_report(args.predictions, get_settings().llm))
        return 0
    try:
        assistant = ShoppingAssistant()
        if args.command == "predict":
            predict(assistant, args.questions, args.out)
        else:
            _chat(assistant)
    except (CatalogueError, PolicyError, QuestionFileError) as exc:
        logger.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
