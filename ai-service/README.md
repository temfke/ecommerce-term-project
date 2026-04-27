# DataPulse AI Service

Python FastAPI + LangGraph multi-agent service that powers the DataPulse chatbot.

In step 2 the graph runs **Guardrails → SQL** and stops — it returns the generated
SQL preview to Spring Boot without executing it. Steps 4–6 will add a sanitizer,
read-only executor, analysis agent, and visualization agent.

## Setup

```bash
cd ai-service
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt
cp .env.example .env             # then edit .env
```

`LLM_PROVIDER=stub` works out of the box with no API key — the agents fall back
to deterministic rules so you can develop the wiring without burning tokens.
Switch to `gemini`, `anthropic`, or `openai` once you have a key:

| Provider    | Get a key at                              | Free tier |
|-------------|-------------------------------------------|-----------|
| `gemini`    | https://aistudio.google.com/app/apikey    | 1500 req/day, no card |
| `anthropic` | https://console.anthropic.com             | $5 credit |
| `openai`    | https://platform.openai.com/api-keys      | $5 credit |

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Health check: <http://127.0.0.1:8001/health>

## Endpoint

`POST /chat/ask` — called by Spring Boot, not directly by the browser.

Request:
```json
{
  "question": "Show me the top 5 products this month",
  "user_id": 42,
  "role": "CORPORATE",
  "store_owner_id": 42,
  "first_name": "Ahmet",
  "history": []
}
```

Response (one of four shapes):
```json
{ "status": "ANSWER",       "narrative": "...", "sql_preview": "SELECT ...", "rows": [...], "chart_type": "BAR" }
{ "status": "GREETING",     "narrative": "Hi Ahmet — ..." }
{ "status": "OUT_OF_SCOPE", "narrative": "...", "guardrail": { "type": "Out of scope", ... } }
{ "status": "BLOCKED",      "narrative": "...", "guardrail": { "type": "Prompt Injection", ... } }
```

If `INTERNAL_API_KEY` is set, the request must carry a matching `X-Internal-Key`
header. This prevents the browser (or anything else) from calling the AI service
directly, bypassing Spring Boot's JWT and role-scoping.
