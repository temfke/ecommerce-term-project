"""Analysis Agent: turn raw query results into a natural-language answer.

Uses an LLM if configured, otherwise falls back to the deterministic narrative
generator in graph.py. The agent never decides scope or runs SQL — by the time
it sees a result, the sanitizer + executor have already done their jobs.
"""
import json
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..executor import ExecutionResult


SYSTEM_PROMPT = """You are a friendly data analyst summarizing query results for an e-commerce dashboard user.

Given the user's question and the actual rows returned by the database, write a
SHORT natural-language answer (1 to 3 sentences). Rules:

- Answer the user's question directly. Use the real numbers from the result.
- Format money as "$1,234.56" and percentages as "42%". Use commas for thousands.
- If there are zero rows, say plainly that there is no matching data.
- Don't mention "SQL", "the query", "the database", or column names like "SUM(o.grand_total)" — phrase it as a person would.
- No bullet lists, no markdown headers. Just plain prose sentences.
- Don't apologize, don't repeat the question, don't add "Let me know if...".
- If the result spans multiple rows, mention the most interesting takeaway (top item, peak, total).
- Keep it under 60 words.
"""


def _format_rows_for_prompt(exec_result: ExecutionResult, max_rows: int = 20) -> str:
    """Compact JSON-ish list the model can read at a glance."""
    if not exec_result.rows:
        return "[] (no rows)"
    rows = exec_result.rows[:max_rows]
    suffix = f" (... {exec_result.row_count - max_rows} more)" if exec_result.row_count > max_rows else ""
    try:
        return json.dumps(rows, default=str) + suffix
    except (TypeError, ValueError):
        return str(rows) + suffix


def summarize_with_llm(
    llm: BaseChatModel,
    question: str,
    exec_result: ExecutionResult,
) -> Optional[str]:
    user_msg = (
        f"User asked: {question}\n\n"
        f"Columns: {exec_result.columns}\n"
        f"Rows: {_format_rows_for_prompt(exec_result)}\n"
        f"Total rows: {exec_result.row_count}"
        + (" (truncated)" if exec_result.truncated else "")
    )
    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        text = response.content if isinstance(response.content, str) else str(response.content)
        cleaned = text.strip()
        return cleaned or None
    except Exception:
        return None


def summarize(
    llm: Optional[BaseChatModel],
    question: str,
    exec_result: ExecutionResult,
) -> Optional[str]:
    """Returns a natural-language narrative, or None to use the deterministic fallback."""
    if llm is None:
        return None
    return summarize_with_llm(llm, question, exec_result)
