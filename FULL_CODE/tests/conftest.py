"""Shared fixtures. Tests run on a small synthetic store in tests/fixtures/store, never on the pack data,
and never call a real LLM."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "store"

# set before anything imports shopassist.config (settings are cached on first use)
os.environ["DATA_DIR"] = str(FIXTURES)
os.environ["LLM_PROVIDER"] = "none"
os.environ.setdefault(
    "QUERY_LOG_PATH", str(Path(os.environ.get("TMPDIR", "/tmp")) / "shopassist-test-log.jsonl")
)

from shopassist.assistant import ShoppingAssistant  # noqa: E402
from shopassist.config import get_settings  # noqa: E402
from shopassist.llm.client import NullLLM  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture()
def assistant(settings):
    """A fresh assistant (fresh conversation memory) for every test."""
    return ShoppingAssistant(settings, llm=NullLLM())


@pytest.fixture(scope="session")
def shared_assistant(settings):
    """Read-only use: parser / catalogue lookups."""
    return ShoppingAssistant(settings, llm=NullLLM())
