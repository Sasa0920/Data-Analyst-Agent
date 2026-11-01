# Feature 01: Project Foundation: Specification

## Goal

A safe, reproducible foundation: a business database loaded with realistic
data, a read-only role the agent will use, a separate app database, and
the project documentation. Everything else depends on this being safe.

## Steps

1. Create the repository, virtual environment, folder structure,
   `.gitignore`, and `.env.example`.
2. Write the docs: problem definition, system architecture, technology
   stack, and `AGENTS.md`.
3. Choose the dataset: **Pagila** (a DVD-rental business database for
   PostgreSQL, PostgreSQL license). Record its source, version, and license
   in `docs/data_dictionary.md`.
4. Add `docker-compose.yml` with PostgreSQL 18.
5. Load Pagila into the `pagila` database.
6. Create the roles and app database from `db/01_roles_and_app_db.sql`:
   - `agent_readonly`: SELECT only on `pagila`, 5 second statement timeout
   - `agent_app`: owner of the `agent_app` database, no access to `pagila`
7. Verify permissions manually with `psql` by trying to break them.
8. Write automated tests in `tests/test_foundation.py` (by hand).
9. Write `docs/data_dictionary.md`: main tables and columns in plain
   English, how they join, and 10 candidate business questions with the
   expected answer worked out by hand.
10. Commit.

## Configuration

`.env` (never committed; `.env.example` lists the names only):

- `POSTGRES_USER`, `POSTGRES_PASSWORD`: admin, used by setup scripts only
- `BUSINESS_DB_URL`: connects as `agent_readonly` to `pagila`
- `APP_DB_URL`: connects as `agent_app` to `agent_app`
- `GOOGLE_API_KEY`, `GEMINI_MODEL`: filled in when the LLM is first used

## Out of scope

- The Database MCP server (Feature 02)
- Evaluation harness and baseline (Feature 03)
- Any LLM calls

## Success criteria

- `docker compose up -d` starts PostgreSQL and the data persists after a restart
- `agent_readonly` can read core tables
- `agent_readonly` cannot INSERT, UPDATE, DELETE, CREATE, or DROP, even
  after turning off the session read-only setting
- `agent_readonly` cannot connect to `agent_app`
- A query running longer than the timeout is cancelled
- `agent_app` can create tables in `agent_app` and cannot connect to `pagila`
- All tests in `tests/test_foundation.py` pass
- Data dictionary lists 10 questions with hand-computed answers
- No secrets in git history