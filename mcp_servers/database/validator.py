"""SQL validator using sqlglot AST parsing to enforce SELECT-only safety."""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# Functions that could lead to DoS, file system access, or credential leaks
BLOCKED_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_write_file",
    "pg_write_binary_file",
    "lo_import",
    "lo_export",
    "dblink",
    "dblink_exec",
    "set_config",
    "pg_terminate_backend",
    "pg_cancel_backend",
}

# Node types that modify data or database structure
FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,  # e.g. COPY, VACUUM, SET
)


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating a SQL string."""

    is_valid: bool
    error_message: str | None = None


def validate_sql(sql: str, allowed_schema: str = "public") -> ValidationResult:
    """Parse and validate SQL using sqlglot AST analysis.

    Returns ValidationResult with is_valid=True if safe, or is_valid=False with a reason.
    """
    cleaned_sql = sql.strip().rstrip(";")
    if not cleaned_sql:
        return ValidationResult(is_valid=False, error_message="Empty SQL string provided.")

    try:
        # Parse into statements using Postgres dialect
        statements = sqlglot.parse(cleaned_sql, read="postgres")
    except SqlglotError as exc:
        return ValidationResult(is_valid=False, error_message=f"SQL parsing error: {exc}")

    if not statements or statements[0] is None:
        return ValidationResult(is_valid=False, error_message="Unparseable SQL statement.")

    # Rule 1: Exactly one statement allowed
    if len(statements) > 1:
        return ValidationResult(
            is_valid=False,
            error_message="Multiple SQL statements are not permitted.",
        )

    root = statements[0]

    # Rule 2: Top-level statement must be SELECT or a SetOperation (e.g. UNION)
    if not isinstance(root, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return ValidationResult(
            is_valid=False,
            error_message=f"Only SELECT queries are permitted (received: {root.key.upper()}).",
        )

    # Rule 3: No SELECT INTO (creates tables)
    if root.find(exp.Into):
        return ValidationResult(
            is_valid=False,
            error_message="SELECT INTO statements are not permitted.",
        )

    # Rule 4: No row-level locking (FOR UPDATE / FOR SHARE)
    if root.find(exp.Lock):
        return ValidationResult(
            is_valid=False,
            error_message="Row-level locking (e.g. FOR UPDATE) is not permitted.",
        )

    # Rule 5: Walk the entire AST for forbidden write/DDL nodes (catches modifying CTEs)
    for node in root.walk():
        if isinstance(node, FORBIDDEN_EXPRESSIONS):
            return ValidationResult(
                is_valid=False,
                error_message=f"Forbidden operation '{node.key.upper()}' detected inside query.",
            )

        # Rule 6: Check for blocked functions
        if isinstance(node, exp.Anonymous) and node.name.lower() in BLOCKED_FUNCTIONS:
            return ValidationResult(
                is_valid=False,
                error_message=f"Call to blocked function '{node.name}' is not permitted.",
            )

        # Rule 7: Enforce schema restriction if a schema qualifier is used
        if isinstance(node, exp.Table) and node.db and node.db.lower() != allowed_schema.lower():
            return ValidationResult(
                is_valid=False,
                error_message=f"Access outside schema '{allowed_schema}' (target: '{node.db}') is not permitted.",
            )

    return ValidationResult(is_valid=True)