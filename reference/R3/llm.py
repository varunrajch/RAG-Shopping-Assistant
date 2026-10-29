"""
llm.py
Tiny client for a local Ollama server. If Ollama is not running every call
returns None and the rest of the app falls back to rules and templates.
It also counts input and output tokens for the query log.
"""
import json
import time

import requests

import config


class LocalLLM:
    def __init__(self):
        self._available = None
        self._checked_at = 0.0
        self.reset_counters()

    def reset_counters(self):
        """Called at the start of every user query."""
        self.called = False
        self.tokens_in = 0
        self.tokens_out = 0

    def available(self):
        """Is Ollama running with our model? Checked at most every 30 seconds."""
        if not config.USE_LLM:
            return False
        if self._available is None or time.time() - self._checked_at > 30:
            try:
                tags = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=1).json()
                names = [m["name"] for m in tags.get("models", [])]
                self._available = any(n.startswith(config.LLM_MODEL) for n in names)
            except (requests.RequestException, ValueError):
                self._available = False
            self._checked_at = time.time()
        return self._available

    def chat(self, system, user, json_mode=False, max_tokens=60):
        """Send one prompt. Returns the text (or a dict in json mode), or None on failure."""
        if not self.available():
            return None
        body = {"model": config.LLM_MODEL, "stream": False,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "options": {"temperature": 0.1, "num_predict": max_tokens}}
        if json_mode:
            body["format"] = "json"
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", json=body,
                              timeout=config.LLM_TIMEOUT_S).json()
        except (requests.RequestException, ValueError):
            self._available = False
            return None
        self.called = True
        self.tokens_in += r.get("prompt_eval_count", 0)
        self.tokens_out += r.get("eval_count", 0)
        text = r.get("message", {}).get("content", "").strip()
        if json_mode:
            try:
                return json.loads(text)
            except ValueError:
                return None
        return text
