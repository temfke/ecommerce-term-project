"""Smoke tests for deterministic SQL intent routing.

Run from ai-service/:
    python -m tests.test_sql_intents
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.sql import generate_sql


def assert_(cond, msg):
    if not cond:
        print(f"  FAIL: {msg}")
        return False
    return True


def run():
    cases = [
        (
            "seller by units",
            "who sold the most items",
            "ADMIN",
            ("stores", "product_units", "units", "limit 1"),
            ("join orders",),
        ),
        (
            "top N sellers by units",
            "top 5 stores by items sold",
            "ADMIN",
            ("stores", "product_units", "limit 5"),
            ("join orders",),
        ),
        (
            "single most-sold item",
            "what is the most sold item",
            "ADMIN",
            ("products", "order_items", "limit 1"),
            ("join orders",),
        ),
        (
            "top N most-sold products",
            "what are the top 5 most sold products",
            "ADMIN",
            ("products", "order_items", "limit 5"),
            ("join orders",),
        ),
        (
            "individual seller by units keeps orders for user scoping",
            "who sold the most items",
            "INDIVIDUAL",
            ("from orders", "stores", "limit 1"),
            tuple(),
        ),
        (
            "last purchase percentage (last 10 — historical default)",
            "What's the percentage of my last purchase in total value of my last 10 purchases?",
            "INDIVIDUAL",
            ("last_purchase", "last_10_total", "percentage", "limit 10"),
            ("products",),
        ),
        (
            "last purchase percentage (last 20 — explicit N)",
            "share of my last purchase in last 20 purchases",
            "INDIVIDUAL",
            ("last_purchase", "last_20_total", "percentage", "limit 20"),
            ("products", "last_10_total"),
        ),
        (
            "last purchase percentage (all — unbounded denominator)",
            "percentage of this purchase according the all purchases",
            "CORPORATE",
            ("last_purchase", "all_total", "percentage", "sum(grand_total)"),
            ("products", "last_10_total", "limit 10"),
        ),
        (
            "last purchase details",
            "last purchase details",
            "INDIVIDUAL",
            ("order_items", "products", "grand_total", "line_total", "limit 100"),
            tuple(),
        ),
        (
            "explicit order item details",
            "the items inside order with id 430967",
            "INDIVIDUAL",
            ("where o.id = 430967", "order_items", "products", "line_total"),
            tuple(),
        ),
        (
            "corporate: last product purchased from my store routes to order details",
            "what is the last product purchased from my store",
            "CORPORATE",
            ("order_items", "products", "grand_total", "line_total", "limit 100"),
            ("group by p.id",),
        ),
        (
            "individual: last item bought routes to order details",
            "what was the last item I bought",
            "INDIVIDUAL",
            ("order_items", "products", "grand_total", "line_total", "limit 100"),
            ("group by p.id",),
        ),
        (
            "corporate: most recent product sold at my store routes to order details",
            "most recent product sold at my store",
            "CORPORATE",
            ("order_items", "products", "line_total", "limit 100"),
            ("group by p.id",),
        ),
        (
            "corporate: rivals from top five sold products",
            "who are my rivals in my most sold 5 items",
            "CORPORATE",
            ("rival_store", "matching_items", "avg_rating", "order_items", "limit 5"),
            tuple(),
        ),
        (
            "named store rival by category",
            "Who is Aegean Outfitters store's rival for that kind of product?",
            "ADMIN",
            ("rival_store", "matching_categories", "source_s", "aegean outfitters"),
            tuple(),
        ),
        (
            "rival categories",
            "What are my rival store's categories?",
            "CORPORATE",
            ("store", "category", "owner_id <> :scoped_store_id"),
            tuple(),
        ),
        (
            "named store categories",
            "What else does Aegean Outfitters store sell?",
            "INDIVIDUAL",
            ("stores", "categories", "aegean outfitters"),
            tuple(),
        ),
        (
            "top revenue product over a year",
            "Which product made me profit more than others in a year?",
            "CORPORATE",
            ("product", "revenue", "interval 1 year", "limit 1"),
            tuple(),
        ),
        (
            "product revenue graph",
            "Show me the graph of each items revenue",
            "CORPORATE",
            ("product", "revenue", "interval 1 year", "limit 100"),
            tuple(),
        ),
        (
            "expense category this month",
            "Which category did I use the most for my expenses this month?",
            "INDIVIDUAL",
            ("category", "spent", "date_format", "limit 1"),
            tuple(),
        ),
        (
            "category visualization last purchases",
            "Categoric visualization of my last 10 purchase",
            "INDIVIDUAL",
            ("category", "spent", "recent_orders", "limit 10"),
            tuple(),
        ),
        (
            "best seller store in category",
            "Best seller store in electronics category?",
            "INDIVIDUAL",
            ("store", "product_count", "avg_rating", "electronics", "limit 1"),
            ("order_items",),
        ),
        # Phrasings that previously failed extraction — locked in here so they
        # don't regress the next time we touch the rival/category regexes.
        (
            "rivals of named store via 'rivals of X' phrasing",
            "rivals of Aegean Outfitters",
            "ADMIN",
            ("rival_store", "matching_categories", "source_s", "aegean outfitters"),
            tuple(),
        ),
        (
            "named rival categories — listing of that rival's catalog",
            "what are my rival Aegean Outfitters' categories",
            "CORPORATE",
            ("s.name as store", "c.name as category", "count(p.id) as products", "aegean outfitters"),
            ("rival_s.id", "matching_categories"),
        ),
        (
            "what else does X sell — bare name without 'store' tag",
            "what else does Aegean Outfitters sell",
            "INDIVIDUAL",
            ("aegean outfitters", "categories", "stores"),
            tuple(),
        ),
        (
            "expense category not misrouted as a named-store-categories question",
            "Which category did I use the most for my expenses this month?",
            "INDIVIDUAL",
            ("category", "spent", "date_format", "limit 1"),
            ("rival",),
        ),
        (
            "best seller store not misrouted via greedy capture",
            "Best seller store in electronics category?",
            "ADMIN",
            ("avg_rating", "limit 1"),
            ("rival",),
        ),
    ]

    passed = 0
    failed = 0
    for label, question, role, must_have, must_not_have in cases:
        print(f"\n[{label}]")
        sql = generate_sql(None, question, role).lower()
        ok = True
        for needle in must_have:
            ok = assert_(needle in sql, f"expected {needle!r} in SQL") and ok
        for needle in must_not_have:
            ok = assert_(needle not in sql, f"did not expect {needle!r} in SQL") and ok
        if ok:
            print("  PASS")
            passed += 1
        else:
            print(sql)
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    raise SystemExit(run())
