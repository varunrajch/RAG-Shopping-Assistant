"""One chat turn end to end:

    message -> parser -> decide -> response -> guard
                           |
                           +-- only if the rules could not understand the message (and an LLM is
                               configured): LLM rewrites it in catalogue words -> parser -> decide again

Also measures latency and LLM tokens per turn and keeps per-conversation state.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from shopassist.catalogue import load_catalogue
from shopassist.config import Settings, get_settings
from shopassist.decide import ConversationState, Decider, Decision
from shopassist.guard import PriceGuard, policy_amounts
from shopassist.llm import prompts
from shopassist.llm.client import LLMClient, build_llm
from shopassist.llm.schemas import RewriteHint, validated_rewrite
from shopassist.parser import ParsedQuery, QueryParser, Vocabulary
from shopassist.policy import parse_policy
from shopassist.response import Reply, ResponseBuilder

logger = logging.getLogger(__name__)
MAX_CONVERSATIONS = 1000
MAX_LLM_ATTEMPTS = 2
NAME_EVIDENCE_MIN = 80  # fuzzy evidence that a name in the LLM rewrite came from the shopper


class TurnResult(BaseModel):
    reply: Reply
    latency_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    llm_used: bool = False
    removed_by_guard: list[str] = Field(default_factory=list)
    debug: dict = Field(default_factory=dict)


class _TokenMeter:
    def __init__(self) -> None:
        self.tokens_in = self.tokens_out = 0

    def add(self, tokens_in: int, tokens_out: int) -> None:
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out


class ShoppingAssistant:
    def __init__(self, settings: Settings | None = None, llm: LLMClient | None = None):
        self.settings = settings or get_settings()
        self.catalogue = load_catalogue(self.settings.catalogue_path)
        policy_md = self.settings.policy_path.read_text(encoding="utf-8")
        self.policy = parse_policy(policy_md)
        self.parser = QueryParser(Vocabulary(self.catalogue, self.settings.matching))
        self.decider = Decider(self.catalogue, self.policy, self.settings.decision)
        self.builder = ResponseBuilder(self.policy)
        self.guard = PriceGuard(self.catalogue, policy_amounts(policy_md))
        self.llm = llm if llm is not None else build_llm(self.settings.llm)
        self._states: OrderedDict[str, ConversationState] = OrderedDict()

    # ----------------------------------------------------------------------------------- state
    def state_for(self, conversation_id: str) -> ConversationState:
        state = self._states.pop(conversation_id, None) or ConversationState()
        self._states[conversation_id] = state
        while len(self._states) > MAX_CONVERSATIONS:
            self._states.popitem(last=False)
        return state

    def reset(self, conversation_id: str) -> None:
        self._states.pop(conversation_id, None)

    # ----------------------------------------------------------------------------------- turn
    def ask(self, message: str, conversation_id: str = "default") -> TurnResult:
        start = time.perf_counter()
        meter = _TokenMeter()
        state = self.state_for(conversation_id)
        state.texts.append(message)

        q = self.parser.parse(message)
        decision = self.decider.decide(q, state)
        rewrite = None
        if self._rules_failed(q, decision, state):
            retry = self._llm_fallback(q, state, meter)
            if retry is not None:
                q, decision, rewrite = retry
        reply = self.builder.build(decision)
        reply, removed = self.guard.enforce(reply, state.texts)

        if (decision.candidates and decision.action != "refuse") or decision.kind == "unknown_fact":
            state.candidate_ids = [p.product_id for p in decision.candidates]
            state.filters = decision.filters
            state.intent = decision.intent
        elif decision.kind in ("policy", "policy_gap", "not_sold", "real_brand"):
            state.candidate_ids, state.filters, state.intent = [], None, None

        result = TurnResult(
            reply=reply,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            tokens_in=meter.tokens_in,
            tokens_out=meter.tokens_out,
            cost_usd=self._cost(meter),
            llm_used=bool(meter.tokens_in),
            removed_by_guard=removed,
            debug={
                "parsed": q.summary(),
                "decision": decision.kind,
                "matched": decision.total,
                "llm_rewrite": rewrite,
            },
        )
        self._log(message, result)
        return result

    # ----------------------------------------------------------------------------------- LLM fallback
    def _rules_failed(self, q: ParsedQuery, decision: Decision, state: ConversationState) -> bool:
        """The rules refused because they did not understand the message, not because they know the
        store lacks it (a real brand, an unsold item, a missing attribute or a policy gap)."""
        if decision.action != "refuse" or decision.kind not in ("not_sold", "no_match"):
            return False
        if q.real_brand or q.unsold_item:
            return False
        return not self.decider.is_followup(q, state)

    def _llm_fallback(
        self, q: ParsedQuery, state: ConversationState, meter: _TokenMeter
    ) -> tuple[ParsedQuery, Decision, str] | None:
        """Ask the LLM to restate the message in catalogue words, then let the rules decide again.
        The LLM's text is never shown and never supplies a fact; a refusal stays a refusal.
        LLM output varies between calls, so an unusable reply gets one more attempt."""
        if not self.llm.available:
            return None
        allowed = self.catalogue.sub_categories
        user = prompts.REWRITE_USER.format(
            sub_categories="\n".join(sorted(allowed)),
            brands=", ".join(sorted(p.title() for p in self.catalogue.brands)),
            message=q.raw,
        )
        for _ in range(MAX_LLM_ATTEMPTS):
            result = self.llm.complete(
                prompts.REWRITE_SYSTEM, user, self.settings.llm.max_tokens_rewrite, json_mode=True
            )
            if result is None:
                return None
            meter.add(result.tokens_in, result.tokens_out)
            hint = validated_rewrite(result.as_json(), allowed)
            retry = self._decide_rewrite(q, hint, state) if hint else None
            if retry is not None:
                return retry
        return None

    def _decide_rewrite(
        self, q: ParsedQuery, hint: RewriteHint, state: ConversationState
    ) -> tuple[ParsedQuery, Decision, str] | None:
        q2 = self.parser.parse(hint.rewritten_query or q.raw)
        if hint.sub_category and not q2.sub_categories and not q2.has_line:
            q2.sub_categories = (hint.sub_category,)
        if q2.real_brand or (q2.unsold_item and not q2.sub_categories):
            return None
        _keep_original_intent(q2, q)
        _drop_invented_names(q2, q)
        # a message the rules could not read is a new topic: decide it without earlier turns' filters
        decision = self.decider.decide(q2, ConversationState(texts=state.texts))
        if decision.action == "refuse":
            return None
        return q2, decision, hint.rewritten_query or hint.sub_category or ""

    def _cost(self, meter: _TokenMeter) -> float:
        s = self.settings.llm
        return round(
            (meter.tokens_in * s.cost_per_million_in + meter.tokens_out * s.cost_per_million_out) / 1_000_000,
            8,
        )

    # ----------------------------------------------------------------------------------- logging
    def _log(self, message: str, result: TurnResult) -> None:
        path = self.settings.query_log_path
        line = {
            "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "message": message[:300],
            "action": result.reply.action,
            "kind": result.reply.kind,
            "latency_ms": result.latency_ms,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_usd": result.cost_usd,
            "cited": result.reply.cited_product_ids,
            "sections": result.reply.cited_policy_sections,
            "removed_by_guard": result.removed_by_guard,
            "llm_rewrite": result.debug.get("llm_rewrite"),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("could not write query log: %s", exc)


def _keep_original_intent(rewritten: ParsedQuery, original: ParsedQuery) -> None:
    """The rewrite may drop what the shopper asked ("kitne ki" -> price) or their budget; keep them."""
    rewritten.asks_price = rewritten.asks_price or original.asks_price
    rewritten.asks_stock = rewritten.asks_stock or original.asks_stock
    rewritten.asks_discount = rewritten.asks_discount or original.asks_discount
    rewritten.superlative = rewritten.superlative or original.superlative
    rewritten.in_stock_only = rewritten.in_stock_only or original.in_stock_only
    if rewritten.budget_max is None:
        rewritten.budget_max = original.budget_max


def _drop_invented_names(rewritten: ParsedQuery, original: ParsedQuery) -> None:
    """The LLM may fix a misspelt name ("ghumo" -> Ghoomo) but must not add one the shopper never said."""
    said = original.text

    def mentioned(word: str | None) -> bool:
        return bool(word) and fuzz.partial_ratio(word, said.replace(" ", "")) >= NAME_EVIDENCE_MIN

    rewritten.names = [n for n in rewritten.names if mentioned(n.line) or mentioned(n.brand)]
