"""SQL Executor — runs sanitized SELECT statements against a read-only DB user.

The executor trusts the sanitizer (it never re-validates the SQL). Its job is
purely operational: open a short-lived connection, enforce a server-side query
timeout, cap the result set, and return the rows + column names.

If the DB user has SELECT-only grants (see setup-readonly-user.sql), even a
catastrophic sanitizer bug can't write to the database.
"""
from dataclasses import dataclass
from typing import Any, Optional

import pymysql
from pymysql.cursors import DictCursor

from .config import settings


MAX_RESULT_ROWS = 100


@dataclass
class ExecutionResult:
    ok: bool
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    error: Optional[str] = None


def execute(sql: str) -> ExecutionResult:
    conn = None
    try:
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            cursorclass=DictCursor,
            connect_timeout=5,
            read_timeout=settings.DB_QUERY_TIMEOUT_SECONDS,
            autocommit=True,
            charset="utf8mb4",
        )
        with conn.cursor() as cur:
            # MySQL 5.7.8+ honours MAX_EXECUTION_TIME (in ms) as a server-side
            # kill switch — defends against a complex query the read_timeout
            # alone would just abandon at the client.
            cur.execute(
                f"SET SESSION MAX_EXECUTION_TIME = {settings.DB_QUERY_TIMEOUT_SECONDS * 1000}"
            )
            cur.execute(sql)
            fetched = cur.fetchmany(MAX_RESULT_ROWS + 1)
            truncated = len(fetched) > MAX_RESULT_ROWS
            rows = fetched[:MAX_RESULT_ROWS]
            columns = [c[0] for c in cur.description] if cur.description else []
            return ExecutionResult(
                ok=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
            )
    except pymysql.MySQLError as e:
        code = e.args[0] if e.args else "?"
        msg = e.args[1] if len(e.args) > 1 else str(e)
        return ExecutionResult(
            ok=False,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            error=f"MySQL error {code}: {msg}",
        )
    except Exception as e:
        return ExecutionResult(
            ok=False,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
