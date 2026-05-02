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
_STORE_UNITS_RE = re.compile(
    r"\b("
    r"who\s+sold\s+(?:the\s+)?most\s+(?:items|products|units)?"
    r"|which\s+(?:store|seller|shop)\s+sold\s+(?:the\s+)?most\s+(?:items|products|units)?"
    r"|top\s+\d{1,2}\s+(?:stores|sellers|shops)\s+by\s+(?:items|products|units)\s+sold"
    r"|(?:top|best)\s+(?:store|seller|shop)\s+by\s+(?:items|products|units)\s+sold"
    r"|(?:top|best)\s+(?:item-selling|product-selling)\s+(?:store|seller|shop)"
    r")\b",
    re.IGNORECASE,
)
_TOP_N_RE = re.compile(r"\btop\s+(\d{1,2})\b", re.IGNORECASE)
_ORDER_ID_RE = re.compile(r"\b(?:order(?:\s+id)?|id)\s*(?:#|with\s+id\s+|id\s*)?(\d{2,})\b", re.IGNORECASE)
_LAST_PURCHASE_PERCENT_RE = re.compile(
    # share/percentage of "this/my/last/etc. purchase" against a denominator
    # phrase ("all purchases", "last 10 purchases", "past 20 orders", ...).
    # Both halves are required so we don't match bare "what's the percentage"
    # or "how many last 10 purchases" — must have both numerator and denominator.
    # The percent keyword is split out: `\b...\b` works around word chars
    # (percentage/percent/share) but not around the literal `%`, so `what %`
    # is matched without a trailing word boundary.
    r"(?:\b(?:percentage|percent|share)\b|what\s*%|%\s*of)"
    r".*\b(?:this|my|the|last|latest|most\s+recent)\s+(?:purchase|order)\b"
    r".*\b(?:all|every|total|(?:last|recent|past)\s+\d{1,3})\s+(?:purchases?|orders?)\b",
    re.IGNORECASE,
)

# Extract "last N" / "recent N" / "past N" purchases-or-orders from the denominator phrase.
_DENOM_LAST_N_RE = re.compile(
    r"\b(?:last|recent|past)\s+(\d{1,3})\s+(?:purchases?|orders?)\b",
    re.IGNORECASE,
)

# Matches "all purchases", "every order", "total purchases" — the unbounded denominator.
_DENOM_ALL_RE = re.compile(
    r"\b(?:all|every|total)\s+(?:purchases?|orders?)\b",
    re.IGNORECASE,
)
_ORDER_DETAIL_RE = re.compile(
    r"\b("
    r"(?:last|latest|most\s+recent)\s+(?:purchase|order)\s+(?:detail|details|content|contents|items?)"
    r"|(?:last|latest|most\s+recent)\s+(?:purchase|order)$"
    r"|(?:amount|total).*(?:content|items?).*(?:last|latest|most\s+recent)\s+(?:purchase|order)"
    r"|items?\s+(?:inside|in|of)\s+(?:the\s+)?(?:order|purchase)"
    r"|(?:order|purchase)\s+(?:detail|details|content|contents|items?)"
    # "last product purchased from my store" / "most recent item sold at my store"
    # / "what was the last thing ordered" / "last item I bought" — same intent as
    # "last order details", phrased from the store owner's or buyer's POV.
    # The optional `\w+` slot allows a pronoun/helper verb ("I", "we", "was")
    # between the noun and the action verb.
    r"|(?:last|latest|most\s+recent)\s+(?:product|item|thing)"
    r"(?:\s+\w+){0,3}\s+(?:purchased|bought|sold|ordered)"
    r")\b",
    re.IGNORECASE,
)
_RIVAL_RE = re.compile(r"\b(rival|rivals|competitor|competitors|competition)\b", re.IGNORECASE)
# Each pattern has a `<store>` named capture. To avoid greedy false positives
# ("Best seller store in electronics category" → fake store="Best in
# electronics"), every pattern requires EITHER an explicit anchor ("who is/are",
# "what are/is", "what else does") OR a marker after the captured name (store
# /shop/seller tag, or apostrophe-s possessive).

