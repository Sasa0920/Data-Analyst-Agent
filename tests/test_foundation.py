import time
from collections.abc import Generator

import psycopg
import psycopg.errors
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env."""
    business_db_url: str
    app_db_url: str
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()

@pytest.fixture
def business_conn() -> Generator[psycopg.Connection, None, None]:
    """Yield an autocommit connection as agent_readonly to the pagila database."""
    with psycopg.connect(settings.business_db_url, autocommit=True) as conn:
        yield conn
@pytest.fixture
def app_conn() -> Generator[psycopg.Connection, None, None]:
    """Yield an autocommit connection as agent_app to the agent_app database."""
    with psycopg.connect(settings.app_db_url, autocommit=True) as conn:
        yield conn

def test_readonly_can_select(business_conn: psycopg.Connection) -> None:
    """Verify that agent_readonly can SELECT from core tables."""
    with business_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer;")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 999  # Pagila v4 has 999 customers


def test_insert_blocked(business_conn: psycopg.Connection) -> None:
    """Verify that INSERT is blocked with InsufficientPrivilege even if session is read-write."""
    business_conn.execute("SET default_transaction_read_only = off;")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        business_conn.execute(
            "INSERT INTO customer (store_id, first_name, last_name, email, address_id, active) "
            "VALUES (1, 'Test', 'User', 'test@example.com', 1, 1);"
        )


def test_update_blocked(business_conn: psycopg.Connection) -> None:
    """Verify that UPDATE is blocked with InsufficientPrivilege even if session is read-write."""
    business_conn.execute("SET default_transaction_read_only = off;")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        business_conn.execute("UPDATE customer SET first_name = 'Hacked';")


def test_delete_blocked(business_conn: psycopg.Connection) -> None:
    """Verify that DELETE is blocked with InsufficientPrivilege even if session is read-write."""
    business_conn.execute("SET default_transaction_read_only = off;")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        business_conn.execute("DELETE FROM customer;")


def test_create_table_blocked(business_conn: psycopg.Connection) -> None:
    """Verify that CREATE TABLE is blocked with InsufficientPrivilege even if session is read-write."""
    business_conn.execute("SET default_transaction_read_only = off;")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        business_conn.execute("CREATE TABLE test_table (id int);")


def test_drop_table_blocked(business_conn: psycopg.Connection) -> None:
    """Verify that DROP TABLE is blocked with InsufficientPrivilege even if session is read-write."""
    business_conn.execute("SET default_transaction_read_only = off;")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        business_conn.execute("DROP TABLE customer;")

def test_cannot_connect_to_app_db() -> None:
    """Verify that agent_readonly cannot connect to the agent_app database."""
    unauthorized_url = settings.business_db_url.rsplit("/", 1)[0] + "/agent_app"
    with pytest.raises(psycopg.OperationalError), psycopg.connect(unauthorized_url):
        pass
def test_statement_timeout(business_conn: psycopg.Connection) -> None:
    """Verify that a query running longer than statement_timeout (5s) is cancelled."""
    start = time.perf_counter()
    with pytest.raises(psycopg.errors.QueryCanceled):
        business_conn.execute("SELECT pg_sleep(10);")
    elapsed = time.perf_counter() - start
    # Should be cancelled right around 5 seconds, allowing 2 seconds of network/execution buffer
    assert 4.5 <= elapsed <= 7.0
# ── App role permission & isolation tests ────────────────────────────────────
def test_app_can_create_table(app_conn: psycopg.Connection) -> None:
    """Verify that agent_app can create and drop tables in its own database."""
    app_conn.execute("CREATE TABLE test_schema_check (id int);")
    app_conn.execute("DROP TABLE test_schema_check;")
def test_app_cannot_connect_to_pagila() -> None:
    """Verify that agent_app cannot connect to the pagila database."""
    unauthorized_url = settings.app_db_url.rsplit("/", 1)[0] + "/pagila"
    with pytest.raises(psycopg.OperationalError), psycopg.connect(unauthorized_url):
        pass