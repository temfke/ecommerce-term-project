"""SQL Sanitizer — the security-critical bridge between LLM-generated SQL and execution.

Defense-in-depth. Even if the SQL agent forgets a scope filter, even if a
prompt injection slipped past the guardrails, the sanitizer:

1. Rejects multi-statement, non-SELECT, or unparseable input
2. Bans SELECT *, sensitive columns, and dangerous MySQL functions
3. Forces a LIMIT cap of 100 rows
4. ALWAYS injects a role-scoped WHERE clause on owned tables, regardless of
   whatever the LLM produced. The user_id / store_owner_id values come from
   the JWT inside Spring Boot, never from the request body or chat input.

Returns a SanitizeResult: ok=True with rewritten SQL, or ok=False with reason.
"""
import re
from dataclasses import dataclass
from typing import Optional

import sqlglot
from sqlglot import exp

from .schema import Role


@dataclass
class SanitizeResult:
    ok: bool
    sql: Optional[str] = None
    reason: Optional[str] = None
    blocked_by: Optional[str] = None


# Tables we know how to scope per role and the ownership column on each table.
INDIVIDUAL_OWNED: dict[str, str] = {
    "orders": "user_id",
    "reviews": "user_id",
    "addresses": "user_id",
    "customer_profiles": "user_id",
}

# Corporate-owned via direct store_id FK; stores itself filtered separately on owner_id.
CORPORATE_OWNED: dict[str, str] = {
    "orders": "store_id",
    "products": "store_id",
}

SENSITIVE_COLS: set[str] = {
    "password_hash",
    "email_verification_token",
    "email_verification_expires_at",
    "refresh_token",
    "stripe_customer_id",
    "stripe_payment_intent_id",
    "stripe_session_id",
}

# MySQL functions that would let SQL touch the filesystem, sleep, or introspect the server.
DANGEROUS_FUNCS: set[str] = {
    "load_file", "benchmark", "sleep",
    "user", "current_user", "version",
    "database", "schema",
}

MAX_ROWS = 100


def sanitize(
    raw_sql: str,
    role: Role,
    user_id: int,
    store_owner_id: Optional[int] = None,
    cross_store: bool = False,
) -> SanitizeResult:
    """Sanitize an LLM-produced SQL string and re-inject scope filters.

    `cross_store=True` is set by the graph for marketplace-public catalog
    questions (including CORPORATE rival/competitor questions). It relaxes the
    filter on catalog tables such as `products` and `stores`, but keeps private
    transaction tables scoped so other tenants' orders are never exposed.
    """
    if not raw_sql or not raw_sql.strip():
        return SanitizeResult(ok=False, reason="Empty SQL", blocked_by="empty")

    # Substitute the LLM's placeholder tokens with literals so sqlglot can parse.
    # Safe because we re-inject scope ourselves below; we don't trust whatever
    # filtering the LLM produced.
    prepared = (
        raw_sql.replace(":scoped_user_id", str(int(user_id)))
               .replace(":scoped_store_id", str(int(store_owner_id or -1)))
    )

    # Belt-and-suspenders: catch dangerous functions before parsing, in case
    # sqlglot represents them as a class shape we don't recognize below.
    for fn_name in DANGEROUS_FUNCS:
        if re.search(rf"\b{re.escape(fn_name)}\s*\(", prepared, flags=re.IGNORECASE):
            return SanitizeResult(
                ok=False,
                reason=f"Function not allowed: {fn_name}",
                blocked_by="dangerous_function",
            )

    try:
        statements = sqlglot.parse(prepared, dialect="mysql")
    except sqlglot.errors.ParseError as e:
        return SanitizeResult(ok=False, reason=f"Could not parse SQL: {e}", blocked_by="parse_error")

    statements = [s for s in statements if s is not None]
    if not statements:
        return SanitizeResult(ok=False, reason="No statements found", blocked_by="empty")
    if len(statements) > 1:
        return SanitizeResult(ok=False, reason="Multiple statements are not allowed", blocked_by="multi_statement")

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        kind = type(tree).__name__.upper()
        return SanitizeResult(
            ok=False,
            reason=f"Only SELECT statements are allowed (got {kind})",
            blocked_by="non_select",
        )

    # Block sensitive column refs anywhere in the tree
    for col in tree.find_all(exp.Column):
        col_name = (col.name or "").lower()
        if col_name in SENSITIVE_COLS:
            return SanitizeResult(
                ok=False,
                reason=f"Column not allowed: {col_name}",
                blocked_by="sensitive_column",
            )

    # Block dangerous functions detected via the AST too (covers identifiers
    # that aren't function calls, like SELECT USER or SELECT VERSION()).
    for func in tree.find_all(exp.Func):
        fn = ""
        if isinstance(func, exp.Anonymous):
            fn = (func.name or "").lower()
        else:
            fn = (getattr(func, "key", "") or type(func).__name__).lower()
        if fn in DANGEROUS_FUNCS:
            return SanitizeResult(
                ok=False,
                reason=f"Function not allowed: {fn}",
                blocked_by="dangerous_function",
            )

    # Block SELECT *
    for select in tree.find_all(exp.Select):
        for proj in select.expressions:
            if isinstance(proj, exp.Star):
                return SanitizeResult(
                    ok=False,
                    reason="SELECT * is not allowed; list columns explicitly",
                    blocked_by="select_star",
                )

    # Inject scope filters on every SELECT in the tree
    if role == "INDIVIDUAL":
        _inject_individual_scope(tree, user_id, public_catalog=cross_store)
    elif role == "CORPORATE":
        if store_owner_id is None:
            return SanitizeResult(
                ok=False,
                reason="Corporate user has no store mapped to their account",
                blocked_by="missing_scope",
            )
        _inject_corporate_scope(tree, store_owner_id, cross_store=cross_store)
    # ADMIN: no rewrite

    _enforce_limit(tree, MAX_ROWS)

    return SanitizeResult(ok=True, sql=tree.sql(dialect="mysql", pretty=True))


