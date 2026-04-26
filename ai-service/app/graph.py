"""LangGraph state machine wiring the agents from section 5.4 of the project spec.

In step 2 the graph stops after SQL generation — it returns the SQL preview to
the caller without executing it. Steps 4-6 will add: sanitizer, executor, analysis,
visualization.
"""
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from .agents import guardrails, sql as sql_agent
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
    classification: Classification
    trigger: str
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


def node_out_of_scope(state: GraphState) -> GraphState:
    state["response"] = ChatResponse(
        status="OUT_OF_SCOPE",
        narrative=(
            "That's outside what I can help with. I focus on your sales, "
            "products, orders, customers, shipments, and reviews."
        ),
        guardrail=Guardrail(
            type="Out of scope",
            trigger=state["trigger"],
            action="No SQL generated",
        ),
    )
    return state


def node_sql(state: GraphState) -> GraphState:
    state["sql_preview"] = sql_agent.generate_sql(_LLM, state["question"], state["role"])
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
    state["response"] = ChatResponse(
        status="BLOCKED",
        narrative=(
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


def _detect_chart_type(columns: list[str], rows: list[dict]) -> str:
    if len(rows) <= 1 or len(columns) < 2:
        return "NONE"
    first_col = columns[0].lower()
    if first_col in _DATE_LIKE_NAMES or "date" in first_col or first_col.endswith("_at"):
        return "LINE"
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


def _format_narrative(state: GraphState, exec_result: ExecutionResult) -> str:
    scope = _scope_label(state["role"])
    if exec_result.row_count == 0:
        return f"No matching data in your {scope}."
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
    chart_type = _detect_chart_type(exec_result.columns, exec_result.rows)
    chart_rows = _to_data_rows(exec_result.columns, exec_result.rows) if chart_type != "NONE" else []
    table = _to_table(exec_result) if exec_result.rows else None

    state["response"] = ChatResponse(
        status="ANSWER",
        narrative=_format_narrative(state, exec_result),
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
    if cls == "cross_tenant":
        return "cross_tenant"
    if cls == "greeting":
        return "greeting"
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
    g.add_node("cross_tenant", node_cross_tenant)
    g.add_node("out_of_scope", node_out_of_scope)
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
        "cross_tenant": "cross_tenant",
        "out_of_scope": "out_of_scope",
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
    g.add_edge("cross_tenant", END)
    g.add_edge("out_of_scope", END)
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
    }
    final = _GRAPH.invoke(initial)
    return final["response"]