# "Who is X[ store]['s] rival[s]" — anchored, so name marker is optional.
_STORE_RIVAL_ANCHORED_RE = re.compile(
    r"\bwho\s+(?:is|are)\s+(?:the\s+)?"
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller))?(?:'s|')?\s+(?:rival|competitor)s?\b",
    re.IGNORECASE,
)
# "X['s|store's] rivals" — inline; possessive or store tag REQUIRED.
_STORE_RIVAL_INLINE_RE = re.compile(
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller)(?:'s|')?|(?:'s|'))"
    r"\s+(?:rival|competitor)s?\b",
    re.IGNORECASE,
)
# "rivals of Aegean Outfitters" / "competitors for Bursa Boots".
_RIVAL_OF_STORE_RE = re.compile(
    r"\b(?:rival|competitor)s?\s+(?:of|for)\s+(?:the\s+)?"
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)\s*[?.!]*$",
    re.IGNORECASE,
)
# "what are X[ store]['s] categories" — anchored.
_STORE_CATEGORIES_ANCHORED_RE = re.compile(
    r"\bwhat\s+(?:are|is)\s+(?:the\s+)?"
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller))?(?:'s|')?\s+(?:categories|category)\b",
    re.IGNORECASE,
)
# "X['s|store's] categories" — inline; possessive or store tag REQUIRED so we
# don't capture "in electronics category" → "in electronics".
_STORE_CATEGORIES_INLINE_RE = re.compile(
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller)(?:'s|')?|(?:'s|'))"
    r"\s+(?:categories|category)\b",
    re.IGNORECASE,
)
_WHAT_ELSE_STORE_SELLS_RE = re.compile(
    r"\bwhat\s+else\s+does\s+"
    r"(?:(?:the\s+)?(?:store|shop|seller)\s+)?"
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller))?\s+sell\b",
    re.IGNORECASE,
)
_BEST_STORE_CATEGORY_RE = re.compile(
    r"\b(?:best\s+seller\s+store|best-selling\s+store|best\s+store|top\s+seller\s+store|"
    r"top-selling\s+store|leading\s+store)\b"
    r".*?\b(?:in|for)\s+(?:the\s+)?(?P<category>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+category)?\s*[?.!]*$",
    re.IGNORECASE,
)
_EXPENSE_CATEGORY_RE = re.compile(
    r"\b(?:which|what)\s+categor(?:y|ies)\b.*\b(?:expense|expenses|spend|spent|bought|purchase|purchases)\b"
    r"|(?:expense|expenses|spend|spent)\b.*\bcategor(?:y|ies)\b",
    re.IGNORECASE,
)
_LAST_10_CATEGORY_VIS_RE = re.compile(
    r"\b(?:categoric|categorical|category)\s+(?:visualization|visualisation|chart|graph|breakdown)\b"
    r".*\b(?:last|recent|past)\s+(?P<n>\d{1,3})\s+(?:purchase|purchases|order|orders)\b"
    r"|\b(?:last|recent|past)\s+(?P<n2>\d{1,3})\s+(?:purchase|purchases|order|orders)\b"
    r".*\b(?:categoric|categorical|category)\s+(?:visualization|visualisation|chart|graph|breakdown)\b",
    re.IGNORECASE,
)
_PROFIT_PRODUCT_RE = re.compile(
    r"\b(?:which|what)\s+(?:product|item)\b.*\b(?:profit|revenue|money|income)\b.*\b(?:year|annual|12\s+months)\b"
    r"|\b(?:profit|revenue|money|income)\b.*\b(?:product|item)\b.*\b(?:year|annual|12\s+months)\b",
    re.IGNORECASE,
)
_PRODUCT_REVENUE_GRAPH_RE = re.compile(
    r"\b(?:show|display|graph|chart|visuali[sz]e)\b.*\b(?:product|products|item|items)\b.*\b(?:revenue|profit|money|income)\b"
    r"|\b(?:product|products|item|items)\b.*\b(?:revenue|profit|money|income)\b.*\b(?:graph|chart|visuali[sz]e|breakdown)\b",
    re.IGNORECASE,
)

# "every store's revenue" / "revenue of every store" / "revenue per store" /
# "stores by revenue" — platform-wide aggregate broken out per store. Without
# this branch the catch-all "revenue" check below returns a daily trend and
# loses the per-store dimension the admin actually asked for.
_PER_STORE_REVENUE_RE = re.compile(
    # "every/all/each/per (the) store(s) ... revenue|sales|..."
    r"\b(?:every|all|each|per)\s+(?:the\s+)?stores?(?:'s|s')?\b"
    r".*\b(?:revenue|revenues|sales|income|earnings|profit)\b"
    # "revenue ... by/per (the) store(s)" — quantifier optional here.
    r"|\b(?:revenue|revenues|sales|income|earnings|profit)\b"
    r".*\b(?:by|per)\s+(?:the\s+)?stores?\b"
    # "revenue of/for every/all/each (the) store(s)"
    r"|\b(?:revenue|revenues|sales|income|earnings|profit)\b"
    r".*\b(?:of|for)\s+(?:every|all|each)\s+(?:the\s+)?stores?\b"
    # "stores by/ranked by/ordered by/sorted by revenue|sales|..."
    r"|\bstores?\s+(?:by|ranked\s+by|ordered\s+by|sorted\s+by)\s+(?:revenue|sales|income|earnings)\b"
    # "how much did every/all/each store(s)/shop(s)/seller(s) make/earn", or
    # the bare "how much did everyone/everybody make". The plain
    # "how much did <X> make" pattern (further down) picks a single named
    # store; the quantifier here signals an aggregate, so we route to the
    # per-store SQL even when the literal word "revenue" is missing.
    r"|\bhow\s+much\s+(?:did|does|has|have)\s+"
    r"(?:"
    r"(?:every|all|each|any)\s+(?:the\s+)?(?:stores?|shops?|sellers?)"
    r"|everyone|everybody|anyone|anybody"
    r")\s+"
    r"(?:make|made|earn|earned|had\s+made|generate|generated)\b",
    re.IGNORECASE,
)

