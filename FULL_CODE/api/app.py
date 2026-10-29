"""HTTP API and static web demo. Business logic lives in shopassist; this module only does
validation, rate limiting, serialisation and error handling."""

from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from shopassist.assistant import ShoppingAssistant, TurnResult
from shopassist.catalogue import Product
from shopassist.config import FULL_CODE_DIR, get_settings
from shopassist.policy import PolicySection

logger = logging.getLogger(__name__)
settings = get_settings()
WEB_DIR = FULL_CODE_DIR / "web"
DEV_SCORE_PATH = FULL_CODE_DIR / "reports" / "dev_score.json"
CONVERSATION_ID = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    conversation_id: str = Field(pattern=CONVERSATION_ID)
    message: str = Field(min_length=1, max_length=settings.api.max_message_chars)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v


class ResetRequest(BaseModel):
    conversation_id: str = Field(pattern=CONVERSATION_ID)


class RateLimiter:
    """Sliding one-minute window per client IP, in memory (enough for a single-process demo)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True


class _Runtime:
    def __init__(self) -> None:
        self.assistant: ShoppingAssistant | None = None
        self.lock = threading.Lock()  # conversation state is not thread-safe
        self.limiter = RateLimiter(settings.api.rate_limit_per_minute)
        self.turns: deque[TurnResult] = deque(maxlen=500)  # recent turns for the live metrics panel

    @property
    def bot(self) -> ShoppingAssistant:
        if self.assistant is None:
            raise HTTPException(status_code=503, detail="The assistant is starting up. Please retry.")
        return self.assistant


runtime = _Runtime()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    runtime.assistant = ShoppingAssistant()
    logger.info("assistant ready: %d products, LLM=%s", len(runtime.bot.catalogue), runtime.bot.llm.name)
    yield


app = FastAPI(
    title="Shopping Assistant",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.api.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def no_stale_ui(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Browsers must re-check the page and its static files, so UI updates show without a hard refresh."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# --------------------------------------------------------------------------------------------- chat
@app.post("/api/chat")
def chat(body: ChatRequest, request: Request) -> dict:
    client = request.client.host if request.client else "unknown"
    if not runtime.limiter.allow(client):
        raise HTTPException(status_code=429, detail="Too many messages. Please wait a minute.")
    try:
        with runtime.lock:
            result = runtime.bot.ask(body.message, conversation_id=body.conversation_id)
    except Exception:  # last-resort guard: log details for developers, show a helpful message to shoppers
        logger.exception("chat turn failed")
        raise HTTPException(
            status_code=500, detail="Sorry, something went wrong. Please try again."
        ) from None
    runtime.turns.append(result)
    return {**result.model_dump(), "sources": _sources(result)}


def _sources(result: TurnResult) -> dict:
    """The catalogue rows and policy text behind a reply, so the UI can show them next to the answer."""
    bot = runtime.bot
    products = [bot.catalogue.get(pid) for pid in result.reply.cited_product_ids]
    sections = [bot.policy.get(sid) for sid in result.reply.cited_policy_sections]
    return {
        "products": [_product_view(p) for p in products if p],
        "policies": [_section_view(s) for s in sections if s],
    }


def _product_view(p: Product) -> dict:
    return {
        "product_id": p.product_id,
        "title": p.title,
        "brand": p.brand,
        "category": p.category,
        "sub_category": p.sub_category,
        "description": p.description,
        "attributes": p.attributes,
        "price_inr": p.price_inr,
        "mrp_inr": p.mrp_inr,
        "stock_status": p.stock_status,
        "rating": p.rating,
        "review_count": p.review_count,
    }


def _section_view(s: PolicySection) -> dict:
    return {"section_id": s.section_id, "title": s.title, "text": s.text}


@app.post("/api/reset")
def reset(body: ResetRequest) -> dict:
    with runtime.lock:
        runtime.bot.reset(body.conversation_id)
    return {"ok": True}


# --------------------------------------------------------------------------------------------- sources
@app.get("/api/product/{product_id}")
def product(product_id: str = PathParam(pattern=r"^SKU-[A-Z0-9]{8}$")) -> dict:
    p = runtime.bot.catalogue.get(product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_view(p)


@app.get("/api/policy/{section_id}")
def policy_section(section_id: str = PathParam(pattern=r"^\d{1,2}\.\d{1,2}$")) -> dict:
    s = runtime.bot.policy.get(section_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Policy section not found")
    return _section_view(s)


# --------------------------------------------------------------------------------------------- metrics
def _dev_score() -> dict | None:
    if not DEV_SCORE_PATH.is_file():
        return None
    try:
        data = json.loads(DEV_SCORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("could not read %s", DEV_SCORE_PATH)
        return None
    keep = (
        "primary_score",
        "n_truth_questions",
        "components",
        "score_by_question_type",
        "latency_ms",
        "tokens",
    )
    return {k: data.get(k) for k in keep}


@app.get("/api/metrics")
def metrics() -> dict:
    turns = list(runtime.turns)
    lat = sorted(t.latency_ms for t in turns)
    session = {
        "turns": len(turns),
        "latency_ms_mean": round(statistics.fmean(lat), 2) if lat else 0.0,
        "latency_ms_p95": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 2) if lat else 0.0,
        "tokens_in_total": sum(t.tokens_in for t in turns),
        "tokens_out_total": sum(t.tokens_out for t in turns),
        "cost_usd_total": round(sum(t.cost_usd for t in turns), 6),
        "actions": {a: sum(1 for t in turns if t.reply.action == a) for a in ("answer", "clarify", "refuse")},
    }
    return {
        "session": session,
        "dev_score": _dev_score(),
        "llm_provider": runtime.bot.llm.name,
        "llm_model": settings.llm.model if runtime.bot.llm.available else None,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------------------------- web
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(Path(WEB_DIR) / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