def _inject_individual_scope(
    tree: exp.Expression,
    user_id: int,
    public_catalog: bool = False,
) -> None:
    uid = int(user_id)
    for select in list(tree.find_all(exp.Select)):
        for table_name, alias in _tables_in(select):
            if table_name not in INDIVIDUAL_OWNED:
                continue
            if public_catalog and table_name == "reviews":
                continue
            ref = alias or table_name
            col_name = INDIVIDUAL_OWNED[table_name]
            _and_where(
                select,
                sqlglot.parse_one(f"{ref}.{col_name} = {uid}", dialect="mysql"),
            )


def _inject_corporate_scope(
    tree: exp.Expression,
    store_owner_id: int,
    cross_store: bool = False,
) -> None:
    """Corporate users see only data tied to stores they own.

    For tables with store_id (orders, products) → filter via subquery:
        store_id IN (SELECT id FROM stores WHERE owner_id = <owner_id>)
    For the stores table itself → filter directly:
        owner_id = <owner_id>

    `cross_store=True` skips the filter on `products` and the `stores` table
    (the catalog has no PII), but still scopes `orders` so cross-tenant
    transaction data never leaks. Used for rival/competitor questions where
    the corporate user legitimately needs to see other stores in their space.

    We build each filter as raw SQL and let sqlglot parse it, rather than
    constructing exp.In / exp.Subquery by hand — that internal API has changed
    across sqlglot versions and producing it manually has caused syntax errors.

    We materialise the SELECT list before mutating the tree because find_all
    is a generator and would otherwise revisit the subqueries we just injected.
    """
    selects = list(tree.find_all(exp.Select))
    owner_id = int(store_owner_id)

    for select in selects:
        for table_name, alias in _tables_in(select):
            ref = alias or table_name

            if table_name in CORPORATE_OWNED:
                if cross_store and table_name != "orders":
                    continue
                col_name = CORPORATE_OWNED[table_name]
                filter_sql = (
                    f"{ref}.{col_name} IN "
                    f"(SELECT id FROM stores WHERE owner_id = {owner_id})"
                )
                _and_where(select, sqlglot.parse_one(filter_sql, dialect="mysql"))

            elif table_name == "stores" and not cross_store:
                _and_where(
                    select,
                    sqlglot.parse_one(f"{ref}.owner_id = {owner_id}", dialect="mysql"),
                )

            elif table_name == "reviews" and not cross_store:
                filter_sql = (
                    f"{ref}.product_id IN ("
                    "SELECT p.id FROM products p "
                    "JOIN stores s ON s.id = p.store_id "
                    f"WHERE s.owner_id = {owner_id})"
                )
                _and_where(select, sqlglot.parse_one(filter_sql, dialect="mysql"))


def _tables_in(select: exp.Select) -> list[tuple[str, Optional[str]]]:
    """Return (table_name_lower, alias_or_None) for tables directly used by this SELECT.

    Walks only the FROM and JOIN clauses; tables nested inside subqueries belong
    to those subqueries' SELECT nodes and will be visited separately.
    """
    seen: list[tuple[str, Optional[str]]] = []
    sources: list[exp.Expression] = []

    from_expr = select.args.get("from")
    if from_expr is not None:
        direct = from_expr.this
        if direct is not None:
            sources.append(direct)
        sources.extend(from_expr.expressions or [])

    for join in select.args.get("joins") or []:
        direct = join.this
        if direct is not None:
            sources.append(direct)

    for src in sources:
        # Important: do not recurse into Subquery sources here. Each nested
        # SELECT is visited by the caller, and adding its base table filter to
        # the outer SELECT produces invalid SQL like `orders.user_id = ...`
        # when the outer scope only knows the derived-table alias.
        if not isinstance(src, exp.Table):
            continue
        name = (src.name or "").lower()
        alias = None
        if src.alias:
            alias = src.alias if isinstance(src.alias, str) else src.alias_or_name
        if name:
            seen.append((name, alias))
    return seen


def _and_where(select: exp.Select, new_filter: exp.Expression) -> None:
    existing = select.args.get("where")
    if existing is None:
        select.set("where", exp.Where(this=new_filter))
    else:
        select.set("where", exp.Where(this=exp.And(this=existing.this, expression=new_filter)))


def _enforce_limit(tree: exp.Expression, max_rows: int) -> None:
    if not isinstance(tree, exp.Select):
        return
    limit = tree.args.get("limit")
    if limit is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
        return
    expr = limit.expression
    if isinstance(expr, exp.Literal) and expr.is_int and int(expr.this) > max_rows:
        limit.set("expression", exp.Literal.number(max_rows))