# "monthly revenue" / "revenue by month" / "revenue per month" — per-month
# grouping over the last year, NOT the daily 30-day trend the catch-all
# returns when it sees the word "revenue".
_MONTHLY_REVENUE_RE = re.compile(
    r"\bmonthly\s+(?:revenue|revenues|sales|income|earnings|profit)\b"
    r"|\b(?:revenue|revenues|sales|income|earnings|profit)\s+(?:by|per)\s+month\b"
    r"|\bmonth-(?:over|on)-month\s+(?:revenue|sales|income)\b",
    re.IGNORECASE,
)

# "yearly revenue" / "annual revenue" / "revenue by year" — same problem as
# the monthly catch-all: without an explicit branch the catch-all collapses
# the answer into a daily 30-day window.
_YEARLY_REVENUE_RE = re.compile(
    r"\b(?:yearly|annual)\s+(?:revenue|revenues|sales|income|earnings|profit)\b"
    r"|\b(?:revenue|revenues|sales|income|earnings|profit)\s+(?:by|per)\s+year\b"
    r"|\byear-(?:over|on)-year\s+(?:revenue|sales|income)\b",
    re.IGNORECASE,
)

# "revenue of the platform" / "total platform revenue" / "platform-wide
# revenue" / "platform's revenue" — answers a single platform-total scalar
# instead of a daily trend. For non-admin roles the sanitizer scopes the
# underlying orders so the user sees their own contribution rather than
# leaking other tenants' totals.
_PLATFORM_REVENUE_RE = re.compile(
    r"\b(?:total\s+)?(?:revenue|revenues|sales|income|earnings|profit)"
    r"\s+(?:of|for|from)\s+(?:the\s+)?(?:whole\s+|entire\s+)?platform\b"
    r"|\bplatform(?:[-\s]?wide)?(?:'s)?\s+(?:total\s+)?(?:revenue|revenues|sales|income|earnings|profit)\b",
    re.IGNORECASE,
)

# "revenue of <X>" / "<X>'s revenue" / "<X> store revenue" — single-store
# total. Excluded: "every"/"all"/"each" (handled by _PER_STORE_REVENUE_RE).
_REVENUE_OF_STORE_RE = re.compile(
    r"\b(?:total\s+)?(?:revenue|revenues|sales|income|earnings|profit)"
    r"\s+(?:of|for|from)\s+(?:the\s+)?"
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller))?\s*[?.!]*$",
    re.IGNORECASE,
)
_STORE_REVENUE_INLINE_RE = re.compile(
    r"\b(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"(?:\s+(?:store|shop|seller)(?:'s|')?|(?:'s|'))"
    r"\s+(?:total\s+)?(?:revenue|revenues|sales|income|earnings|profit)\b",
    re.IGNORECASE,
)
# "how much did Aegean Outfitters make/earn/had made/generate"
_HOW_MUCH_DID_STORE_MAKE_RE = re.compile(
    r"\bhow\s+much\s+(?:did|does|has|have)\s+"
    r"(?P<store>[a-z0-9][\w '&.-]{1,80}?)"
    r"\s+(?:make|made|earn|earned|had\s+made|generate|generated)\b",
    re.IGNORECASE,
)

# Aggregate quantifiers that can fool the named-store regex into capturing
# them as a fake store name ("revenue of every store" → store="every").
_AGGREGATE_STORE_TERMS = {
    "every", "all", "each", "any", "every single",
    "all the", "each the", "platform", "platforms", "platform-wide",
    "everyone", "everybody", "anyone", "anybody",
}
# A captured store name beginning with one of these words is also rejected
# ("all stores", "every store", "each shop") — these slip past
# `_AGGREGATE_STORE_TERMS` because the cleaning step strips "store"/"shop"
# but keeps the leading quantifier.
_AGGREGATE_STORE_PREFIXES = ("every ", "all ", "each ", "any ")


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


def _order_id_from_question(question: str) -> Optional[int]:
    match = _ORDER_ID_RE.search(question)
    if not match:
        return None
    return int(match.group(1))


