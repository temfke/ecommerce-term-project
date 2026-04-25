"""Smoke tests for the SQL sanitizer.

Run from ai-service/ with the venv active:
    python -m pytest tests/test_sanitizer.py -v
or simply:
    python -m tests.test_sanitizer
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sanitizer import sanitize


def assert_(cond, msg):
    if not cond:
        print(f"  FAIL: {msg}")
        return False
    return True


def run():
    passed = 0
    failed = 0

    cases = [
        # (label, raw_sql, role, user_id, store_owner_id, expect_ok, must_contain_in_sql_or_reason)
        ("INDIVIDUAL: orders gets user_id filter injected",
         "SELECT id, grand_total FROM orders ORDER BY created_at DESC LIMIT 10",
         "INDIVIDUAL", 42, None, True, "user_id"),

        ("INDIVIDUAL: even if LLM filtered to user 99, sanitizer adds user_id = 42",
         "SELECT id FROM orders WHERE user_id = 99",
         "INDIVIDUAL", 42, None, True, "= 42"),

        ("CORPORATE: orders gets store subquery injected",
         "SELECT id, grand_total FROM orders LIMIT 10",
         "CORPORATE", 42, 7, True, "owner_id = 7"),

        ("ADMIN: no rewrite",
         "SELECT id FROM orders LIMIT 5",
         "ADMIN", 1, None, True, "FROM orders"),

        ("Block UPDATE",
         "UPDATE products SET unit_price = 0",
         "ADMIN", 1, None, False, "Only SELECT"),

        ("Block multi-statement",
         "SELECT 1; SELECT 2;",
         "ADMIN", 1, None, False, "Multiple statements"),

        ("Block SELECT *",
         "SELECT * FROM products",
         "ADMIN", 1, None, False, "SELECT *"),

        ("Block password_hash",
         "SELECT email, password_hash FROM users",
         "ADMIN", 1, None, False, "password_hash"),

        ("Block load_file",
         "SELECT LOAD_FILE('/etc/passwd')",
         "ADMIN", 1, None, False, "load_file"),

        ("LIMIT cap to 100",
         "SELECT id FROM products LIMIT 5000",
         "ADMIN", 1, None, True, "LIMIT 100"),

        ("Inject LIMIT when missing",
         "SELECT id FROM products",
         "ADMIN", 1, None, True, "LIMIT 100"),
    ]

    for label, sql, role, uid, sid, expect_ok, needle in cases:
        print(f"\n[{label}]")
        result = sanitize(sql, role, uid, sid)  # type: ignore
        ok_match = (result.ok == expect_ok)
        text = (result.sql or "") + (result.reason or "")
        contains = needle.lower() in text.lower()
        if ok_match and contains:
            print(f"  PASS  ({'ok' if result.ok else 'blocked: ' + (result.reason or '')})")
            if result.ok and result.sql:
                preview = result.sql.replace("\n", " ")[:120]
                print(f"        -> {preview}")
            passed += 1
        else:
            print(f"  FAIL  expect_ok={expect_ok} got ok={result.ok}")
            print(f"        sql={result.sql}")
            print(f"        reason={result.reason}")
            print(f"        wanted to find: {needle!r}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    raise SystemExit(run())
