"""HTTP layer: validation, response shape, source lookups."""

import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_chat_returns_submission_shaped_reply(client):
    res = client.post(
        "/api/chat", json={"conversation_id": "api-1", "message": "krida ion flex football rate?"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["reply"]["action"] == "clarify"
    assert {"latency_ms", "tokens_in", "tokens_out", "cost_usd", "sources"} <= body.keys()
    # sources are sent with every reply: one catalogue row per cited product
    cited = body["reply"]["cited_product_ids"]
    assert [p["product_id"] for p in body["sources"]["products"]] == cited
    assert body["sources"]["products"][0]["price_inr"] in (519, 559)


def test_policy_reply_carries_policy_text(client):
    res = client.post("/api/chat", json={"conversation_id": "api-3", "message": "dubai me deliver karte ho?"})
    sources = res.json()["sources"]
    assert [s["section_id"] for s in sources["policies"]] == ["2.3"]
    assert "India" in sources["policies"][0]["text"]


@pytest.mark.parametrize(
    "payload",
    [
        {"conversation_id": "api-2", "message": ""},
        {"conversation_id": "api-2", "message": "   "},
        {"conversation_id": "api-2", "message": "x" * 301},
        {"conversation_id": "bad id!", "message": "hi"},
        {"message": "hi"},
    ],
)
def test_chat_rejects_invalid_input(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


def test_product_and_policy_sources(client):
    assert client.get("/api/product/SKU-TEST0011").json()["price_inr"] == 249
    assert client.get("/api/product/SKU-NOTFOUND").status_code == 404
    assert client.get("/api/product/not-an-id").status_code == 422
    assert client.get("/api/policy/6.2").json()["title"] == "In-ear audio products"


def test_metrics_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    m = client.get("/api/metrics").json()
    assert m["llm_provider"] == "none" and "session" in m
