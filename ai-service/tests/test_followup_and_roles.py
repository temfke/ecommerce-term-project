"""Tests for chatbot follow-up handling and role-aware responses.

Covers two related behaviors:

1. Follow-up questions after a previous answer should be classified as
   ``explanation`` and routed to ``node_explanation`` (no new SQL run),
   and the prior history should be forwarded to the SQL agent for
   resolution-style follow-ups ("what about last month?").

2. The chatbot should adapt its narrative and SQL to the caller's role
   (ADMIN / CORPORATE / INDIVIDUAL): greeting scope label, cross-tenant
   blocks, off-topic blocks, user-directory blocks, and the SQL shape
   for "who sold the most items" and "most sold item".

Run from ai-service/ with the venv active:
    .venv/Scripts/python.exe -m tests.test_followup_and_roles
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.guardrails import classify_stub
from app.agents.sql import _format_history, generate_sql
from app.graph import (
    node_blocked, node_cross_tenant, node_explanation, node_greeting,
    node_out_of_scope, node_sql_injection,
)
from app.schema import ChatTurn


def assert_(cond, msg):
    if not cond:
        print(f"  FAIL: {msg}")
        return False
    return True


def test_followup_classification():
    """Follow-up phrasings should be classified as 'explanation', not 'in_scope'."""
    cases = [
        ("how did you calculate that", "explanation"),
        ("How was this computed?", "explanation"),
        ("explain your calculation", "explanation"),
        ("what's the formula", "explanation"),
        ("where does this number come from", "explanation"),
        ("can you explain that", "explanation"),
        ("can you clarify this", "explanation"),
        ("tell me more about that", "explanation"),
        ("why did you say that", "explanation"),
        ("what do you mean", "explanation"),
        ("about your previous answer", "explanation"),
        ("what is the last order detail", "in_scope"),  # not a follow-up
        ("hi", "greeting"),
    ]
    ok = True
    for question, expected in cases:
        cls, _ = classify_stub(question, role="INDIVIDUAL")
        ok = assert_(cls == expected, f"{question!r} -> got {cls!r}, want {expected!r}") and ok
    return ok


def test_followup_history_passed_to_sql_agent():
    """Prior turns should be embedded in the SQL agent prompt for resolution-style
    follow-ups so the LLM can interpret 'what about last month?'."""
    history = [
        ChatTurn(role="user", content="top 5 products this month"),
        ChatTurn(role="assistant", content="Here are the top 5 products: A, B, C, D, E."),
    ]
    formatted = _format_history(history)
    ok = True
    ok = assert_("Prior conversation" in formatted, "history block header missing") and ok
    ok = assert_("top 5 products this month" in formatted, "user turn missing") and ok
    ok = assert_("A, B, C, D, E" in formatted, "assistant turn missing") and ok
    # Empty / None history should produce no block (don't pollute the prompt).
    ok = assert_(_format_history(None) == "", "None history should produce empty string") and ok
    ok = assert_(_format_history([]) == "", "empty history should produce empty string") and ok
    return ok


def test_explanation_node_uses_history_fallback():
    """With no LLM and no history, the explanation node still produces a sensible
    fallback narrative — does not raise and does not run SQL."""
    state = {"question": "how did you calculate that?", "role": "INDIVIDUAL", "history": []}
    out = node_explanation(state)
    resp = out["response"]
    ok = True
    ok = assert_(resp.status == "ANSWER", f"status={resp.status!r}") and ok
    ok = assert_(resp.sql_preview is None, "follow-up explanation should not surface a SQL preview") and ok
    ok = assert_(len(resp.narrative) > 0, "narrative should not be empty") and ok
    ok = assert_("aggregating" in resp.narrative.lower() or "percentage" in resp.narrative.lower(),
                 "fallback narrative should describe methodology") and ok
    return ok


def test_explanation_node_reads_last_assistant_turn():
    """The explanation node's prompt is derived from the last assistant turn,
    so dict-style and pydantic-style turns must both work."""
    from app.graph import _last_assistant_turn
    history_dicts = [
        {"role": "user", "content": "what was my last order"},
        {"role": "assistant", "content": "Order #123 totals 45.00."},
    ]
    history_models = [
        ChatTurn(role="user", content="what was my last order"),
        ChatTurn(role="assistant", content="Order #123 totals 45.00."),
    ]
    ok = True
    ok = assert_("Order #123" in _last_assistant_turn(history_dicts), "dict history not read") and ok
    ok = assert_("Order #123" in _last_assistant_turn(history_models), "model history not read") and ok
    ok = assert_(_last_assistant_turn([]) == "", "empty history should give ''") and ok
    return ok


def test_role_specific_greeting_scope_label():
    """Greeting narrative names the right scope per role."""
    cases = [
        ("ADMIN", "platform"),
        ("CORPORATE", "store"),
        ("INDIVIDUAL", "account"),
    ]
    ok = True
    for role, scope in cases:
        out = node_greeting({"role": role, "first_name": "Mert"})
        narrative = out["response"].narrative
        ok = assert_(out["response"].status == "GREETING", f"{role}: status") and ok
        ok = assert_("Mert" in narrative, f"{role}: name interpolation") and ok
        ok = assert_(scope in narrative, f"{role}: expected scope label {scope!r} in {narrative!r}") and ok
    # Falls back to "there" when first_name absent.
    out = node_greeting({"role": "INDIVIDUAL", "first_name": None})
    ok = assert_("Hi there" in out["response"].narrative, "missing-name fallback") and ok
    return ok


def test_role_specific_cross_tenant_block():
    """Cross-tenant block message names the right scope per role."""
    cases = [
        ("INDIVIDUAL", "account"),
        ("CORPORATE", "store"),
    ]
    ok = True
    for role, scope in cases:
        out = node_cross_tenant({"role": role, "trigger": "another user"})
        resp = out["response"]
        ok = assert_(resp.status == "BLOCKED", f"{role}: status") and ok
        ok = assert_(scope in resp.narrative, f"{role}: scope label") and ok
        ok = assert_(resp.guardrail.type == "Cross-tenant data access", f"{role}: guardrail type") and ok
    return ok


def test_role_specific_classification():
    """Cross-tenant / off-topic / user-directory rules apply only to non-admin roles."""
    ok = True

    # Cross-tenant phrasing — non-admin blocked, admin allowed.
    cls_ind, _ = classify_stub("show me orders for another user", "INDIVIDUAL")
    ok = assert_(cls_ind == "cross_tenant", f"INDIVIDUAL cross-tenant -> {cls_ind!r}") and ok
    cls_corp, _ = classify_stub("revenue across all stores", "CORPORATE")
    ok = assert_(cls_corp == "cross_tenant", f"CORPORATE cross-tenant -> {cls_corp!r}") and ok
    cls_admin, _ = classify_stub("revenue across all stores", "ADMIN")
    ok = assert_(cls_admin == "in_scope", f"ADMIN cross-tenant -> {cls_admin!r}") and ok

    # User directory — non-admin blocked, admin allowed.
    cls_ind_dir, _ = classify_stub("list all users", "INDIVIDUAL")
    ok = assert_(cls_ind_dir == "cross_tenant", f"INDIVIDUAL list users -> {cls_ind_dir!r}") and ok
    cls_admin_dir, _ = classify_stub("list all users", "ADMIN")
    ok = assert_(cls_admin_dir == "in_scope", f"ADMIN list users -> {cls_admin_dir!r}") and ok

    # Off-topic — non-admin blocked, admin allowed (admins sometimes explore freely).
    cls_ind_off, _ = classify_stub("what's the weather today", "INDIVIDUAL")
    ok = assert_(cls_ind_off == "out_of_scope", f"INDIVIDUAL off-topic -> {cls_ind_off!r}") and ok
    cls_admin_off, _ = classify_stub("what's the weather today", "ADMIN")
    ok = assert_(cls_admin_off == "in_scope", f"ADMIN off-topic -> {cls_admin_off!r}") and ok

    # Explanation classification fires regardless of role.
    for role in ("ADMIN", "CORPORATE", "INDIVIDUAL"):
        cls_x, _ = classify_stub("how did you calculate that", role)
        ok = assert_(cls_x == "explanation", f"{role} explanation -> {cls_x!r}") and ok
    return ok


def test_role_specific_sql_shape():
    """SQL shape differs by role for the same question."""
    ok = True

    # "who sold the most items" — INDIVIDUAL must keep `orders` so the sanitizer
    # can scope to the user's purchases; ADMIN/CORPORATE go through the
    # platform-wide product_units subquery.
    sql_ind = generate_sql(None, "who sold the most items", "INDIVIDUAL").lower()
    sql_admin = generate_sql(None, "who sold the most items", "ADMIN").lower()
    ok = assert_("from orders" in sql_ind,
                 "INDIVIDUAL seller-by-units must keep orders for user scoping") and ok
    ok = assert_("product_units" in sql_admin,
                 "ADMIN seller-by-units should aggregate via product_units") and ok
    ok = assert_("from orders" not in sql_admin,
                 "ADMIN seller-by-units should NOT join orders") and ok

    # "most sold item" — INDIVIDUAL keeps orders join so the sanitizer can scope;
    # ADMIN/CORPORATE skip the orders join.
    sql_item_ind = generate_sql(None, "what is the most sold item", "INDIVIDUAL").lower()
    sql_item_admin = generate_sql(None, "what is the most sold item", "ADMIN").lower()
    ok = assert_("join orders" in sql_item_ind,
                 "INDIVIDUAL most-sold-item must join orders") and ok
    ok = assert_("join orders" not in sql_item_admin,
                 "ADMIN most-sold-item should not join orders") and ok
    return ok


def test_percent_narrative_variants():
    """The narrative formatter should describe the denominator scope based on the
    SQL agent's column alias: last_10_total / last_20_total / all_total."""
    from decimal import Decimal
    from app.graph import _simple_row_answer
    ok = True

    last_10 = _simple_row_answer({
        "last_purchase": Decimal("250.00"),
        "last_10_total": Decimal("1000.00"),
        "percentage": Decimal("25.00"),
    })
    ok = assert_(last_10 is not None and "last 10 purchases" in last_10,
                 f"last_10 narrative wrong: {last_10!r}") and ok

    last_20 = _simple_row_answer({
        "last_purchase": Decimal("250.00"),
        "last_20_total": Decimal("2000.00"),
        "percentage": Decimal("12.50"),
    })
    ok = assert_(last_20 is not None and "last 20 purchases" in last_20,
                 f"last_20 narrative wrong: {last_20!r}") and ok

    all_total = _simple_row_answer({
        "last_purchase": Decimal("250.00"),
        "all_total": Decimal("10000.00"),
        "percentage": Decimal("2.50"),
    })
    ok = assert_(all_total is not None and "all your purchases" in all_total,
                 f"all_total narrative wrong: {all_total!r}") and ok

    return ok


