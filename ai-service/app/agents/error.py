"""Error Agent: when MySQL rejects the LLM-generated SQL, feed the failure
back to the LLM and ask it to produce a corrected SELECT.

The graph drives the retry loop (capped at settings.MAX_RETRIES) and routes
the corrected SQL back through the sanitizer, so a "fix" that smuggles in a
DROP or sensitive column is still rejected before it reaches the database.
"""
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..schema import DB_SCHEMA_DOC, Role


SYSTEM_PROMPT = """You are a senior MySQL developer fixing a SELECT that the
database refused to run.

You will be given:
  - the user's original natural-language question,
  - the SQL that just failed,
  - the exact MySQL error message.

Produce a corrected single SELECT statement. Strict rules:

1. Output ONLY the SQL — no markdown fences, no commentary.
2. SELECT statements only. Never UPDATE, INSERT, DELETE, DROP, TRUNCATE, ALTER.
3. Single statement. No semicolons except the final one. No comments.
4. Avoid SELECT * — list the columns you actually need.
5. Never query password_hash, refresh tokens, email_verification_*, or any
   auth/Stripe columns.
6. Do NOT add ownership/scope filters (no `WHERE user_id = ...`, no
   `WHERE store_id = ...`). A downstream sanitizer re-injects scope from the
   authenticated session.
7. Use the schema below as the source of truth. If the error says a column
   or table doesn't exist, pick the correct one from this schema.
8. LIMIT to at most 100 rows for list queries.

Schema:
"""


def fix_sql(
    llm: Optional[BaseChatModel],
    question: str,
    failed_sql: str,
    error_message: str,
    role: Role,
) -> Optional[str]:
    """Return a corrected SQL string, or None if no LLM is available or the
    LLM call itself blew up. The graph treats `None` as 'give up retrying'."""
    if llm is None:
        return None
    user_msg = (
        f"Original question: {question}\n\n"
        f"User role (for context only — do NOT add scope filters): {role}\n\n"
        f"SQL that failed:\n{failed_sql}\n\n"
        f"MySQL error:\n{error_message}\n\n"
        "Produce the corrected SELECT now."
    )
    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT + DB_SCHEMA_DOC),
            HumanMessage(content=user_msg),
        ])
        text = response.content if isinstance(response.content, str) else str(response.content)
        cleaned = text.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
        return cleaned or None
    except Exception:
        return None
