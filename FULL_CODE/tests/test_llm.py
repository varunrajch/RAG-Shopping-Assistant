"""The optional LLM layer: mocked HTTP, validated output, safe fallback."""

import httpx

from shopassist.assistant import ShoppingAssistant
from shopassist.llm.client import GroqLLM, LLMResult
from shopassist.llm.schemas import validated_rewrite


def _groq(settings, handler):
    llm_settings = settings.llm.__class__(**{**vars(settings.llm), "api_key": "test-key", "max_retries": 1})
    return GroqLLM(llm_settings, http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_groq_success_counts_tokens(settings):
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"sub_category": "Yoga Mats"}'}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 9},
            },
        )

    result = _groq(settings, handler).complete("sys", "user", 50, json_mode=True)
    assert result.tokens_in == 120 and result.tokens_out == 9
    assert result.as_json() == {"sub_category": "Yoga Mats"}


def test_groq_failure_falls_back_to_none_and_backs_off(settings):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    llm = _groq(settings, handler)
    assert llm.complete("sys", "user", 50) is None
    assert len(calls) == 2  # one retry, then give up
    assert not llm.available  # backs off instead of slowing every turn


def test_llm_rewrite_is_validated():
    allowed = {"Toasters", "Footballs"}
    ok = validated_rewrite({"rewritten_query": "white toaster price", "sub_category": "Toasters"}, allowed)
    assert ok.rewritten_query == "white toaster price" and ok.sub_category == "Toasters"
    unknown_type = validated_rewrite({"rewritten_query": "phone", "sub_category": "Phones"}, allowed)
    assert unknown_type.sub_category is None
    assert validated_rewrite({"rewritten_query": "<script>x</script>", "sub_category": None}, allowed) is None
    assert validated_rewrite({"rewritten_query": "x" * 500}, allowed) is None
    assert validated_rewrite({"rewritten_query": None, "sub_category": None}, allowed) is None
    assert validated_rewrite(None, allowed) is None


class FakeLLM:
    """Pretends to be a working LLM; records how often it is called."""

    name = "fake"
    available = True

    def __init__(self, *replies: str):
        self.replies = replies
        self.calls = 0

    def complete(self, system, user, max_tokens, json_mode=False):
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return LLMResult(reply, 300, 20)


def test_llm_is_not_called_when_rules_understand_the_message(settings):
    llm = FakeLLM('{"rewritten_query": "anything", "sub_category": null}')
    result = ShoppingAssistant(settings, llm=llm).ask("Chargit QuillBolt red earphones kitne ke")
    assert llm.calls == 0 and result.tokens_in == 0 and not result.llm_used


def test_llm_fallback_rewrites_then_rules_answer_with_catalogue_facts(settings):
    llm = FakeLLM('{"rewritten_query": "pavana zephyrfusion toaster price", "sub_category": "Toasters"}')
    result = ShoppingAssistant(settings, llm=llm).ask("bread garam karne wali machine kitne ki")
    assert llm.calls == 1 and result.llm_used
    assert result.reply.action == "answer"
    assert result.reply.cited_product_ids == ["SKU-TEST0010"]
    assert "₹1,499" in result.reply.answer_text
    assert result.tokens_in == 300 and result.tokens_out == 20 and result.cost_usd > 0


def test_llm_cannot_turn_a_known_refusal_into_an_answer(settings):
    llm = FakeLLM('{"rewritten_query": "chargit quillbolt earphones", "sub_category": "Wired Earphones"}')
    bot = ShoppingAssistant(settings, llm=llm)
    assert bot.ask("redmi note 13 price").reply.action == "refuse"  # real brand: rules are sure
    assert bot.ask("silver payal dikhao", "c2").reply.action == "refuse"  # unsold item: rules are sure
    assert llm.calls == 0


def test_unhelpful_llm_keeps_the_refusal(settings):
    llm = FakeLLM('{"rewritten_query": null, "sub_category": null}')
    result = ShoppingAssistant(settings, llm=llm).ask("kuch accha sa dikhao yaar")
    assert llm.calls == 2 and result.reply.action == "refuse"  # one retry, then the refusal stands


def test_unusable_first_llm_reply_gets_one_more_attempt(settings):
    llm = FakeLLM(
        '{"rewritten_query": null, "sub_category": null}',
        '{"rewritten_query": "toaster price", "sub_category": "Toasters"}',
    )
    result = ShoppingAssistant(settings, llm=llm).ask("bread garam karne wali machine kitne ki")
    assert llm.calls == 2 and result.reply.action == "answer"
    assert result.tokens_in == 600


def test_llm_fallback_works_in_the_middle_of_a_conversation(settings):
    llm = FakeLLM('{"rewritten_query": "toaster price", "sub_category": "Toasters"}')
    bot = ShoppingAssistant(settings, llm=llm)
    bot.ask("6 mm yoga mat chahiye", "conv")
    bot.ask("TPE wali 600 ke andar", "conv")  # leaves a budget and material in memory
    result = bot.ask("bread garam karne wali machine kitne ki", "conv")
    assert result.reply.action == "answer"
    assert result.reply.cited_product_ids == ["SKU-TEST0010"]


def test_rate_limit_pauses_only_as_long_as_the_api_asks(settings):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "12"})

    llm = _groq(settings, handler)
    assert llm.complete("sys", "user", 50) is None
    assert len(calls) == 1  # no pointless retries inside the chat turn
    assert not llm.available


def test_llm_cannot_add_a_brand_the_shopper_never_named(settings):
    llm = FakeLLM('{"rewritten_query": "Kridaa footballs", "sub_category": "Footballs"}')
    result = ShoppingAssistant(settings, llm=llm).ask("pair se maarne wali gol cheez dikhao")
    assert result.reply.action == "answer"
    # without the invented brand the request still covers every football, not just one brand's
    assert {p for p in result.reply.cited_product_ids} == {"SKU-TEST0005", "SKU-TEST0006"}


def test_llm_may_fix_a_misspelt_brand(settings):
    llm = FakeLLM('{"rewritten_query": "Pavana ZephyrFusion toaster price", "sub_category": "Toasters"}')
    result = ShoppingAssistant(settings, llm=llm).ask("pavanaa zefirfuzn wala bread machine kitne ka")
    assert result.reply.cited_product_ids == ["SKU-TEST0010"]