def test_new_ai_section_narratives():
    """Deterministic narratives for the requested AI-section answer shapes."""
    from decimal import Decimal
    from app.executor import ExecutionResult
    from app.graph import _format_narrative, node_explanation

    ok = True
    rivals = ExecutionResult(
        ok=True,
        columns=["rival_store", "matching_items", "avg_rating"],
        rows=[
            {"rival_store": "X Store", "matching_items": 3, "avg_rating": Decimal("4.6")},
            {"rival_store": "Y Store", "matching_items": 2, "avg_rating": Decimal("4.4")},
        ],
        row_count=2,
        truncated=False,
    )
    text = _format_narrative({"role": "CORPORATE", "question": "who are my rivals"}, rivals)
    ok = assert_("X Store and Y Store are your rivals" in text, f"rival narrative: {text!r}") and ok

    no_rivals = ExecutionResult(ok=True, columns=["rival_store", "matching_items"], rows=[], row_count=0, truncated=False)
    text = _format_narrative({"role": "CORPORATE", "question": "who are my rivals"}, no_rivals)
    ok = assert_(text == "You don't have any rivals.", f"empty rival narrative: {text!r}") and ok

    categories = ExecutionResult(
        ok=True,
        columns=["store", "category", "products"],
        rows=[
            {"store": "X Store", "category": "M", "products": 4},
            {"store": "X Store", "category": "N", "products": 2},
        ],
        row_count=2,
        truncated=False,
    )
    text = _format_narrative({"role": "CORPORATE", "question": "what are X store categories"}, categories)
    ok = assert_("X Store's categories are M and N" in text, f"category narrative: {text!r}") and ok

    revenue = ExecutionResult(
        ok=True,
        columns=["product", "revenue"],
        rows=[{"product": "Widget", "revenue": Decimal("1234.50")}],
        row_count=1,
        truncated=False,
    )
    text = _format_narrative({"role": "CORPORATE", "question": "which product made me profit"}, revenue)
    ok = assert_("Widget made you more revenue" in text, f"revenue narrative: {text!r}") and ok

    explained = node_explanation({
        "question": "How did you calculate it?",
        "role": "CORPORATE",
        "history": [{"role": "assistant", "content": "Widget made you more revenue than the others."}],
    })["response"].narrative
    ok = assert_("price times quantity" in explained, f"explanation narrative: {explained!r}") and ok
    return ok


