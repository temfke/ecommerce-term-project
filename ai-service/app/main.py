"""FastAPI entrypoint. Spring Boot calls POST /chat/ask with the authenticated
user's role + scoped IDs derived from the JWT — never trust the request body
to set role/scope on its own.

Run locally:
    uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
"""
from fastapi import FastAPI, Header, HTTPException

from .config import settings
from .graph import run as run_graph
from .schema import ChatRequest, ChatResponse


app = FastAPI(title="DataPulse AI Service", version="0.2.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "internal_auth": bool(settings.INTERNAL_API_KEY),
    }


@app.post("/chat/ask", response_model=ChatResponse)
def chat_ask(
    request: ChatRequest,
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
) -> ChatResponse:
    if settings.INTERNAL_API_KEY:
        if not x_internal_key or x_internal_key != settings.INTERNAL_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid internal key")
    return run_graph(request)
