"""SQL Agent: turn a natural-language question into a SELECT statement.

The agent generates SQL only; the sanitizer adds role-scoped WHERE clauses
server-side so the LLM never controls who-can-see-what.

When prior conversation turns are provided, they're passed as context so
follow-ups like "now show it as a pie chart" or "what about last week?"
resolve against the previous question's SQL.
"""
import re
from typing import List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..schema import ChatTurn, DB_SCHEMA_DOC, Role


# Two or three capitalized "word" tokens in a row, where a "word" is a run of
# letter-class characters (Unicode `\w` matches Turkish Ö/ç/ı/ğ etc.). Used by
# the stub to detect proper names like "Mert Özelsancak" or "Jane Q Public".
_PERSON_NAME_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü']{1,30}(?:\s+[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü']{1,30}){1,2})\b")
_STORE_SALES_RE = re.compile(
    r"\bhow\s+many\s+(?:sales|orders)\s+(?:did|does|has|have)\s+"
    r"(?P<store>.+?)\s+(?:make|made|had\s+made|have|has|had)\??$",
    re.IGNORECASE,
)
_STORE_SALES_ALT_RE = re.compile(
    r"\b(?P<store>[a-z0-9][\w '&.-]{1,80}?)\s+(?:sales|orders)\s+(?:count|total|number)\??$",
    re.IGNORECASE,
)
_TOP_N_RE = re.compile(r"\btop\s+(\d{1,2})\b", re.IGNORECASE)


def _esc(s: str) -> str:
    """Escape a string for safe single-quoted SQL literal interpolation in the
    stub. Strips anything that isn't a letter, digit, space, hyphen, or
    apostrophe — defense-in-depth on top of the sanitizer that runs after."""
    return re.sub(r"[^\w \-']", "", s, flags=re.UNICODE).replace("'", "''")


def _top_limit(question: str, default: int = 5) -> int:
    match = _TOP_N_RE.search(question)
    if not match:
        return default
    return max(1, min(int(match.group(1)), 100))


def _store_name_from_sales_question(question: str) -> Optional[str]:
    for pattern in (_STORE_SALES_RE, _STORE_SALES_ALT_RE):
        match = pattern.search(question.strip())
        if match:
            store = match.group("store")
            store = re.sub(r"\b(the|store|shop)\b", " ", store, flags=re.IGNORECASE)
            store = re.sub(r"\s+", " ", store).strip(" ?.,'\"")
            if store and store.lower() not in {"my", "my store", "own store"}:
                return store
    return None


def _is_high_confidence_stub_intent(question: str) -> bool:
    lower = question.lower()
    if _store_name_from_sales_question(question):
        return True
    if (
        any(k in lower for k in ("top", "most sold", "best selling", "best-selling"))
        and any(k in lower for k in ("product", "products", "item", "items"))
        and "store" not in lower
    ):
        return True
    if any(
        k in lower
        for k in (
            "seller store", "top seller", "top sellers",
            "top selling store", "top-selling store",
            "best store", "best seller store", "best-selling store",
            "which store", "store ranking", "leading store",
            "leading shop", "top shop", "best shop",
        )
    ):
        return True
    return False


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
     "by status", "by [some dimension]", "categoric visualization",
     "categorical visualization" → output (label_text, numeric_value)
     with GROUP BY on the categorical column. NEVER return a single
     aggregate row when a chart is asked for.
   - "trend", "over time", "by day/week/month" → first column is the date,
     second is the metric, GROUP BY date, ORDER BY date.
   - "top N", "best", "highest" → ORDER BY value DESC LIMIT N.
   - Plain count or total ("how many", "total") → fine to return a single
     aggregate row.
   - "percentage", "what % of", "share of" → return BOTH the part and the
     whole so the analyst can show the ratio, e.g.
     SELECT
       (SELECT grand_total FROM orders ORDER BY created_at DESC LIMIT 1) AS last_purchase,
       (SELECT SUM(grand_total) FROM (SELECT grand_total FROM orders ORDER BY created_at DESC LIMIT 10) t) AS last_10_total;
9. RIVAL / COMPETITOR QUESTIONS (corporate user only) — when the user asks
   about rivals, competitors, or "other stores" selling similar items:
   - Identify the user's top categories first (their best-selling products'
     category_id from order_items + orders + products).
   - Then SELECT across the full `products` and `stores` catalog (do NOT
     filter by store_id) joined on those category_id values.
   - Group by store name; sort by product count or aggregate listing price.
   - The sanitizer keeps your own `orders` scoped to your stores, but lets
     `products` and `stores` span the whole platform for these questions.
