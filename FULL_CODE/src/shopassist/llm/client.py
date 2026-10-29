"""LLM clients. The assistant works fully without one (NullLLM); Groq is an optional extra.

The LLM never produces a price, stock value, product ID or the answer/clarify/refuse decision.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from shopassist.config import LLMSettings

logger = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_INLINE_WAIT_S = 2.0  # wait at most this long inside one chat turn
DOWN_AFTER_FAILURE_S = 30.0  # then fall back to rules-only for this long


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int

    def as_json(self) -> dict | None:
        try:
            data = json.loads(self.text)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None


class LLMClient(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    def complete(
        self, system: str, user: str, max_tokens: int, json_mode: bool = False
    ) -> LLMResult | None: ...


class NullLLM:
    """Used when LLM_PROVIDER=none or no key is configured: every call is a no-op."""

    name = "none"

    @property
    def available(self) -> bool:
        return False

    def complete(self, system: str, user: str, max_tokens: int, json_mode: bool = False) -> LLMResult | None:
        return None


class GroqLLM:
    """Groq's OpenAI-compatible chat API with timeouts, bounded retries and back-off."""

    name = "groq"

    def __init__(self, settings: LLMSettings, http: httpx.Client | None = None):
        self.settings = settings
        self._http = http or httpx.Client(timeout=settings.timeout_s)
        self._down_until = 0.0

    @property
    def available(self) -> bool:
        return bool(self.settings.api_key) and time.monotonic() >= self._down_until

    def complete(self, system: str, user: str, max_tokens: int, json_mode: bool = False) -> LLMResult | None:
        if not self.available:
            return None
        body: dict = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.settings.temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.settings.reasoning_effort:
            body["reasoning_effort"] = self.settings.reasoning_effort
        headers = {"Authorization": f"Bearer {self.settings.api_key}"}
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        pause = DOWN_AFTER_FAILURE_S
        for attempt in range(self.settings.max_retries + 1):
            try:
                resp = self._http.post(url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                logger.warning("LLM request failed (attempt %d): %s", attempt + 1, type(exc).__name__)
                wait = min(2.0, 0.4 * 2**attempt)
            else:
                if resp.status_code == 200:
                    return self._parse(resp)
                logger.warning("LLM returned HTTP %d (attempt %d)", resp.status_code, attempt + 1)
                if resp.status_code not in RETRY_STATUS:
                    break
                wait = _retry_after(resp) or min(2.0, 0.4 * 2**attempt)
                if wait > MAX_INLINE_WAIT_S:
                    # rate limited for a while: pause the LLM only as long as the API asks
                    pause = min(wait, DOWN_AFTER_FAILURE_S)
                    break
            time.sleep(wait)
        # stop calling for a short while so a slow or limited API does not slow every chat turn
        self._down_until = time.monotonic() + pause
        return None

    @staticmethod
    def _parse(resp: httpx.Response) -> LLMResult | None:
        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError):
            logger.warning("LLM response had an unexpected shape")
            return None
        return LLMResult(
            text=text.strip(),
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
        )


def _retry_after(resp: httpx.Response) -> float | None:
    """Seconds the API asks us to wait (Retry-After header), if it says so."""
    try:
        return max(0.0, float(resp.headers.get("retry-after", "")))
    except ValueError:
        return None


def build_llm(settings: LLMSettings) -> LLMClient:
    if settings.provider == "groq":
        if not settings.api_key:
            logger.warning("LLM_PROVIDER=groq but GROQ_API_KEY is not set; running without an LLM")
            return NullLLM()
        return GroqLLM(settings)
    return NullLLM()
