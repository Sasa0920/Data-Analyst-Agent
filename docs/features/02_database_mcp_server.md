# Feature 02: Database MCP Server: Specification

## Goal

A standalone MCP server that gives the agent three tools to explore and
query the business database, and carries the main safety layer. Nothing
the agent sends reaches the database without passing through this server.

## Tools

| Tool | Input | Returns |
|---|---|---|
| `list_tables` | none | Tables in the allowed schema, each with a short description of its role if known |
| `describe_table` | `table_name` | Columns (name, type, nullable), primary key, foreign keys |
| `run_query` | `sql`, optional `max_rows` | Columns, rows, row count, truncated flag, elapsed time |

Tool results are plain dictionaries. Failures are returned as structured
errors (not raised), so the agent can read them and correct itself later.

```json
{ "ok": true, "columns": ["store_id", "total"], "rows": [[1, "33489.47"]],
  "row_count": 1, "truncated": false, "elapsed_ms": 12 }

{ "ok": false, "error_type": "validation", "message": "Only SELECT statements are allowed" }
```

`error_type` is one of: `validation`, `timeout`, `database`, `internal`.

## Safety rules (this server's job)

1. **SQL validation before execution** (parsed with `sqlglot`, Postgres dialect):
   - exactly one statement
   - top-level statement must be a SELECT or a set operation (UNION and similar)
   - no write or DDL node anywhere in the parsed tree (this catches
     data-modifying CTEs)
   - no `SELECT ... INTO`, no locking reads (`FOR UPDATE`, `FOR SHARE`)
   - no references outside the allowed schema
   - no calls to blocked functions (for example `pg_sleep`, `pg_read_file`,
     `lo_import`, `lo_export`, `dblink`, `set_config`, `pg_terminate_backend`)
   - unparseable SQL is rejected
2. **Read-only database role:** connects only as `agent_readonly`.
3. **Read-only transaction** for every query.
4. **Limits:** row limit (default 100, maximum 500), statement timeout,
   and a maximum cell length so one huge text value cannot flood the result.
5. **Streaming fetch:** results are read in a bounded way, never fully
   loaded into memory before the row limit applies.
6. **Identifiers are never formatted into SQL strings.** Table names passed
   to `describe_table` are used only as query parameters.
7. **Errors are sanitized:** no connection strings, passwords, or stack
   traces in tool output.

## Logging

Log per call: tool name, SQL length and a hash, outcome, row count, elapsed
time. Do not log result rows or full SQL text at INFO level.

## Configuration (`.env`, via pydantic-settings)

`BUSINESS_DB_URL`, `DEFAULT_ROW_LIMIT`, `MAX_ROW_LIMIT`,
`STATEMENT_TIMEOUT_MS`, `MAX_CELL_CHARS`, `ALLOWED_SCHEMA`.

## Layout

```text
mcp_servers/database/
├── __init__.py
├── config.py       # settings
├── validator.py    # validate_sql(sql) -> result with reason
├── db.py           # connection and bounded execution
└── server.py       # FastMCP instance and thin tool functions
```

## Out of scope

- The agent that calls these tools (Feature 05)
- Schema selection and prompting (Feature 04)
- Allowlist-based function control and further hardening (Feature 11)

## Success criteria

- All three tools work through an in-memory FastMCP client and through the
  MCP Inspector over HTTP
- Every query in the red-team list is blocked, and each block is logged
- Validator unit tests cover the allowed list and the blocked list
- Bypassing the validator (calling the execution layer directly with a
  `DELETE`) is still blocked by the database role
- A deliberately expensive query is cancelled by the timeout
- Row limit and truncation flag are correct
- Tool outputs contain no secrets or stack traces
- `pytest -q` and `ruff check .` pass