10. BESTSELLER STORE IN A CATEGORY (individual user) — order data is private
    per-user, so do NOT try to rank stores by other people's orders. Use the
    public catalog instead: rank stores by COUNT(p.id) (or AVG review rating
    for the category) within the requested category.
10b. PUBLIC INFORMATION FOR NON-ADMIN USERS - INDIVIDUAL and CORPORATE users
    may ask about public marketplace facts: products, items, stores, categories,
    prices, stock, availability, and public product ratings/review summaries.
    Do not use other stores' `orders`, `order_items`, customers, shipments,
    addresses, payments, or revenue/profit for public comparisons. For public
    store/category questions, prefer `products`, `stores`, `categories`, and
    aggregated `reviews`.
10c. ADMIN USERS - admins may ask platform-wide questions about stores,
    products, orders, customers, shipments, reviews, and previous answers. The
    sanitizer still blocks unsafe SQL and sensitive auth columns.
11. PERSON-BY-NAME LOOKUPS — when the user names a person ("show Mert
    Özelsancak's order history", "what did Jane Doe buy", "orders for
    user Ali Yılmaz"), resolve the user_id by joining the `users` table
    on first_name + last_name and then look up their orders. Use
    case-insensitive matching with LIKE because diacritics and casing
    vary. Example shape (admin role):
       SELECT o.id, o.status, o.grand_total, o.created_at
       FROM orders o
       JOIN users u ON u.id = o.user_id
       WHERE LOWER(CONCAT(u.first_name, ' ', u.last_name)) LIKE LOWER('%<full name>%')
          OR (LOWER(u.first_name) LIKE LOWER('%<first>%')
              AND LOWER(u.last_name)  LIKE LOWER('%<last>%'))
       ORDER BY o.created_at DESC LIMIT 50;
    Never SELECT password_hash or any auth column from `users` — only
    join on it for filtering.
12. STORE vs PRODUCT — read the noun carefully. Phrases like "top seller
    store", "best store", "which store sells the most", "top selling store",
    "leading shop" describe STORES, not products. The first projected column
    MUST be `s.name` from the `stores` table and the GROUP BY MUST be on
    `s.id`. Do NOT return `products.name` for store-level questions, even if
    the user's wording overlaps ("top selling" can apply to either — when in
    doubt, the noun after "top selling" decides). Example shape:
       SELECT s.name, SUM(oi.price * oi.quantity) AS revenue
       FROM order_items oi
       JOIN orders o  ON o.id = oi.order_id
       JOIN stores s  ON s.id = o.store_id
       GROUP BY s.id ORDER BY revenue DESC LIMIT 5;

13. SIMPLE STORE SALES COUNTS - questions like "how many sales did Aegean
    Outfitters make" ask for a STORE, not products. Return the matching store
    name, COUNT(orders.id) as sales_count, and optionally SUM(orders.grand_total)
    as revenue. Non-admin role scoping is enforced after generation.
