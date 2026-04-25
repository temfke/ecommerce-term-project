"""SQL Agent: turn a natural-language question into a SELECT statement.

In step 2 we only GENERATE the SQL — execution and sanitization come in steps 4-5.
The agent never sees raw role/user values from the request body that could let
the LLM be tricked into removing scope filters; the role-scoped WHERE clauses
are placeholders that the sanitizer (step 4) will rewrite server-side.
"""
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..schema import DB_SCHEMA_DOC, Role


SYSTEM_PROMPT = """You are a senior SQL developer specializing in MySQL 8.

You write a single SELECT statement that answers the user's question against
the schema below. Strict rules:

1. Output ONLY the SQL — no markdown fences, no commentary, no explanation.
2. SELECT statements only. Never UPDATE, INSERT, DELETE, DROP, TRUNCATE, ALTER, GRANT.
3. Single statement only. No semicolons except the final one. No comments.
4. Avoid SELECT * — list the columns you actually need.
5. Never query password_hash, refresh tokens, email_verification_*, or any auth columns.
6. Use placeholder ":scoped_user_id" or ":scoped_store_id" wherever you need to
   restrict results to the current user / their store. The execution layer
   will substitute the real values from the authenticated session.
7. LIMIT to at most 100 rows for list queries.

Schema:
"""


SCOPE_HINT = {
    "ADMIN": "The current user is an ADMIN — no ownership restriction needed.",
    "CORPORATE": (
        "The current user is a CORPORATE owner. Restrict every query to their "
        "store with `WHERE store_id = :scoped_store_id` (or join through stores "
        "and filter on stores.owner_id = :scoped_user_id)."
    ),
    "INDIVIDUAL": (
        "The current user is an INDIVIDUAL customer. Restrict every query to "
        "their data with `WHERE user_id = :scoped_user_id`."
    ),
}


def generate_sql_stub(question: str, role: Role) -> str:
    """Deterministic stub used when no LLM is configured."""
    lower = question.lower()
    scope_clause = ""
    if role == "CORPORATE":
        scope_clause = "AND o.store_id = :scoped_store_id\n"
    elif role == "INDIVIDUAL":
        scope_clause = "AND o.user_id = :scoped_user_id\n"

    if any(k in lower for k in ("trend", "revenue", "weekly", "monthly", "over time")):
        return (
            "SELECT DATE(o.created_at) AS day, SUM(oi.unit_price * oi.quantity) AS revenue\n"
            "FROM orders o JOIN order_items oi ON oi.order_id = o.id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 7 DAY\n"
            f"{scope_clause}"
            "GROUP BY day ORDER BY day;"
        )

    return (
        "SELECT p.name, SUM(oi.quantity) AS units\n"
        "FROM order_items oi JOIN products p ON p.id = oi.product_id\n"
        "JOIN orders o ON o.id = oi.order_id\n"
        "WHERE MONTH(o.created_at) = MONTH(NOW())\n"
        f"{scope_clause}"
        "GROUP BY p.id ORDER BY units DESC LIMIT 5;"
    )


def generate_sql_with_llm(llm: BaseChatModel, question: str, role: Role) -> str:
    full_prompt = SYSTEM_PROMPT + DB_SCHEMA_DOC + "\n\n" + SCOPE_HINT[role]
    response = llm.invoke([
        SystemMessage(content=full_prompt),
        HumanMessage(content=question),
    ])
    text = response.content if isinstance(response.content, str) else str(response.content)
    # Strip stray markdown fences if the model added any
    cleaned = text.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return cleaned


def generate_sql(llm: Optional[BaseChatModel], question: str, role: Role) -> str:
    if llm is None:
        return generate_sql_stub(question, role)
    try:
        return generate_sql_with_llm(llm, question, role)
    except Exception:
        return generate_sql_stub(question, role)