def _clean_named_entity(value: str) -> Optional[str]:
    # Strip both possessive/role tokens AND leading question-words so that
    # a too-greedy regex capture like "What are my rival" or "Which store's"
    # cleans down to nothing instead of leaving "What are" / "Which" as a
    # bogus store name. Real store names don't begin with these tokens.
    value = re.sub(
        r"\b(what|where|which|when|how|who|are|is|do|does|did"
        r"|the|a|an|store|shop|seller|rival|competitor|my|your|our)\b",
        " ", value, flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value).strip(" ?.,'\"")
    if not value:
        return None
    if value.lower() in {"store", "shop", "seller", "rival", "competitor", "my rival"}:
        return None
    return value


def _store_name_from_rival_question(question: str) -> Optional[str]:
    """Extract the store the user is asking about rivals for.

    Anchored "who is/are X['s] rival" first (allows bare names),
    then inline "X['s|store's] rivals" (requires marker), then
    "rivals of X". Names that clean to an empty/discarded entity are
    treated as "no specific store" so the caller falls back to the generic
    rivals-for-top-items branch."""
    patterns = (
        _STORE_RIVAL_ANCHORED_RE,
        _STORE_RIVAL_INLINE_RE,
        _RIVAL_OF_STORE_RE,
    )
    for pattern in patterns:
        match = pattern.search(question.strip())
        if not match:
            continue
        store = _clean_named_entity(match.group("store"))
        if store:
            return store
    return None


def _store_name_from_category_question(question: str) -> Optional[str]:
    patterns = (
        _WHAT_ELSE_STORE_SELLS_RE,
        _STORE_CATEGORIES_ANCHORED_RE,
        _STORE_CATEGORIES_INLINE_RE,
    )
    for pattern in patterns:
        match = pattern.search(question.strip())
        if match:
            store = _clean_named_entity(match.group("store"))
            if store:
                return store
    return None


def _category_from_best_store_question(question: str) -> Optional[str]:
    match = _BEST_STORE_CATEGORY_RE.search(question.strip())
    if not match:
        return None
    return _clean_named_entity(match.group("category"))


def _store_name_from_revenue_question(question: str) -> Optional[str]:
    """Extract a single store name from a revenue/earnings question.

    Returns None when the phrase asks about every/all stores so the caller
    can route to the platform-wide aggregate instead of a single-store
    lookup. Also returns None when the cleaned name is a stop word
    ("my", "your", etc.) that real store names won't match.
    """
    q = question.strip()
    if _PER_STORE_REVENUE_RE.search(q):
        return None
    for pattern in (_REVENUE_OF_STORE_RE, _HOW_MUCH_DID_STORE_MAKE_RE, _STORE_REVENUE_INLINE_RE):
        match = pattern.search(q)
        if not match:
            continue
        store = _clean_named_entity(match.group("store"))
        if not store:
            continue
        lowered = store.lower()
        if lowered in _AGGREGATE_STORE_TERMS:
            continue
        if any(lowered.startswith(p) for p in _AGGREGATE_STORE_PREFIXES):
            continue
        return store
    return None


def _last_n_from_category_visualization(question: str, default: int = 10) -> int:
    match = _LAST_10_CATEGORY_VIS_RE.search(question)
    if not match:
        return default
    raw = match.group("n") or match.group("n2")
    if not raw:
        return default
    return max(1, min(int(raw), 100))


def _history_text(history: Optional[List[ChatTurn]]) -> str:
    if not history:
        return ""
    return " ".join((turn.content or "") for turn in history[-4:]).lower()


def _is_product_revenue_followup(question: str, history: Optional[List[ChatTurn]]) -> bool:
    q = (question or "").strip().lower()
    if not re.search(r"\b(show|graph|chart|visuali[sz]e|display)\b", q):
        return False
    if not re.search(r"\b(it|that|this|revenue|profit|money|item|product|items|products)\b", q):
        return False
    h = _history_text(history)
    return bool(
        re.search(r"\b(product|item|products|items)\b", h)
        and re.search(r"\b(revenue|profit|money|income)\b", h)
    )


def _is_high_confidence_stub_intent(question: str) -> bool:
    lower = question.lower()
    if _RIVAL_RE.search(question):
        return True
    if _store_name_from_category_question(question):
        return True
    if _category_from_best_store_question(question):
        return True
    if _EXPENSE_CATEGORY_RE.search(question):
        return True
    if _LAST_10_CATEGORY_VIS_RE.search(question):
        return True
    if _PRODUCT_REVENUE_GRAPH_RE.search(question) or _PROFIT_PRODUCT_RE.search(question):
        return True
    # Store-revenue intents (per-store / monthly / single-named-store) — the
    # LLM otherwise tends to fall back to a daily revenue trend regardless of
    # whether the user asked about stores or months.
    if _PER_STORE_REVENUE_RE.search(question):
        return True
    if _PLATFORM_REVENUE_RE.search(question):
        return True
    if _MONTHLY_REVENUE_RE.search(question) or _YEARLY_REVENUE_RE.search(question):
        return True
    if _store_name_from_revenue_question(question):
        return True
    if _LAST_PURCHASE_PERCENT_RE.search(question):
        return True
    if _ORDER_DETAIL_RE.search(question) or _order_id_from_question(question) is not None:
        return True
    if _store_name_from_sales_question(question):
        return True
    if _STORE_UNITS_RE.search(question):
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
15. SELLER / STORE BY UNITS SOLD - questions like "who sold the most items" or
    "which store sold the most products" ask for a STORE/SELLER, not an item.
    Return store name and SUM(order_items.quantity) as units, ordered
    descending. For admin/corporate, this can be computed through
    order_items -> products -> stores; for individual users, use orders so the
    sanitizer can scope the result to that user's purchases.