14. SIMPLE MOST-SOLD ITEM - questions like "what is the most sold item" ask for
    exactly one item unless the user says "top N". Return product/item name and
    SUM(order_items.quantity) as units, ordered descending.

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
    limit = _top_limit(question)

    store_name = _store_name_from_sales_question(question)
    if store_name:
        return (
            "SELECT s.name AS store, COUNT(o.id) AS sales_count, "
            "COALESCE(SUM(o.grand_total), 0) AS revenue\n"
            "FROM stores s\n"
            "LEFT JOIN orders o ON o.store_id = s.id\n"
            f"WHERE LOWER(s.name) LIKE LOWER('%{_esc(store_name)}%')\n"
            "GROUP BY s.id, s.name\n"
            "ORDER BY sales_count DESC LIMIT 5;"
        )

    if (
        any(k in lower for k in ("most sold item", "most-sold item", "most sold product", "best selling product", "best-selling product"))
        and "top" not in lower
        and "store" not in lower
    ):
        if role != "INDIVIDUAL":
            return (
                "SELECT p.name AS product, SUM(oi.quantity) AS units\n"
                "FROM order_items oi\n"
                "JOIN products p ON p.id = oi.product_id\n"
                "GROUP BY p.id, p.name ORDER BY units DESC LIMIT 1;"
            )
        return (
            "SELECT p.name AS product, SUM(oi.quantity) AS units\n"
            "FROM order_items oi\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "JOIN orders o ON o.id = oi.order_id\n"
            "GROUP BY p.id, p.name ORDER BY units DESC LIMIT 1;"
        )

    if (
        any(k in lower for k in ("top", "most sold", "best selling", "best-selling"))
        and any(k in lower for k in ("product", "products", "item", "items"))
        and "store" not in lower
    ):
        where = ""
        if "this month" in lower or "current month" in lower:
            where = "WHERE YEAR(o.created_at) = YEAR(NOW()) AND MONTH(o.created_at) = MONTH(NOW())\n"
        elif "this year" in lower or "current year" in lower:
            where = "WHERE YEAR(o.created_at) = YEAR(NOW())\n"
        if not where and role != "INDIVIDUAL":
            return (
                "SELECT p.name AS product, SUM(oi.quantity) AS units\n"
                "FROM order_items oi\n"
                "JOIN products p ON p.id = oi.product_id\n"
                f"GROUP BY p.id, p.name ORDER BY units DESC LIMIT {limit};"
            )
        return (
            "SELECT p.name AS product, SUM(oi.quantity) AS units\n"
            "FROM order_items oi\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "JOIN orders o ON o.id = oi.order_id\n"
            f"{where}"
            f"GROUP BY p.id, p.name ORDER BY units DESC LIMIT {limit};"
        )

    # Store-level "top seller" must come BEFORE the trend/product branches
    # because "top selling" overlaps with several keyword sets — and before
    # the default product fallback, which would otherwise return product names.
    if any(
        k in lower
        for k in (
            "seller store", "top seller", "top sellers",
            "top selling store", "top-selling store",
            "best store", "best seller store", "best-selling store",
            "which store", "store ranking", "leading store",
            "leading shop", "top shop", "best shop",
        )
    ):
        return (
            "SELECT s.name AS store, SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM order_items oi\n"
            "JOIN orders o ON o.id = oi.order_id\n"
            "JOIN stores s ON s.id = o.store_id\n"
            "GROUP BY s.id ORDER BY revenue DESC LIMIT 5;"
        )

    if any(k in lower for k in ("trend", "revenue", "weekly", "monthly", "over time")):
        return (
            "SELECT DATE(o.created_at) AS day, SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM orders o JOIN order_items oi ON oi.order_id = o.id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 30 DAY\n"
            "GROUP BY day ORDER BY day;"
        )

    # "show Mert Özelsancak's order history" / "orders for user Jane Doe" etc.
    # Resolve a user by their proper name (capitalized, possibly with non-ASCII
    # characters) and pull that user's orders. Only fires when there's a
    # plausible name AND an order/history/purchase signal — otherwise it would
    # eat ordinary "last order" questions.
    name_match = _PERSON_NAME_RE.search(question)
    history_signal = any(k in lower for k in ("order history", "orders for", "purchases of", "purchases by", "what did", "buy history", "purchase history"))
    if name_match and (history_signal or "order" in lower or "purchase" in lower):
        full_name = name_match.group(0).strip()
        # Strip a trailing English possessive ("Mert Özelsancak's" → "Mert Özelsancak")
        # so the LIKE actually matches the stored last name.
        full_name = re.sub(r"['’]s\b", "", full_name).strip()
        parts = full_name.split()
        first, last = parts[0], parts[-1]
        # Single-quoted literals; no user input is interpolated besides the
        # captured name fragments, which are letters-only by regex construction.
        return (
            "SELECT o.id, o.status, o.grand_total, o.created_at, "
            "u.first_name, u.last_name\n"
            "FROM orders o\n"
            "JOIN users u ON u.id = o.user_id\n"
            f"WHERE LOWER(CONCAT(u.first_name, ' ', u.last_name)) LIKE LOWER('%{_esc(full_name)}%')\n"
            f"   OR (LOWER(u.first_name) LIKE LOWER('%{_esc(first)}%') "
            f"AND LOWER(u.last_name) LIKE LOWER('%{_esc(last)}%'))\n"
            "ORDER BY o.created_at DESC LIMIT 50;"
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
        f"GROUP BY p.id ORDER BY units DESC LIMIT {limit};"
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
    if _is_high_confidence_stub_intent(question):
        return generate_sql_stub(question, role)
    if llm is None:
        return generate_sql_stub(question, role)
    try:
        return generate_sql_with_llm(llm, question, role, history)
    except Exception:
        return generate_sql_stub(question, role)
