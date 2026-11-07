"""FastMCP server exposing database exploration and safe querying tools."""

import hashlib
import logging
from typing import Any

from fastmcp import FastMCP

from mcp_servers.database.db import execute_query, get_table_schema, get_tables

# Configure sanitized logger
logger = logging.getLogger("mcp_servers.database")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

mcp = FastMCP("Database Explorer")


@mcp.tool()
def list_tables() -> dict[str, Any]:
    """List all available tables and views in the public business database schema.

    Use this tool first to discover which tables exist before querying them.
    """
    result = get_tables()
    table_count = len(result.get("tables", [])) if result.get("ok") else 0
    logger.info(
        "Tool call 'list_tables' -> ok: %s, table_count: %d",
        result.get("ok"),
        table_count,
    )
    return result


@mcp.tool()
def describe_table(table_name: str) -> dict[str, Any]:
    """Retrieve column names, data types, nullability, primary keys, and foreign keys for a table.

    Use this tool before writing joins to see column names and foreign key relationships.

    Args:
        table_name: The exact name of the table to inspect (e.g. 'customer', 'film', 'rental').
    """
    result = get_table_schema(table_name)
    logger.info(
        "Tool call 'describe_table' for '%s' -> ok: %s",
        table_name,
        result.get("ok"),
    )
    return result


@mcp.tool()
def run_query(sql: str, max_rows: int | None = None) -> dict[str, Any]:
    """Safely execute a read-only SELECT SQL query over the business database.

    Rules:
    - Only single SELECT queries are permitted (no INSERT, UPDATE, DELETE, DROP, or modifying CTEs).
    - Queries are capped to a maximum safe row limit (default 100, max 500).
    - Results return columns, rows, row_count, and a truncated flag.

    Args:
        sql: The SQL SELECT query to run.
        max_rows: Optional row count limit (1 to 500). Defaults to 100.
    """
    # Hash SQL for audit logging without leaking sensitive query constants
    sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:10]
    sql_len = len(sql)

    result = execute_query(sql, max_rows=max_rows)

    logger.info(
        "Tool call 'run_query' [len=%d, hash=%s] -> ok: %s, rows: %d, truncated: %s, elapsed: %sms",
        sql_len,
        sql_hash,
        result.get("ok"),
        result.get("row_count", 0),
        result.get("truncated", False),
        result.get("elapsed_ms", 0),
    )
    return result


if __name__ == "__main__":
    mcp.run()