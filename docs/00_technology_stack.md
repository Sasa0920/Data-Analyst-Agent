# Technology Stack

All direct dependencies are pinned in `requirements.txt` and installed at
the start. The "Added in feature" column shows when each one is
first used. 

| Layer | Technology | Role | 
|---|---|---|---|
| Language | Python 3.12.4 | Everything on the backend |
| Business DB | PostgreSQL 18 (Docker) | Data the agent queries |
| DB driver | psycopg 3 | Connect to PostgreSQL |
| Config | pydantic-settings | Typed settings from `.env` |
| Testing | pytest (+ pytest-asyncio later) | Unit and integration tests |
| Lint/format | ruff | Style and simple bug checks |
| Tool protocol | MCP via FastMCP | Build the 3 tool servers |
| SQL safety | sqlglot | Parse SQL, allow only SELECT |
| Evaluation | pandas, benchmark subset (Spider or BIRD) | Measure accuracy; verify format and license first |
| LLM | Gemini via langchain-google-genai | SQL generation and narration; model name comes from `.env`, check current availability |
| Agent | LangGraph | Orchestrate steps, retries, pauses |
| Observability | Langfuse (or OpenTelemetry) | Trace steps, tokens, latency |
| Vector search | Qdrant + FastEmbed (ONNX, no PyTorch) | Glossary retrieval |
| Charting | Chart data from MCP server; library chosen in feature 9 | Chart output |
| Persistence | langgraph-checkpoint-postgres, SQLAlchemy + Alembic | Checkpoints, run history |
| API | FastAPI + Uvicorn | REST and SSE |
| Frontend | React + Vite + TypeScript | UI |
| Infra | Docker Compose, Git, GitHub | Reproducible setup |

