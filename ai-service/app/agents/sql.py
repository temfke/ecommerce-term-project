"""SQL Agent: turn a natural-language question into a SELECT statement.

The agent generates SQL only; the sanitizer adds role-scoped WHERE clauses
server-side so the LLM never controls who-can-see-what.

When prior conversation turns are provided, they're passed as context so
follow-ups like "now show it as a pie chart" or "what about last week?"
resolve against the previous question's SQL.
"""
from typing import List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..schema import ChatTurn, DB_SCHEMA_DOC, Role


SYSTEM_PROMPT = """You are a senior SQL developer specializing in MySQL 8.

You write a single SELECT statement that answers the user's question against
the schema below. Strict rules:

1. Output ONLY the SQL — no markdown fences, no commentary, no explanation.
2. SELECT statements only. Never UPDATE, INSERT, DELETE, DROP, TRUNCATE, ALTER, GRANT.
3. Single statement only. No semicolons except the final one. No comments.
4. Avoid SELECT * — list the columns you actually need.
5. Never query password_hash, refresh tokens, email_verification_*, or any auth columns.
6. Do NOT add any ownership/scope filter (no `WHERE user_id = ...`, no
   `WHERE store_id = ...`). A downstream sanitizer adds the role-scoped
   WHERE clause from the authenticated session automatically. Just write
   the analytical SQL the question asks for.
7. LIMIT to at most 100 rows for list queries.
8. CHART-SHAPE HEURISTIC — pick the SELECT shape from the user's intent:
   - "pie chart", "donut", "breakdown", "split", "share", "by category",
     "by status", "by [some dimension]" → output (label_text, numeric_value)
     with GROUP BY on the categorical column. NEVER return a single
     aggregate row when a chart is asked for.
   - "trend", "over time", "by day/week/month" → first column is the date,
     second is the metric, GROUP BY date, ORDER BY date.
   - "top N", "best", "highest" → ORDER BY value DESC LIMIT N.
   - Plain count or total ("how many", "total") → fine to return a single
     aggregate row.

Schema:
"""


# The SQL agent does not see role context anymore — scope is the sanitizer's job.
SCOPE_HINT = {"ADMIN": "", "CORPORATE": "", "INDIVIDUAL": ""}


def generate_sql_stub(question: str, role: Role) -> str:
    """Deterministic stub used when no LLM is configured.

    Note: no scope clauses here on purpose — the sanitizer always re-injects
    them based on the authenticated session, so adding them here would just
    produce duplicate (but correct) WHERE conditions in the preview.
    """
    lower = question.lower()

    if any(k in lower for k in ("trend", "revenue", "weekly", "monthly", "over time")):
        return (
            "SELECT DATE(o.created_at) AS day, SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM orders o JOIN order_items oi ON oi.order_id = o.id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 30 DAY\n"
            "GROUP BY day ORDER BY day;"
        )

    if any(k in lower for k in ("recent order", "my order", "latest order", "last order", "order history")):
        return (
            "SELECT o.id, o.status, o.grand_total, o.created_at\n"
            "FROM orders o\n"
            "ORDER BY o.created_at DESC\n"
            "LIMIT 20;"
        )

    if any(k in lower for k in ("review", "rating", "star")):
        return (
            "SELECT p.name, r.star_rating, r.review_body, r.created_at\n"
            "FROM reviews r JOIN products p ON p.id = r.product_id\n"
            "ORDER BY r.created_at DESC LIMIT 20;"
        )

    if "shipment" in lower or "tracking" in lower or "delivery" in lower:
        return (
            "SELECT s.tracking_id, s.carrier, s.status, s.estimated_delivery\n"
            "FROM shipments s JOIN orders o ON o.id = s.order_id\n"
            "ORDER BY s.created_at DESC LIMIT 20;"
        )

    if "count" in lower:
        return "SELECT COUNT(*) AS total FROM orders;"

    return (
        "SELECT p.name, SUM(oi.quantity) AS units\n"
        "FROM order_items oi JOIN products p ON p.id = oi.product_id\n"
        "JOIN orders o ON o.id = oi.order_id\n"
        "WHERE MONTH(o.created_at) = MONTH(NOW())\n"
        "GROUP BY p.id ORDER BY units DESC LIMIT 5;"
    )


def _format_history(history: Optional[List[ChatTurn]]) -> str:
    if not history:
        return ""
    lines = []
    for t in history[-10:]:
        prefix = "User" if t.role == "user" else "Assistant"
        # Keep each line short so the prompt doesn't balloon
        snippet = (t.content or "").strip().replace("\n", " ")
        if len(snippet) > 240:
            snippet = snippet[:240] + "…"
        lines.append(f"{prefix}: {snippet}")
    return (
        "\n\nPrior conversation (most recent last) — use this only to resolve "
        "follow-up questions like \"show it as a chart\" or \"what about last month\":\n"
        + "\n".join(lines)
    )


def generate_sql_with_llm(
    llm: BaseChatModel,
    question: str,
    role: Role,
    history: Optional[List[ChatTurn]] = None,
) -> str:
    full_prompt = SYSTEM_PROMPT + DB_SCHEMA_DOC + "\n\n" + SCOPE_HINT[role] + _format_history(history)
    response = llm.invoke([
        SystemMessage(content=full_prompt),
        HumanMessage(content=question),
    ])
    text = response.content if isinstance(response.content, str) else str(response.content)
    cleaned = text.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return cleaned


def generate_sql(
    llm: Optional[BaseChatModel],
    question: str,
    role: Role,
    history: Optional[List[ChatTurn]] = None,
) -> str:
    if llm is None:
        return generate_sql_stub(question, role)
    try:
        return generate_sql_with_llm(llm, question, role, history)
    except Exception:
        return generate_sql_stub(question, role)
