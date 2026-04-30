"""LangGraph state machine wiring the agents from section 5.4 of the project spec.

In step 2 the graph stops after SQL generation — it returns the SQL preview to
the caller without executing it. Steps 4-6 will add: sanitizer, executor, analysis,
visualization.
"""
import re
from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from .agents import guardrails, sql as sql_agent
from .agents.analysis import summarize as summarize_with_analyst
from .analyzer import analyze
from .executor import ExecutionResult, execute as execute_sql
from .llm import get_chat_model
from .sanitizer import sanitize
from .schema import (
    ChatRequest, ChatResponse, Classification, DataRow, Guardrail, Role, TableData,
)


class GraphState(TypedDict, total=False):
    question: str
    role: Role
    user_id: int
    store_owner_id: Optional[int]
    first_name: Optional[str]
    history: list
    classification: Classification
    trigger: str
    cross_store: bool
    public_catalog: bool
    sql_preview: str
    sanitize_blocked: bool
    sanitize_reason: str
    sanitize_category: str
    execution: ExecutionResult
    response: ChatResponse


_LLM = get_chat_model()


def _scope_label(role: Role) -> str:
    return {"ADMIN": "platform", "CORPORATE": "store", "INDIVIDUAL": "account"}[role]


def node_guardrails(state: GraphState) -> GraphState:
    cls, trig = guardrails.classify(_LLM, state["question"], state["role"])
    state["classification"] = cls
    state["trigger"] = trig
    state["cross_store"] = guardrails.detect_rival_query(state["question"], state["role"])
    state["public_catalog"] = guardrails.detect_public_info_query(state["question"], state["role"])
    return state


def node_greeting(state: GraphState) -> GraphState:
    name = state.get("first_name") or "there"
    state["response"] = ChatResponse(
        status="GREETING",
        narrative=(
            f"Hi {name} — I can answer questions about your "
            f"{_scope_label(state['role'])} data. Try one of the suggested questions below."
        ),
    )
    return state


def node_blocked(state: GraphState) -> GraphState:
    state["response"] = ChatResponse(
        status="BLOCKED",
        narrative=(
            "This message tripped the safety filters. Attempts to alter the "
            "system prompt are blocked and logged."
        ),
        guardrail=Guardrail(
            type="Prompt Injection",
            trigger=f'"{state["trigger"]}"',
            action="Request fully rejected",
        ),
    )
    return state


def node_sql_injection(state: GraphState) -> GraphState:
    state["response"] = ChatResponse(
        status="BLOCKED",
        narrative=(
            "That message looks like an attempt to run raw SQL. The chatbot only "
            "executes safe, system-generated read-only queries — even for admins."
        ),
        guardrail=Guardrail(
            type="SQL Injection Attempt",
            trigger=f'"{state["trigger"]}"',
            action="SQL generation halted",
        ),
    )
    return state


def node_cross_tenant(state: GraphState) -> GraphState:
    state["response"] = ChatResponse(
        status="BLOCKED",
        narrative=(
            f"I can only show your own {_scope_label(state['role'])} data. "
            "Cross-tenant access isn't permitted."
        ),
        guardrail=Guardrail(
            type="Cross-tenant data access",
            trigger=f'"{state["trigger"]}"',
            action="SQL generation halted",
        ),
    )
    return state


_EXPLANATION_FALLBACK = (
    "I work out the figure by aggregating the relevant rows from your data — "
    "using the scoped rows available to your role. When a percentage is "
    "involved, I divide the matching part by the matching total; otherwise I "
    "summarize the relevant totals, rankings, or categories from the result."
)

_EXPLANATION_SYSTEM_PROMPT = (
    "You are explaining or clarifying the previous assistant answer. "
    "Describe the reasoning, formula, or meaning in plain English, in 2-3 short "
    "sentences (under 80 words). Do NOT show SQL, code, or column names; "
    "phrase it the way a friendly analyst would on a call."
)


def _last_assistant_turn(history) -> str:
    if not history:
        return ""
    for turn in reversed(history):
        role = getattr(turn, "role", None) if not isinstance(turn, dict) else turn.get("role")
        content = getattr(turn, "content", None) if not isinstance(turn, dict) else turn.get("content")
        if role == "assistant" and content:
            return str(content)
    return ""


