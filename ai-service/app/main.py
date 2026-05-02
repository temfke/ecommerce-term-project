"""FastAPI entrypoint. Spring Boot calls POST /chat/ask with the authenticated
user's role + scoped IDs derived from the JWT — never trust the request body
to set role/scope on its own.

Run locally:
    uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
"""
import time
from collections import deque
from threading import Lock

from fastapi import FastAPI, Header, HTTPException

from .config import settings
from .graph import run as run_graph
from .schema import ChatRequest, ChatResponse


app = FastAPI(title="TEMF AI Service", version="0.3.0")


# Per-user sliding-window rate limiter. Cheap, in-memory, single-process —
# matches the architecture: a single uvicorn worker behind the Spring Boot
# proxy. Swap for Redis if we ever scale to multiple workers.
_rate_state: dict[int, deque[float]] = {}
_rate_lock = Lock()


def _check_rate_limit(user_id: int) -> None:
    if settings.RATE_LIMIT_REQUESTS <= 0:
        return
    now = time.monotonic()
    cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        bucket = _rate_state.setdefault(user_id, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= settings.RATE_LIMIT_REQUESTS:
            retry_after = max(1, int(bucket[0] + settings.RATE_LIMIT_WINDOW_SECONDS - now))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many requests. Limit is {settings.RATE_LIMIT_REQUESTS} "
                    f"per {settings.RATE_LIMIT_WINDOW_SECONDS}s; retry in {retry_after}s."
                ),
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


# Substring match against whatever LangChain surfaces — Gemini, Anthropic, and
# OpenAI all phrase quota errors differently, but the substrings below cover
# the actual messages we've seen on the free tiers.
_QUOTA_HINTS = (
    "429",
    "quota",
    "rate limit",
    "ratelimit",
    "resource_exhausted",
    "resourceexhausted",
    "exceeded your current quota",
    "insufficient_quota",
    "too many requests",
)


def _looks_like_quota_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _QUOTA_HINTS)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "internal_auth": bool(settings.INTERNAL_API_KEY),
        "max_retries": settings.MAX_RETRIES,
        "rate_limit": f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_WINDOW_SECONDS}s",
    }


@app.post("/chat/ask", response_model=ChatResponse)
def chat_ask(
    request: ChatRequest,
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
) -> ChatResponse:
    if settings.INTERNAL_API_KEY:
        if not x_internal_key or x_internal_key != settings.INTERNAL_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid internal key")
    _check_rate_limit(request.user_id)
    try:
        return run_graph(request)
    except HTTPException:
        raise
    except Exception as exc:
        # Convert LLM-provider quota / 429 errors into a 503 so Spring Boot
        # surfaces a friendly "service unavailable" message instead of leaking
        # the raw provider error to the chat UI.
        if _looks_like_quota_error(exc):
            raise HTTPException(
                status_code=503,
                detail="AI provider quota exhausted — please retry shortly.",
            ) from exc
        raise
