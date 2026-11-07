"""Tests for Database MCP Server: validator, execution engine, and FastMCP tools."""

import psycopg.errors
import pytest

from mcp_servers.database.db import (
    execute_query,
    format_cell_value,
    get_connection,
)
from mcp_servers.database.server import describe_table, list_tables, run_query
from mcp_servers.database.validator import validate_sql

# ── 1. Validator Tests (Red-Team Attacks & Allowed SQL) ──────────────────────


def test_valid_select() -> None:
    """Allow standard SELECT queries."""
    res = validate_sql("SELECT customer_id, first_name FROM customer LIMIT 10;")
    assert res.is_valid is True
    assert res.error_message is None


def test_valid_joins_and_unions() -> None:
    """Allow joins, aggregations, and UNION statements."""
    sql = """
        SELECT c.name, count(f.film_id)
        FROM category c
        JOIN film_category fc ON c.category_id = fc.category_id
        JOIN film f ON fc.film_id = f.film_id
        GROUP BY c.name
        UNION
        SELECT 'All', count(*) FROM film;
    """
    assert validate_sql(sql).is_valid is True


def test_valid_readonly_cte() -> None:
    """Allow read-only Common Table Expressions."""
    sql = "WITH top_cust AS (SELECT customer_id FROM customer LIMIT 5) SELECT * FROM top_cust;"
    assert validate_sql(sql).is_valid is True


@pytest.mark.parametrize(
    "bad_sql",
    [
        "INSERT INTO customer (store_id, first_name) VALUES (1, 'Eve');",
        "UPDATE customer SET first_name = 'Hacked';",
        "DELETE FROM customer WHERE customer_id = 1;",
        "DROP TABLE customer;",
        "CREATE TABLE hack (id int);",
        "ALTER TABLE customer ADD COLUMN hacked text;",
        "TRUNCATE TABLE customer;",
    ],
)
def test_block_ddl_and_dml(bad_sql: str) -> None:
    """Block all modifying DDL and DML operations."""
    res = validate_sql(bad_sql)
    assert res.is_valid is False
    assert "Only SELECT" in res.error_message or "Forbidden" in res.error_message


def test_block_modifying_cte() -> None:
    """Block data-modifying CTEs disguised as SELECTs."""
    sql = "WITH deleted AS (DELETE FROM customer RETURNING *) SELECT * FROM deleted;"
    res = validate_sql(sql)
    assert res.is_valid is False
    assert "DELETE" in res.error_message


def test_block_select_into() -> None:
    """Block SELECT INTO which creates tables."""
    sql = "SELECT * INTO stolen_customer FROM customer;"
    res = validate_sql(sql)
    assert res.is_valid is False
    assert "SELECT INTO" in res.error_message


def test_block_row_locking() -> None:
    """Block locking reads (FOR UPDATE / FOR SHARE)."""
    sql = "SELECT * FROM customer FOR UPDATE;"
    res = validate_sql(sql)
    assert res.is_valid is False
    assert "locking" in res.error_message.lower()


def test_block_multiple_statements() -> None:
    """Block chained statements using semicolons."""
    sql = "SELECT 1; DROP TABLE customer;"
    res = validate_sql(sql)
    assert res.is_valid is False
    assert "Multiple SQL statements" in res.error_message


@pytest.mark.parametrize(
    "func_name",
    ["pg_sleep(5)", "pg_read_file('/etc/passwd')", "set_config('a', 'b', false)"],
)
def test_block_dangerous_functions(func_name: str) -> None:
    """Block calls to DoS, file access, and config functions."""
    sql = f"SELECT {func_name};"
    res = validate_sql(sql)
    assert res.is_valid is False
    assert "blocked function" in res.error_message.lower()


def test_block_unallowed_schema() -> None:
    """Block queries targeting outside schemas."""
    sql = "SELECT * FROM information_schema.tables;"
    res = validate_sql(sql, allowed_schema="public")
    assert res.is_valid is False
    assert "Access outside schema" in res.error_message


# ── 2. Database Execution Engine Tests ───────────────────────────────────────


def test_execute_select_success() -> None:
    """Verify successful query execution returns structured dict."""
    res = execute_query("SELECT customer_id, email FROM customer LIMIT 5;")
    assert res["ok"] is True
    assert res["columns"] == ["customer_id", "email"]
    assert len(res["rows"]) == 5
    assert res["row_count"] == 5
    assert res["truncated"] is False
    assert res["elapsed_ms"] > 0


def test_row_limit_and_truncation() -> None:
    """Verify queries exceeding max_rows have truncated=True and bounded rows."""
    res = execute_query("SELECT * FROM payment;", max_rows=10)
    assert res["ok"] is True
    assert res["row_count"] == 10
    assert len(res["rows"]) == 10
    assert res["truncated"] is True


def test_max_cell_truncation() -> None:
    """Verify cell truncation helper bounds long strings."""
    short_val = format_cell_value("Hello World", max_chars=20)
    assert short_val == "Hello World"

    long_str = "A" * 600
    truncated_val = format_cell_value(long_str, max_chars=50)
    assert len(truncated_val) < 600
    assert truncated_val.endswith("... [truncated]")


def test_db_role_still_protects_even_if_validator_bypassed() -> None:
    """Defense-in-depth: Even if validator is bypassed, DB role blocks writes."""
    with get_connection() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SET default_transaction_read_only = off;")
        conn.execute("DELETE FROM customer;")


# ── 3. FastMCP Tool Function Tests ──────────────────────────────────────────


def test_tool_list_tables() -> None:
    """Verify list_tables tool returns core Pagila tables."""
    res = list_tables()
    assert res["ok"] is True
    table_names = [t["table_name"] for t in res["tables"]]
    assert "customer" in table_names
    assert "film" in table_names
    assert "rental" in table_names


def test_tool_describe_table() -> None:
    """Verify describe_table tool returns columns, PKs, and FKs."""
    res = describe_table("customer")
    assert res["ok"] is True
    assert res["table_name"] == "customer"

    col_names = [c["column_name"] for c in res["columns"]]
    assert "customer_id" in col_names
    assert "email" in col_names
    assert "customer_id" in res["primary_keys"]
    assert any(fk["column_name"] == "address_id" for fk in res["foreign_keys"])


def test_tool_describe_nonexistent_table() -> None:
    """Verify describing non-existent table returns clean error."""
    res = describe_table("ghost_table_xyz")
    assert res["ok"] is False
    assert res["error_type"] == "database"
    assert "does not exist" in res["message"]


def test_tool_run_query_blocked() -> None:
    """Verify run_query tool intercepts attacks with validation error."""
    res = run_query("DELETE FROM customer;")
    assert res["ok"] is False
    assert res["error_type"] == "validation"