def _methodology_from_context(question: str, previous_answer: str) -> Optional[str]:
    q = (question or "").lower()
    prev = (previous_answer or "").lower()
    combined = f"{q} {prev}"

    if "rival" in combined or "competitor" in combined:
        return (
            "I took your five best-selling items, looked for other stores with matching items or matching product categories, "
            "then ranked those stores by their average rating on those matching products."
        )
    if "percentage" in combined or "%" in combined:
        return (
            "I divided the value of the last purchase by the total value of the comparison set, such as all purchases or the last N purchases, "
            "then multiplied the result by 100."
        )
    if "revenue" in combined or "profit" in combined or "money" in combined:
        return (
            "I grouped the sold order items by product, calculated each product's revenue as price times quantity, "
            "summed those values for the selected year, and picked the highest total."
        )
    if "category" in combined or "categories" in combined or "expense" in combined or "spent" in combined:
        return (
            "I checked your purchased order items, matched each product to its category, summed the spending per category, "
            "and sorted the categories from highest to lowest."
        )
    if "last purchased" in combined or "last purchase" in combined or "last order" in combined:
        return (
            "I sorted your eligible orders by purchase time from newest to oldest, selected the latest order, "
            "and listed the items and total from that order."
        )
    return None


def node_explanation(state: GraphState) -> GraphState:
    prev = _last_assistant_turn(state.get("history") or [])
    narrative = _methodology_from_context(state["question"], prev) or _EXPLANATION_FALLBACK
    if _LLM is not None and prev and narrative == _EXPLANATION_FALLBACK:
        try:
            response = _LLM.invoke([
                SystemMessage(content=_EXPLANATION_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Previous answer the user just received:\n{prev}\n\n"
                        f"User now asks: {state['question']}"
                    ),
                ),
            ])
            text = response.content if isinstance(response.content, str) else str(response.content)
            text = text.strip()
            if text:
                narrative = text
        except Exception:
            pass
    state["response"] = ChatResponse(status="ANSWER", narrative=narrative)
    return state


def node_out_of_scope(state: GraphState) -> GraphState:
    trigger = state.get("trigger", "")
    if trigger == "raw SQL on demand":
        narrative = (
            "I can't generate raw SQL on request. I do show the query I ran "
            "alongside each answer so you can see how I got the numbers — "
            "ask me a data question and the SQL preview comes with it."
        )
        guardrail_type = "SQL export request"
    else:
        narrative = (
            "That's outside what I can help with. I focus on your sales, "
            "products, orders, customers, shipments, and reviews."
        )
        guardrail_type = "Out of scope"
    state["response"] = ChatResponse(
        status="OUT_OF_SCOPE",
        narrative=narrative,
        guardrail=Guardrail(
            type=guardrail_type,
            trigger=trigger,
            action="No SQL generated",
        ),
    )
    return state


def node_sql(state: GraphState) -> GraphState:
    state["sql_preview"] = sql_agent.generate_sql(
        _LLM, state["question"], state["role"], state.get("history"),
    )
    return state


def node_sanitize(state: GraphState) -> GraphState:
    """Step 4: parse, validate, and re-scope the LLM-generated SQL.

    Defense-in-depth: even if the SQL agent ignored the role hint, the sanitizer
    re-injects the WHERE clause based on JWT-derived user_id / store_owner_id.
    """
    result = sanitize(
        state["sql_preview"],
        state["role"],
        state["user_id"],
        state.get("store_owner_id"),
        cross_store=state.get("cross_store", False) or state.get("public_catalog", False),
    )
    if not result.ok:
        state["sanitize_blocked"] = True
        state["sanitize_reason"] = result.reason or "Query rejected"
        state["sanitize_category"] = result.blocked_by or "policy_violation"
    else:
        state["sql_preview"] = result.sql or state["sql_preview"]
    return state


def node_sanitize_blocked(state: GraphState) -> GraphState:
    state["response"] = ChatResponse(
        status="BLOCKED",
        narrative=(
            "The generated SQL didn't pass the safety check, so I discarded it "
            "and didn't run anything against the database."
        ),
        guardrail=Guardrail(
            type="SQL Sanitizer",
            trigger=state.get("sanitize_category", "policy_violation"),
            action=state.get("sanitize_reason", "Query rejected"),
        ),
    )
    return state


def node_execute(state: GraphState) -> GraphState:
    state["execution"] = execute_sql(state["sql_preview"])
    return state