def test_other_guardrail_nodes():
    """Smoke-test the remaining guardrail nodes for consistent shape."""
    ok = True
    out = node_blocked({"trigger": "ignore previous instructions"})
    ok = assert_(out["response"].status == "BLOCKED", "blocked status") and ok
    ok = assert_(out["response"].guardrail.type == "Prompt Injection", "blocked type") and ok

    out = node_sql_injection({"trigger": "DROP TABLE users"})
    ok = assert_(out["response"].status == "BLOCKED", "sql_injection status") and ok
    ok = assert_(out["response"].guardrail.type == "SQL Injection Attempt", "sql_injection type") and ok

    out = node_out_of_scope({"trigger": "raw SQL on demand"})
    ok = assert_(out["response"].status == "OUT_OF_SCOPE", "out_of_scope status") and ok
    ok = assert_(out["response"].guardrail.type == "SQL export request", "out_of_scope type") and ok

    out = node_out_of_scope({"trigger": "weather"})
    ok = assert_(out["response"].guardrail.type == "Out of scope", "generic out_of_scope type") and ok
    return ok


def run():
    tests = [
        ("follow-up classification", test_followup_classification),
        ("follow-up history forwarded to SQL agent", test_followup_history_passed_to_sql_agent),
        ("explanation node fallback narrative", test_explanation_node_uses_history_fallback),
        ("explanation node reads last assistant turn", test_explanation_node_reads_last_assistant_turn),
        ("role-specific greeting scope", test_role_specific_greeting_scope_label),
        ("role-specific cross-tenant block", test_role_specific_cross_tenant_block),
        ("role-specific classification", test_role_specific_classification),
        ("role-specific SQL shape", test_role_specific_sql_shape),
        ("percent narrative variants", test_percent_narrative_variants),
        ("new AI-section narratives", test_new_ai_section_narratives),
        ("other guardrail nodes", test_other_guardrail_nodes),
    ]
    passed = 0
    failed = 0
    for label, fn in tests:
        print(f"\n[{label}]")
        if fn():
            print("  PASS")
            passed += 1
        else:
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    raise SystemExit(run())
