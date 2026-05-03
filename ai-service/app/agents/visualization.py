"""Visualization Agent: pick the chart type that best fits the result and
project the rows into (label, value) pairs the frontend can render.

The graph splits this into two conceptual steps:
  - decide_chart_type: BAR | LINE | PIE | NONE
  - to_data_rows:      shape the rows for the chosen chart

LLM-backed decision when an LLM is configured, deterministic fallback otherwise
so the pipeline still works on the stub provider.
"""
import json
import re
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..executor import ExecutionResult
from ..schema import DataRow


_DATE_LIKE_NAMES = {
    "day", "date", "month", "week", "year",
    "created_at", "ordered_at", "updated_at", "shipped_at",
}
_PIE_KEYWORDS = (
    "pie", "donut", "doughnut", "share", "split", "breakdown",
    "categoric", "categorical",
)
# Above this row count a donut becomes a ring of unreadable thin slivers;
# bar is clearer. Below this it almost always reads better as a part-of-whole.
_PIE_MAX_ROWS_DEFAULT = 6
# When the user explicitly invoked a pie keyword we tolerate a few more
# slices before falling back to BAR.
_PIE_MAX_ROWS_KEYWORD = 10
_VALID_CHART_TYPES = {"BAR", "LINE", "PIE", "NONE"}


SYSTEM_PROMPT = """You are choosing the chart type for a query result.

Pick exactly one of: BAR, LINE, PIE, NONE.

Rules:
  - NONE: a single-row scalar result, or fewer than two columns — nothing to chart.
  - LINE: the first column is a date or time bucket (day/week/month/year).
  - PIE: a small categorical result (2 to 6 rows) that reads as parts of a
    whole — category breakdowns, store/status share, top-N rankings where
    proportions matter. Tolerate up to 8 rows when the user explicitly says
    pie / donut / share / split / breakdown.
  - BAR: more than 8 rows, or any result where exact magnitudes matter more
    than proportions and the donut would be unreadable.

Respond with ONLY a JSON object: {"chart_type": "BAR"} (or LINE / PIE / NONE).
"""


def _deterministic_chart_type(columns: list[str], rows: list[dict], question: str) -> str:
    if len(rows) <= 1 or len(columns) < 2:
        return "NONE"
    first_col = columns[0].lower()
    if first_col in _DATE_LIKE_NAMES or "date" in first_col or first_col.endswith("_at"):
        return "LINE"
    q = (question or "").lower()
    n = len(rows)
    # Explicit keyword bias: still PIE for up to 10 slices.
    if any(k in q for k in _PIE_KEYWORDS) and n <= _PIE_MAX_ROWS_KEYWORD:
        return "PIE"
    # Default: small categorical results read better as a donut. The user
    # asked us to prefer donut wherever it makes visual sense, not just
    # when they spelled "pie" or "breakdown" in the question.
    if 2 <= n <= _PIE_MAX_ROWS_DEFAULT:
        return "PIE"
    return "BAR"


def decide_chart_type(
    llm: Optional[BaseChatModel],
    question: str,
    exec_result: ExecutionResult,
) -> str:
    deterministic = _deterministic_chart_type(exec_result.columns, exec_result.rows, question)
    # Cheap signals never need an LLM: nothing to chart, or it's a clear time series.
    if deterministic in ("NONE", "LINE") or llm is None:
        return deterministic

    sample = exec_result.rows[: min(8, len(exec_result.rows))]
    user_msg = (
        f"User question: {question}\n"
        f"Columns: {exec_result.columns}\n"
        f"Row count: {exec_result.row_count}\n"
        f"Sample rows: {json.dumps(sample, default=str)}\n"
        f"Deterministic guess: {deterministic}"
    )
    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        text = response.content if isinstance(response.content, str) else str(response.content)
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(cleaned)
            choice = str(data.get("chart_type", "")).upper()
        except json.JSONDecodeError:
            match = re.search(r"\b(BAR|LINE|PIE|NONE)\b", cleaned, re.IGNORECASE)
            choice = match.group(1).upper() if match else ""
        if choice in _VALID_CHART_TYPES:
            return choice
    except Exception:
        pass
    return deterministic


def to_data_rows(columns: list[str], rows: list[dict]) -> list[DataRow]:
    """Project the first two columns into label/value pairs, dropping rows
    whose value column isn't numeric. The frontend chart component expects
    this shape regardless of the source SQL.
    """
    if len(columns) < 2 or not rows:
        return []
    label_col, value_col = columns[0], columns[1]
    out: list[DataRow] = []
    for r in rows:
        try:
            out.append(DataRow(label=str(r[label_col]), value=float(r[value_col])))
        except (TypeError, ValueError):
            continue
    return out