def node_execution_error(state: GraphState) -> GraphState:
    err = state["execution"].error or "Unknown database error"
    timed_out = "timed out" in err.lower() or "lost connection" in err.lower()
    state["response"] = ChatResponse(
        status="BLOCKED",
        narrative=(
            "I generated and sanitized the SQL, but the database query timed out "
            "before MySQL returned an answer. Try narrowing the date range or "
            "asking for a smaller ranking."
            if timed_out else
            "I generated and sanitized the SQL, but the database refused to run it. "
            "This usually means the query asked for something that doesn't exist "
            "(missing table, column, or join condition)."
        ),
        sql_preview=state["sql_preview"],
        guardrail=Guardrail(
            type="Execution error",
            trigger=err[:200],
            action="No data returned",
        ),
    )
    return state


_DATE_LIKE_NAMES = {"day", "date", "month", "week", "year", "created_at", "ordered_at", "updated_at", "shipped_at"}
_PIE_KEYWORDS = ("pie", "donut", "doughnut", "share", "split", "breakdown",
                 "categoric", "categorical")


def _detect_chart_type(columns: list[str], rows: list[dict], question: str = "") -> str:
    if len(rows) <= 1 or len(columns) < 2:
        return "NONE"
    first_col = columns[0].lower()
    if first_col in _DATE_LIKE_NAMES or "date" in first_col or first_col.endswith("_at"):
        return "LINE"
    q = (question or "").lower()
    if any(k in q for k in _PIE_KEYWORDS):
        return "PIE"
    return "BAR"


def _to_data_rows(columns: list[str], rows: list[dict]) -> list[DataRow]:
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


def _display_value(value) -> str:
    from decimal import Decimal
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _display_money(value) -> str:
    from decimal import Decimal
    if value is None:
        value = 0
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)):
        return f"{float(value):,.2f}"
    return str(value)


def _display_percent(value) -> str:
    from decimal import Decimal
    if value is None:
        return "0%"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)):
        return f"{float(value):,.2f}%"
    return f"{value}%"


_DENOM_TOTAL_RE = re.compile(r"^(?:last_(\d+)|all)_total$")


