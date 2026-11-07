"""Configuration settings for the Database MCP server."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseMCPSettings(BaseSettings):
    """Settings controlling database connection, query limits, and safety thresholds."""

    business_db_url: str
    default_row_limit: int = 100
    max_row_limit: int = 500
    statement_timeout_ms: int = 5000
    max_cell_chars: int = 500
    allowed_schema: str = "public"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


db_mcp_settings = DatabaseMCPSettings()