"""Database connection and bounded query execution layer."""
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
import psycopg.errors
from psycopg.rows import dict_row

from mcp_servers.database.config import db_mcp_settings
from mcp_servers.database.validator import validate_sql


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """Provide a connection as agent_readonly with read-only session defaults."""
    with psycopg.connect(
        db_mcp_settings.business_db_url,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SET statement_timeout = '{db_mcp_settings.statement_timeout_ms}ms';"
            )
            cur.execute("SET default_transaction_read_only = on;")
        yield conn


def format_cell_value(val: Any, max_chars: int) -> Any:
    """Sanitize and truncate individual cell values to prevent memory flooding."""
    if val is None:
        return None
    val_str = str(val)
    if len(val_str) > max_chars:
        return val_str[:max_chars] + "... [truncated]"
    return val


def execute_query(sql: str, max_rows: int | None = None) -> dict[str, Any]:
    """Safely validate and execute a SELECT query with bounded streaming and timeouts."""
    # 1. SQL Validation (AST analysis)
    validation = validate_sql(sql, allowed_schema=db_mcp_settings.allowed_schema)
    if not validation.is_valid:
        return {
            "ok": False,
            "error_type": "validation",
            "message": validation.error_message or "Invalid SQL query.",
        }

    # 2. Determine row limit (bounded between 1 and max_row_limit)
    if max_rows is None or max_rows <= 0:
        limit = db_mcp_settings.default_row_limit
    else:
        limit = min(max_rows, db_mcp_settings.max_row_limit)

    start_time = time.perf_counter()

    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(sql)

            if cur.description is None:
                return {
                    "ok": True,
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                    "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 2),
                }

            columns = [desc[0] for desc in cur.description]

            # Fetch limit + 1 to detect if more rows exist without loading whole table
            raw_rows = cur.fetchmany(limit + 1)
            truncated = len(raw_rows) > limit
            selected_rows = raw_rows[:limit]

            # Format and bound cell contents
            formatted_rows = [
                [
                    format_cell_value(cell, db_mcp_settings.max_cell_chars)
                    for cell in row
                ]
                for row in selected_rows
            ]

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return {
                "ok": True,
                "columns": columns,
                "rows": formatted_rows,
                "row_count": len(formatted_rows),
                "truncated": truncated,
                "elapsed_ms": elapsed_ms,
            }

    except psycopg.errors.QueryCanceled:
        return {
            "ok": False,
            "error_type": "timeout",
            "message": f"Query exceeded statement timeout ({db_mcp_settings.statement_timeout_ms}ms) and was cancelled.",
        }
    except psycopg.errors.InsufficientPrivilege as exc:
        return {
            "ok": False,
            "error_type": "database",
            "message": f"Permission denied: {exc}",
        }
    except psycopg.Error as exc:
        return {
            "ok": False,
            "error_type": "database",
            "message": f"Database error: {exc}",
        }
    except Exception as exc: # noqa: BLE001
        return {
            "ok": False,
            "error_type": "internal",
            "message": f"Internal execution error: {exc}",
        }


def get_tables() -> dict[str, Any]:
    """List all base tables and views in the allowed schema."""
    query = """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = %s
        ORDER BY table_name;
    """
    try:
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (db_mcp_settings.allowed_schema,))
            tables = [
                {
                    "table_name": row["table_name"],
                    "table_type": row["table_type"],
                }
                for row in cur.fetchall()
            ]
        return {"ok": True, "tables": tables}
    except psycopg.Error as exc:
        return {
            "ok": False,
            "error_type": "database",
            "message": f"Failed to list tables: {exc}",
        }


def get_table_schema(table_name: str) -> dict[str, Any]:
    """Retrieve column details, primary keys, and foreign keys for a specific table."""
    columns_query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position;
    """
    pk_query = """
        SELECT a.attname AS column_name
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE i.indisprimary
          AND n.nspname = %s
          AND c.relname = %s;
    """
    fk_query = """
        SELECT
            a.attname AS column_name,
            cl.relname AS foreign_table_name,
            af.attname AS foreign_column_name
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        JOIN pg_class cl_src ON cl_src.oid = c.conrelid
        JOIN pg_class cl ON cl.oid = c.confrelid
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = ANY(c.confkey)
        WHERE c.contype = 'f'
          AND n.nspname = %s
          AND cl_src.relname = %s;
    """

    try:
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            schema = db_mcp_settings.allowed_schema

            # 1. Columns
            cur.execute(columns_query, (schema, table_name))
            columns = cur.fetchall()
            if not columns:
                return {
                    "ok": False,
                    "error_type": "database",
                    "message": f"Table '{table_name}' does not exist in schema '{schema}'.",
                }

            # 2. Primary Keys
            cur.execute(pk_query, (schema, table_name))
            primary_keys = [r["column_name"] for r in cur.fetchall()]

            # 3. Foreign Keys
            cur.execute(fk_query, (schema, table_name))
            foreign_keys = cur.fetchall()

        return {
            "ok": True,
            "table_name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
        }
    except psycopg.Error as exc:
        return {
            "ok": False,
            "error_type": "database",
            "message": f"Failed to describe table '{table_name}': {exc}",
        }