def _join_names(values: list[str]) -> str:
    cleaned = [str(v) for v in values if str(v).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _percent_scope_phrase(denom_key: str) -> str:
    """Translate the SQL alias chosen by the SQL agent into a human phrase
    used in the narrative ("your last 10 purchases" / "all your purchases")."""
    m = _DENOM_TOTAL_RE.match(denom_key)
    if not m:
        return denom_key.replace("_", " ")
    n = m.group(1)
    if n is None:
        return "all your purchases"
    return f"your last {n} purchases"


def _simple_row_answer(row: dict) -> Optional[str]:
    cols = {str(k).lower(): k for k in row.keys()}

    if "rival_store" in cols:
        store = row[cols["rival_store"]]
        return f"{store} is your closest rival."

    if "last_purchase" in cols and "percentage" in cols:
        # The SQL agent picks the denominator alias from the question
        # ("last_10_total", "last_20_total", "all_total", ...). Find it
        # generically so the narrative works for every variant.
        denom_key = next(
            (k for k in cols if k not in ("last_purchase", "percentage") and _DENOM_TOTAL_RE.match(k)),
            None,
        )
        if denom_key is not None:
            scope_phrase = _percent_scope_phrase(denom_key)
            return (
                "Your last purchase was "
                f"{_display_money(row[cols['last_purchase']])}. The total value of "
                f"{scope_phrase} was {_display_money(row[cols[denom_key]])}, so your last purchase made up "
                f"{_display_percent(row[cols['percentage']])} of that total."
            )

    if "store" in cols and "sales_count" in cols:
        store = row[cols["store"]]
        sales_raw = row[cols["sales_count"]]
        sales = _display_value(sales_raw)
        sale_word = "sale" if sales_raw == 1 else "sales"
        revenue = row.get(cols.get("revenue")) if "revenue" in cols else None
        if revenue is not None:
            return f"{store} made {sales} {sale_word} with {_display_money(revenue)} in revenue."
        return f"{store} made {sales} {sale_word}."

    if "store" in cols and ("product_count" in cols or "avg_rating" in cols):
        store = row[cols["store"]]
        rating = row.get(cols.get("avg_rating")) if "avg_rating" in cols else None
        if rating is not None:
            return f"It is {store}, with an average rating of {_display_value(rating)}."
        return f"It is {store}."

    if "store" in cols and "units" in cols:
        store = row[cols["store"]]
        return f"{store} sold the most items with {_display_value(row[cols['units']])} units sold."

    if "category" in cols and "spent" in cols:
        return (
            f"You bought from {row[cols['category']]} category the most this month, "
            f"with {_display_money(row[cols['spent']])} spent."
        )

    item_key = cols.get("product") or cols.get("item") or cols.get("name")
    if item_key and "revenue" in cols:
        return (
            f"{row[item_key]} made you more revenue than the others, "
            f"with {_display_money(row[cols['revenue']])} over the selected year."
        )

    if item_key and "units" in cols:
        return f"The most sold item is {row[item_key]} with {_display_value(row[cols['units']])} units sold."

    if len(row) == 1:
        key = next(iter(row.keys()))
        label = str(key).replace("_", " ")
        return f"{label.capitalize()}: {_display_value(row[key])}."

    return None


def _rivals_answer(exec_result: ExecutionResult) -> Optional[str]:
    cols = {c.lower(): c for c in exec_result.columns}
    store_key = cols.get("rival_store")
    if not store_key:
        return None
    if not exec_result.rows:
        return "You don't have any rivals."
    names_list = [str(r.get(store_key)) for r in exec_result.rows]
    names = _join_names(names_list)
    if len(names_list) == 1:
        return f"{names} is your rival."
    return f"{names} are your rivals."


def _store_categories_answer(exec_result: ExecutionResult, question: str) -> Optional[str]:
    cols = {c.lower(): c for c in exec_result.columns}
    if "store" not in cols or "category" not in cols:
        return None
    if not exec_result.rows:
        return "I couldn't find matching store categories."

    grouped: dict[str, list[str]] = {}
    for row in exec_result.rows:
        store = str(row.get(cols["store"]))
        category = str(row.get(cols["category"]))
        if store and category and category not in grouped.setdefault(store, []):
            grouped[store].append(category)

    q = (question or "").lower()
    parts = []
    for store, categories in grouped.items():
        joined = _join_names(categories)
        if "what else" in q:
            parts.append(f"{store} also sells {joined}.")
        elif "rival" in q or "competitor" in q:
            parts.append(f"Your rival {store}'s categories are {joined}.")
        else:
            parts.append(f"{store}'s categories are {joined}.")
    return " ".join(parts)


def _product_revenue_answer(exec_result: ExecutionResult) -> Optional[str]:
    cols = {c.lower(): c for c in exec_result.columns}
    product_key = cols.get("product") or cols.get("item") or cols.get("name")
    if not product_key or "revenue" not in cols or not exec_result.rows:
        return None
    top = exec_result.rows[0]
    return (
        f"{top[product_key]} made you more revenue than the others, "
        f"with {_display_money(top[cols['revenue']])} over the selected year."
    )


def _order_details_answer(exec_result: ExecutionResult) -> Optional[str]:
    if not exec_result.rows:
        return None
    cols = {c.lower(): c for c in exec_result.columns}
    required = {"order_id", "grand_total", "product"}
    if not required.issubset(cols):
        return None
    first = exec_result.rows[0]
    order_id = first.get(cols["order_id"])
    total = first.get(cols["grand_total"])
    status = first.get(cols["status"]) if "status" in cols else None
    status_part = f" ({status})" if status else ""
    products = []
    for row in exec_result.rows:
        name = row.get(cols["product"])
        qty = row.get(cols["quantity"]) if "quantity" in cols else None
        if qty in (None, 1):
            products.append(str(name))
        else:
            products.append(f"{name} x{_display_value(qty)}")
    product_text = _join_names(products)
    return (
        f"The last purchased item{'s' if exec_result.row_count != 1 else ''} "
        f"{'are' if exec_result.row_count != 1 else 'is'} {product_text}. "
        f"Order #{order_id}{status_part} totals {_display_money(total)}."
    )


def _format_narrative(state: GraphState, exec_result: ExecutionResult) -> str:
    scope = _scope_label(state["role"])
    if exec_result.row_count == 0:
        rival_empty = _rivals_answer(exec_result)
        if rival_empty:
            return rival_empty
        return f"No matching data in your {scope}."

    rivals = _rivals_answer(exec_result)
    if rivals:
        return rivals

    categories = _store_categories_answer(exec_result, state.get("question", ""))
    if categories:
        return categories

    product_revenue = _product_revenue_answer(exec_result)
    if product_revenue:
        return product_revenue

    if exec_result.row_count == 1:
        direct = _simple_row_answer(exec_result.rows[0])
        if direct:
            return direct
    order_details = _order_details_answer(exec_result)
    if order_details:
        return order_details
    if exec_result.row_count == 1 and len(exec_result.columns) == 1:
        col = exec_result.columns[0]
        val = exec_result.rows[0][col]
        return f"Result: {col} = {val}."
    suffix = " (showing first 100 rows)" if exec_result.truncated else ""
    return f"Here's the answer for your {scope} data — {exec_result.row_count} row(s){suffix}."


def _to_table(exec_result) -> TableData:
    rows = [
        [_jsonable(r.get(c)) for c in exec_result.columns]
        for r in exec_result.rows
    ]
    return TableData(columns=exec_result.columns, rows=rows)


def _jsonable(value):
    """Coerce DB values to JSON-friendly primitives."""
    from datetime import date, datetime
    from decimal import Decimal
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def node_finalize_answer(state: GraphState) -> GraphState:
    exec_result = state["execution"]
    chart_type = _detect_chart_type(exec_result.columns, exec_result.rows, state.get("question", ""))
    chart_rows = _to_data_rows(exec_result.columns, exec_result.rows) if chart_type != "NONE" else []
    table = _to_table(exec_result) if exec_result.rows else None
    analysis = analyze(state["question"], exec_result, chart_type)

    deterministic_narrative = _format_narrative(state, exec_result)
    deterministic_special = (
        _order_details_answer(exec_result)
        or _rivals_answer(exec_result)
        or _store_categories_answer(exec_result, state.get("question", ""))
        or _product_revenue_answer(exec_result)
    )
    if exec_result.row_count == 1 or deterministic_special:
        narrative = deterministic_narrative
    else:
        llm_narrative = summarize_with_analyst(_LLM, state["question"], exec_result)
        narrative = llm_narrative or deterministic_narrative

    state["response"] = ChatResponse(
        status="ANSWER",
        narrative=narrative,
        title=analysis.title,
        bullets=analysis.bullets or None,
        insight=analysis.insight,
        sql_preview=state["sql_preview"],
        rows=chart_rows or None,
        chart_type=chart_type if chart_rows else "NONE",
        table=table,
    )
    return state


def _route_after_guardrails(state: GraphState) -> str:
    cls = state["classification"]
    if cls == "prompt_injection":
        return "blocked"
    if cls == "sql_injection":
        return "sql_injection"
    if cls == "cross_tenant":
        return "cross_tenant"
    if cls == "greeting":
        return "greeting"
    if cls == "explanation":
        return "explanation"
    if cls == "out_of_scope":
        return "out_of_scope"
    return "sql"


def _route_after_sanitize(state: GraphState) -> str:
    return "blocked_sql" if state.get("sanitize_blocked") else "execute"


def _route_after_execute(state: GraphState) -> str:
    return "finalize_answer" if state["execution"].ok else "execution_error"


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("guardrails", node_guardrails)
    g.add_node("greeting", node_greeting)
    g.add_node("blocked", node_blocked)
    g.add_node("sql_injection", node_sql_injection)
    g.add_node("cross_tenant", node_cross_tenant)
    g.add_node("out_of_scope", node_out_of_scope)
    g.add_node("explanation", node_explanation)
    g.add_node("sql", node_sql)
    g.add_node("sanitize", node_sanitize)
    g.add_node("blocked_sql", node_sanitize_blocked)
    g.add_node("execute", node_execute)
    g.add_node("execution_error", node_execution_error)
    g.add_node("finalize_answer", node_finalize_answer)

    g.add_edge(START, "guardrails")
    g.add_conditional_edges("guardrails", _route_after_guardrails, {
        "greeting": "greeting",
        "blocked": "blocked",
        "sql_injection": "sql_injection",
        "cross_tenant": "cross_tenant",
        "out_of_scope": "out_of_scope",
        "explanation": "explanation",
        "sql": "sql",
    })
    g.add_edge("sql", "sanitize")
    g.add_conditional_edges("sanitize", _route_after_sanitize, {
        "execute": "execute",
        "blocked_sql": "blocked_sql",
    })
    g.add_conditional_edges("execute", _route_after_execute, {
        "finalize_answer": "finalize_answer",
        "execution_error": "execution_error",
    })
    g.add_edge("greeting", END)
    g.add_edge("blocked", END)
    g.add_edge("sql_injection", END)
    g.add_edge("cross_tenant", END)
    g.add_edge("out_of_scope", END)
    g.add_edge("explanation", END)
    g.add_edge("blocked_sql", END)
    g.add_edge("execution_error", END)
    g.add_edge("finalize_answer", END)

    return g.compile()


_GRAPH = build_graph()


def run(req: ChatRequest) -> ChatResponse:
    initial: GraphState = {
        "question": req.question,
        "role": req.role,
        "user_id": req.user_id,
        "store_owner_id": req.store_owner_id,
        "first_name": req.first_name,
        "history": req.history or [],
    }
    final = _GRAPH.invoke(initial)
    return final["response"]
