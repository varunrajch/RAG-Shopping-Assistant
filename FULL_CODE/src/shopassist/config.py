"""Settings: config.yaml for tunables, environment variables for secrets and overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

FULL_CODE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = FULL_CODE_DIR / "config.yaml"


@dataclass(frozen=True)
class MatchingSettings:
    fuzzy_name_cutoff: int
    fuzzy_min_token_len: int
    max_join_tokens: int


@dataclass(frozen=True)
class DecisionSettings:
    max_cited_products: int
    max_list_items: int
    max_clarify_options: int
    max_same_answer_citations: int
    extra_policy_citations: int


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    reasoning_effort: str | None
    base_url: str
    temperature: float
    max_tokens_rewrite: int
    timeout_s: float
    max_retries: int
    cost_per_million_in: float
    cost_per_million_out: float
    api_key: str | None


@dataclass(frozen=True)
class APISettings:
    host: str
    port: int
    cors_origins: tuple[str, ...]
    max_message_chars: int
    rate_limit_per_minute: int


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    catalogue_path: Path
    policy_path: Path
    query_log_path: Path
    matching: MatchingSettings
    decision: DecisionSettings
    llm: LLMSettings
    api: APISettings


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else FULL_CODE_DIR / p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load config.yaml once. Env vars override it: LLM_PROVIDER, LLM_MODEL, GROQ_API_KEY, DATA_DIR,
    QUERY_LOG_PATH."""
    load_dotenv(FULL_CODE_DIR / ".env")
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    paths = raw["paths"]
    data_dir = _resolve(os.getenv("DATA_DIR", paths["data_dir"]))
    llm_raw = dict(raw["llm"])
    llm_raw["provider"] = os.getenv("LLM_PROVIDER", llm_raw["provider"]).strip().lower()
    llm_raw["model"] = os.getenv("LLM_MODEL", llm_raw["model"])
    api_raw = dict(raw["api"])
    api_raw["cors_origins"] = tuple(api_raw["cors_origins"])
    return Settings(
        data_dir=data_dir,
        catalogue_path=data_dir / paths["catalogue"],
        policy_path=data_dir / paths["policy"],
        query_log_path=_resolve(os.getenv("QUERY_LOG_PATH", paths["query_log"])),
        matching=MatchingSettings(**raw["matching"]),
        decision=DecisionSettings(**raw["decision"]),
        llm=LLMSettings(**llm_raw, api_key=os.getenv("GROQ_API_KEY") or None),
        api=APISettings(**api_raw),
    )