16. LAST PURCHASE / ORDER DETAILS - questions like "last purchase details",
    "last order detail", "the items inside order with id 430967", or "amount
    and content of my last purchase" ask for the order and every item in it.
    Return one row per item with order_id, status, grand_total, created_at,
    product, quantity, price, and line_total. Always include `orders` so the
    sanitizer can enforce account/store ownership.
17. LAST PURCHASE PERCENTAGE - questions like "What's the percentage of my last
    purchase in total value of my last 10 purchases?" ask for one percentage.
    Return last_purchase, last_10_total, and percentage.

Schema:
"""


# The SQL agent does not see role context anymore — scope is the sanitizer's job.
SCOPE_HINT = {"ADMIN": "", "CORPORATE": "", "INDIVIDUAL": ""}


def _top_product_names_subquery(source_store_name: Optional[str] = None) -> str:
    store_join = ""
    store_where = ""
    if source_store_name:
        store_join = "JOIN stores source_s ON source_s.id = p.store_id\n"
        store_where = f"WHERE LOWER(source_s.name) LIKE LOWER('%{_esc(source_store_name)}%')\n"
    return (
        "SELECT top_products.product_name\n"
        "FROM (\n"
        "  SELECT LOWER(p.name) AS product_name, SUM(oi.quantity) AS units\n"
        "  FROM order_items oi\n"
        "  JOIN orders o ON o.id = oi.order_id\n"
        "  JOIN products p ON p.id = oi.product_id\n"
        f"  {store_join}"
        f"  {store_where}"
        "  GROUP BY p.id, p.name\n"
        "  ORDER BY units DESC\n"
        "  LIMIT 5\n"
        ") top_products"
    )


def _rivals_for_top_items_sql(role: Role, source_store_name: Optional[str] = None) -> str:
    exclude = ""
    if source_store_name:
        exclude = f"AND LOWER(rival_s.name) NOT LIKE LOWER('%{_esc(source_store_name)}%')\n"
    elif role == "CORPORATE":
        exclude = "AND rival_s.owner_id <> :scoped_store_id\n"
    return (
        "SELECT rival_s.name AS rival_store, "
        "COUNT(DISTINCT rival_p.name) AS matching_items, "
        "ROUND(AVG(r.star_rating), 2) AS avg_rating\n"
        "FROM products rival_p\n"
        "JOIN stores rival_s ON rival_s.id = rival_p.store_id\n"
        "JOIN reviews r ON r.product_id = rival_p.id\n"
        "WHERE LOWER(rival_p.name) IN (\n"
        f"{_top_product_names_subquery(source_store_name)}\n"
        ")\n"
        f"{exclude}"
        "GROUP BY rival_s.id, rival_s.name\n"
        "HAVING AVG(r.star_rating) >= 4\n"
        "ORDER BY matching_items DESC, avg_rating DESC\n"
        "LIMIT 5;"
    )


def _store_rival_by_categories_sql(store_name: str) -> str:
    return (
        "SELECT rival_s.name AS rival_store, "
        "COUNT(DISTINCT rival_p.category_id) AS matching_categories, "
        "ROUND(AVG(r.star_rating), 2) AS avg_rating\n"
        "FROM products rival_p\n"
        "JOIN stores rival_s ON rival_s.id = rival_p.store_id\n"
        "JOIN reviews r ON r.product_id = rival_p.id\n"
        "WHERE rival_p.category_id IN (\n"
        "  SELECT DISTINCT source_p.category_id\n"
        "  FROM products source_p\n"
        "  JOIN stores source_s ON source_s.id = source_p.store_id\n"
        f"  WHERE LOWER(source_s.name) LIKE LOWER('%{_esc(store_name)}%')\n"
        ")\n"
        f"AND LOWER(rival_s.name) NOT LIKE LOWER('%{_esc(store_name)}%')\n"
        "GROUP BY rival_s.id, rival_s.name\n"
        "HAVING AVG(r.star_rating) >= 4\n"
        "ORDER BY matching_categories DESC, avg_rating DESC\n"
        "LIMIT 5;"
    )


def _rival_categories_sql(role: Role) -> str:
    exclude = "AND rival_s.owner_id <> :scoped_store_id\n" if role == "CORPORATE" else ""
    return (
        "SELECT rival_s.name AS store, c.name AS category, COUNT(DISTINCT rival_p.id) AS products\n"
        "FROM products rival_p\n"
        "JOIN stores rival_s ON rival_s.id = rival_p.store_id\n"
        "JOIN categories c ON c.id = rival_p.category_id\n"
        "WHERE LOWER(rival_p.name) IN (\n"
        f"{_top_product_names_subquery()}\n"
        ")\n"
        f"{exclude}"
        "GROUP BY rival_s.id, rival_s.name, c.id, c.name\n"
        "ORDER BY rival_s.name, products DESC, c.name\n"
        "LIMIT 100;"
    )


def _store_categories_listing_sql(store_name: str) -> str:
    """Catalog of categories carried by a single named store, with product counts."""
    return (
        "SELECT s.name AS store, c.name AS category, COUNT(p.id) AS products\n"
        "FROM stores s\n"
        "JOIN products p ON p.store_id = s.id\n"
        "JOIN categories c ON c.id = p.category_id\n"
        f"WHERE LOWER(s.name) LIKE LOWER('%{_esc(store_name)}%')\n"
        "GROUP BY s.id, s.name, c.id, c.name\n"
        "ORDER BY products DESC, c.name\n"
        "LIMIT 100;"
    )


def generate_sql_stub(question: str, role: Role, history: Optional[List[ChatTurn]] = None) -> str:
    """Deterministic stub used when no LLM is configured.

    Note: no scope clauses here on purpose — the sanitizer always re-injects
    them based on the authenticated session, so adding them here would just
    produce duplicate (but correct) WHERE conditions in the preview.
    """
    lower = question.lower()
    limit = _top_limit(question)

    if _RIVAL_RE.search(question):
        store_name = _store_name_from_rival_question(question)
        if store_name:
            # "what are my rival X's categories" → user wants X's catalog,
            # not the platform-wide rival aggregate.
            if "categor" in lower:
                return _store_categories_listing_sql(store_name)
            return _store_rival_by_categories_sql(store_name)
        if "categor" in lower:
            # No specific rival named, but the categories question still
            # might name a store via the categories pattern.
            named = _store_name_from_category_question(question)
            if named:
                return _store_categories_listing_sql(named)
            return _rival_categories_sql(role)
        return _rivals_for_top_items_sql(role)

    store_for_categories = _store_name_from_category_question(question)
    if store_for_categories:
        return _store_categories_listing_sql(store_for_categories)

    best_category = _category_from_best_store_question(question)
    if best_category:
        if role == "ADMIN":
            return (
                "SELECT s.name AS store, SUM(oi.quantity) AS units, "
                "COALESCE(ROUND(AVG(pr.avg_rating), 2), 0) AS avg_rating\n"
                "FROM order_items oi\n"
                "JOIN products p ON p.id = oi.product_id\n"
                "JOIN stores s ON s.id = p.store_id\n"
                "JOIN categories c ON c.id = p.category_id\n"
                "LEFT JOIN (\n"
                "  SELECT product_id, AVG(star_rating) AS avg_rating\n"
                "  FROM reviews\n"
                "  GROUP BY product_id\n"
                ") pr ON pr.product_id = p.id\n"
                f"WHERE LOWER(c.name) LIKE LOWER('%{_esc(best_category)}%')\n"
                "GROUP BY s.id, s.name\n"
                "ORDER BY units DESC, avg_rating DESC\n"
                "LIMIT 1;"
            )
        return (
            "SELECT s.name AS store, COUNT(p.id) AS product_count, "
            "COALESCE(ROUND(AVG(r.star_rating), 2), 0) AS avg_rating\n"
            "FROM stores s\n"
            "JOIN products p ON p.store_id = s.id\n"
            "JOIN categories c ON c.id = p.category_id\n"
            "LEFT JOIN reviews r ON r.product_id = p.id\n"
            f"WHERE LOWER(c.name) LIKE LOWER('%{_esc(best_category)}%') AND p.active = TRUE\n"
            "GROUP BY s.id, s.name\n"
            "ORDER BY avg_rating DESC, product_count DESC\n"
            "LIMIT 1;"
        )

    if _LAST_10_CATEGORY_VIS_RE.search(question):
        n = _last_n_from_category_visualization(question)
        return (
            "SELECT c.name AS category, SUM(oi.price * oi.quantity) AS spent\n"
            "FROM (\n"
            "  SELECT id\n"
            "  FROM orders\n"
            "  ORDER BY created_at DESC\n"
            f"  LIMIT {n}\n"
            ") recent_orders\n"
            "JOIN order_items oi ON oi.order_id = recent_orders.id\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "JOIN categories c ON c.id = p.category_id\n"
            "GROUP BY c.id, c.name\n"
            "ORDER BY spent DESC\n"
            "LIMIT 100;"
        )

    if _EXPENSE_CATEGORY_RE.search(question):
        return (
            "SELECT c.name AS category, SUM(oi.price * oi.quantity) AS spent\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "JOIN categories c ON c.id = p.category_id\n"
            "WHERE o.created_at >= DATE_FORMAT(NOW(), '%Y-%m-01')\n"
            "GROUP BY c.id, c.name\n"
            "ORDER BY spent DESC\n"
            "LIMIT 1;"
        )

    if _PRODUCT_REVENUE_GRAPH_RE.search(question) or _is_product_revenue_followup(question, history):
        return (
            "SELECT p.name AS product, SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 1 YEAR\n"
            "GROUP BY p.id, p.name\n"
            "ORDER BY revenue DESC\n"
            "LIMIT 100;"
        )

    if _PROFIT_PRODUCT_RE.search(question):
        return (
            "SELECT p.name AS product, SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 1 YEAR\n"
            "GROUP BY p.id, p.name\n"
            "ORDER BY revenue DESC\n"
            "LIMIT 1;"
        )

    if _LAST_PURCHASE_PERCENT_RE.search(question):
        n_match = _DENOM_LAST_N_RE.search(question)
        if n_match:
            n = max(1, min(int(n_match.group(1)), 1000))
            denom_alias = f"last_{n}_total"
            denom_subquery = (
                f"  SELECT SUM(recent_orders.grand_total) AS {denom_alias}\n"
                "  FROM (\n"
                "    SELECT grand_total\n"
                "    FROM orders\n"
                "    ORDER BY created_at DESC\n"
                f"    LIMIT {n}\n"
                "  ) recent_orders"
            )
        elif _DENOM_ALL_RE.search(question):
            denom_alias = "all_total"
            denom_subquery = (
                f"  SELECT SUM(grand_total) AS {denom_alias}\n"
                "  FROM orders"
            )
        else:
            # Regex required a denominator phrase, so this branch is only
            # reachable if the future regex relaxes — fall back to "last 10"
            # to preserve the historical default rather than crash.
            denom_alias = "last_10_total"
            denom_subquery = (
                f"  SELECT SUM(recent_orders.grand_total) AS {denom_alias}\n"
                "  FROM (\n"
                "    SELECT grand_total\n"
                "    FROM orders\n"
                "    ORDER BY created_at DESC\n"
                "    LIMIT 10\n"
                "  ) recent_orders"
            )
        return (
            "SELECT last_order.grand_total AS last_purchase, "
            f"denom.{denom_alias} AS {denom_alias}, "
            f"ROUND((last_order.grand_total / NULLIF(denom.{denom_alias}, 0)) * 100, 2) AS percentage\n"
            "FROM (\n"
            "  SELECT id, grand_total, created_at\n"
            "  FROM orders\n"
            "  ORDER BY created_at DESC\n"
            "  LIMIT 1\n"
            ") last_order\n"
            "CROSS JOIN (\n"
            f"{denom_subquery}\n"
            ") denom;"
        )

    order_id = _order_id_from_question(question)
    if order_id is not None:
        return (
            "SELECT o.id AS order_id, o.status, o.grand_total, o.created_at, "
            "p.name AS product, oi.quantity, oi.price, "
            "(oi.quantity * oi.price) AS line_total\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "JOIN products p ON p.id = oi.product_id\n"
            f"WHERE o.id = {order_id}\n"
            "ORDER BY p.name LIMIT 100;"
        )

    if _ORDER_DETAIL_RE.search(question):
        return (
            "SELECT o.id AS order_id, o.status, o.grand_total, o.created_at, "
            "p.name AS product, oi.quantity, oi.price, "
            "(oi.quantity * oi.price) AS line_total\n"
            "FROM (\n"
            "  SELECT id, status, grand_total, created_at\n"
            "  FROM orders\n"
            "  ORDER BY created_at DESC\n"
            "  LIMIT 1\n"
            ") o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "ORDER BY p.name LIMIT 100;"
        )

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

    if _STORE_UNITS_RE.search(question):
        store_limit = _top_limit(question, default=1)
        if role == "INDIVIDUAL":
            return (
                "SELECT s.name AS store, SUM(oi.quantity) AS units\n"
                "FROM orders o\n"
                "JOIN order_items oi ON oi.order_id = o.id\n"
                "JOIN stores s ON s.id = o.store_id\n"
                f"GROUP BY s.id, s.name ORDER BY units DESC LIMIT {store_limit};"
            )
        return (
            "SELECT s.name AS store, SUM(product_units.units) AS units\n"
            "FROM (\n"
            "  SELECT product_id, SUM(quantity) AS units\n"
            "  FROM order_items\n"
            "  GROUP BY product_id\n"
            ") product_units\n"
            "JOIN products p ON p.id = product_units.product_id\n"
            "JOIN stores s ON s.id = p.store_id\n"
            f"GROUP BY s.id, s.name ORDER BY units DESC LIMIT {store_limit};"
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

    # Per-store totals — admin's "total revenues of every store" lands here.
    # Sanitizer scopes orders/stores for non-admin roles automatically, so the
    # same SQL gives a corporate user their own stores' totals and an
    # individual user the spend they've contributed to each store.
    if _PER_STORE_REVENUE_RE.search(question):
        return (
            "SELECT s.name AS store, "
            "COALESCE(SUM(oi.price * oi.quantity), 0) AS revenue\n"
            "FROM stores s\n"
            "LEFT JOIN orders o ON o.store_id = s.id\n"
            "LEFT JOIN order_items oi ON oi.order_id = o.id\n"
            "GROUP BY s.id, s.name\n"
            "ORDER BY revenue DESC\n"
            "LIMIT 100;"
        )

    # Platform-total revenue — single scalar. Sanitizer still scopes orders
    # for non-admin roles, so corporate/individual users get their own slice.
    if _PLATFORM_REVENUE_RE.search(question):
        return (
            "SELECT COALESCE(SUM(oi.price * oi.quantity), 0) AS total_revenue\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id;"
        )

    # Per-month grouping over the last year — the catch-all below would
    # collapse "monthly revenue" into a daily 30-day trend instead. When the
    # user also names a store ("monthly revenue of DS6 store") we filter by
    # store name so the trend reflects that store, not the whole platform.
    if _MONTHLY_REVENUE_RE.search(question):
        named_store = _store_name_from_revenue_question(question)
        if named_store:
            return (
                "SELECT DATE_FORMAT(o.created_at, '%Y-%m') AS month, "
                "SUM(oi.price * oi.quantity) AS revenue\n"
                "FROM orders o\n"
                "JOIN order_items oi ON oi.order_id = o.id\n"
                "JOIN stores s ON s.id = o.store_id\n"
                f"WHERE LOWER(s.name) LIKE LOWER('%{_esc(named_store)}%')\n"
                "  AND o.created_at >= NOW() - INTERVAL 12 MONTH\n"
                "GROUP BY month\n"
                "ORDER BY month;"
            )
        return (
            "SELECT DATE_FORMAT(o.created_at, '%Y-%m') AS month, "
            "SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 12 MONTH\n"
            "GROUP BY month\n"
            "ORDER BY month;"
        )

    # Per-year grouping over the last 5 years. Same shape as monthly; filters
    # by store name when paired with one ("yearly revenue of DS6 store").
    if _YEARLY_REVENUE_RE.search(question):
        named_store = _store_name_from_revenue_question(question)
        if named_store:
            return (
                "SELECT YEAR(o.created_at) AS year, "
                "SUM(oi.price * oi.quantity) AS revenue\n"
                "FROM orders o\n"
                "JOIN order_items oi ON oi.order_id = o.id\n"
                "JOIN stores s ON s.id = o.store_id\n"
                f"WHERE LOWER(s.name) LIKE LOWER('%{_esc(named_store)}%')\n"
                "  AND o.created_at >= NOW() - INTERVAL 5 YEAR\n"
                "GROUP BY year\n"
                "ORDER BY year;"
            )
        return (
            "SELECT YEAR(o.created_at) AS year, "
            "SUM(oi.price * oi.quantity) AS revenue\n"
            "FROM orders o\n"
            "JOIN order_items oi ON oi.order_id = o.id\n"
            "WHERE o.created_at >= NOW() - INTERVAL 5 YEAR\n"
            "GROUP BY year\n"
            "ORDER BY year;"
        )

    # Single-store revenue lookup — "total revenue of DS6 store",
    # "Aegean Outfitters' revenue", "how much did Aegean Outfitters make".
    revenue_store_name = _store_name_from_revenue_question(question)
    if revenue_store_name:
        return (
            "SELECT s.name AS store, "
            "COUNT(o.id) AS sales_count, "
            "COALESCE(SUM(o.grand_total), 0) AS revenue\n"
            "FROM stores s\n"
            "LEFT JOIN orders o ON o.store_id = s.id\n"
            f"WHERE LOWER(s.name) LIKE LOWER('%{_esc(revenue_store_name)}%')\n"
            "GROUP BY s.id, s.name\n"
            "ORDER BY revenue DESC LIMIT 5;"
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
    if _is_high_confidence_stub_intent(question) or _is_product_revenue_followup(question, history):
        return generate_sql_stub(question, role, history)
    if llm is None:
        return generate_sql_stub(question, role, history)
    try:
        return generate_sql_with_llm(llm, question, role, history)
    except Exception:
        return generate_sql_stub(question, role, history)
