"""Analyzer — turns a raw query result into a presentable answer card.

Computes a title, summary bullets, and a one-line insight from the executor's
output. Deterministic and free; the LLM-based Analysis Agent (step 6 final
form) can replace this later for richer narratives.
"""
from dataclasses import dataclass
from typing import Optional

from .executor import ExecutionResult


@dataclass
class Analysis:
    title: str
    bullets: list[str]
    insight: Optional[str]


_TITLE_KEYWORDS = [
    (("order status", "status breakdown", "fulfilment", "fulfillment"), "📦 Order Status Breakdown"),
    (("revenue", "trend", "monthly", "weekly", "over time"), "📈 Revenue Trend"),
    (("review", "rating", "star"), "⭐ Reviews"),
    (("shipment", "tracking", "delivery", "shipping"), "🚚 Shipments"),
    # Store-specific title must precede the generic "top/best" rule below,
    # otherwise "top seller store" gets the product-flavoured 🏆 Top Performers.
    (("seller store", "top store", "best store", "store ranking", "which store", "top seller", "leading store", "leading shop"), "🏪 Top Stores"),
    (("top", "best", "selling", "popular"), "🏆 Top Performers"),
    (("customer", "spending", "purchase"), "👥 Customer Insights"),
    (("inventory", "stock"), "📦 Inventory"),
    (("category", "categories"), "🗂️ Categories"),
    (("count",), "🔢 Totals"),
    (("product",), "🛍️ Products"),
    (("order",), "🧾 Orders"),
]

_LABEL_EMOJI = {
    "delivered": "✅",
    "shipped": "🚚",
    "pending": "⏳",
    "processing": "🔄",
    "confirmed": "✓",
    "cancelled": "❌",
    "returned": "↩️",
    "in_transit": "🚛",
    "open": "🟢",
    "closed": "🔒",
    "suspended": "⛔",
    "pending_approval": "⏳",
    "admin": "🛡️",
    "corporate": "🏢",
    "individual": "👤",
}


def analyze(question: str, exec_result: ExecutionResult, chart_type: str) -> Analysis:
    return Analysis(
        title=_detect_title(question),
        bullets=_compute_bullets(exec_result, chart_type),
        insight=_compute_insight(exec_result, chart_type),
    )


def _detect_title(question: str) -> str:
    q = (question or "").lower()
    for keywords, title in _TITLE_KEYWORDS:
        if any(k in q for k in keywords):
            return title
    return "📊 Analysis"


def _pairs(exec_result: ExecutionResult) -> list[tuple[str, float]]:
    cols = exec_result.columns
    rows = exec_result.rows
    if len(cols) < 2 or not rows:
        return []
    label_col, value_col = cols[0], cols[1]
    out: list[tuple[str, float]] = []
    for r in rows:
        try:
            out.append((str(r[label_col]), float(r[value_col])))
        except (TypeError, ValueError):
            continue
    return out


def _compute_bullets(exec_result: ExecutionResult, chart_type: str) -> list[str]:
    if exec_result.row_count <= 1:
        return []
    pairs = _pairs(exec_result)
    if not pairs:
        return []
    if chart_type == "LINE" and len(pairs) >= 2:
        return _time_series_bullets(pairs)
    return _categorical_bullets(pairs)


def _categorical_bullets(pairs: list[tuple[str, float]], max_bullets: int = 6) -> list[str]:
    total = sum(v for _, v in pairs)
    show_pct = total > 0 and len(pairs) > 1
    out: list[str] = []
    for label, value in pairs[:max_bullets]:
        emoji = _LABEL_EMOJI.get(label.lower(), "•")
        v_str = _fmt(value)
        if show_pct:
            pct = (value / total) * 100
            out.append(f"{emoji} {label}: {v_str} ({pct:.0f}%)")
        else:
            out.append(f"{emoji} {label}: {v_str}")
    return out


def _time_series_bullets(pairs: list[tuple[str, float]]) -> list[str]:
    values = [v for _, v in pairs]
    total = sum(values)
    peak = max(pairs, key=lambda p: p[1])
    low = min(pairs, key=lambda p: p[1])
    return [
        f"📈 Peak: {peak[0]} ({_fmt(peak[1])})",
        f"📉 Lowest: {low[0]} ({_fmt(low[1])})",
        f"Σ Total: {_fmt(total)}",
    ]


def _compute_insight(exec_result: ExecutionResult, chart_type: str) -> Optional[str]:
    pairs = _pairs(exec_result)
    if len(pairs) < 2:
        return None

    total = sum(v for _, v in pairs)
    if total == 0:
        return None

    top_label, top_value = max(pairs, key=lambda p: p[1])
    top_pct = (top_value / total) * 100

    if chart_type == "LINE":
        avg = total / len(pairs)
        if top_value > avg * 1.5:
            uplift = (top_value / avg - 1) * 100
            return f"💡 Peak on {top_label} was {uplift:.0f}% above average."
        return f"💡 {len(pairs)} data points — averaging {_fmt(avg)} per period."

    if top_pct >= 60:
        return f"💡 {top_label} dominates with {top_pct:.0f}% of the total."
    if top_pct >= 40:
        return f"💡 {top_label} leads at {top_pct:.0f}% — strong concentration on top."
    if len(pairs) >= 4 and top_pct < 30:
        return f"💡 Long tail across {len(pairs)} items — top entry is only {top_pct:.0f}%."
    return f"💡 Distributed across {len(pairs)} items — top is {top_label} ({top_pct:.0f}%)."


def _fmt(v: float) -> str:
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.2f}"
