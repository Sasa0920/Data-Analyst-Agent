# Problem Definition

## Problem

In most companies, the answers to everyday business questions sit in a
relational database, but only a small group of people can write SQL.
Everyone else (managers, marketing, sales, HR) must ask a data analyst.
Routine questions wait in a queue, decisions are delayed, and analysts
spend a large part of their time on simple, repetitive requests.

The obvious shortcut is to paste the question into an LLM and run whatever
SQL it returns. That fails in three ways:

1. **Silent wrong answers.** A bad join still returns a clean table, so a
   wrong answer looks exactly as confident as a right one.
2. **Unsafe execution.** Generated SQL could modify data, run expensive
   queries, or be hijacked by instructions hidden in text stored in the
   database (prompt injection).
3. **Unmeasured accuracy.** Nobody knows how often it is right, because
   nobody measured it.

## Users

- Business users who cannot write SQL and ask routine data questions
- Data analysts who want routine questions handled so they can focus on
  deeper work
- Reviewers of this project, who need to inspect and measure the system

## Existing solutions

Commercial and open-source "chat with your data" and text-to-SQL tools
exist. This project is an educational, engineering-focused implementation.
The goal is to understand and build the architecture and engineering
practices behind them (agent orchestration, tool protocols, safety,
evaluation), not to compete with those products.

## Project goal

Build an agent that answers plain-English questions over a relational
database **safely and verifiably**, and measure how well it works.

## AI solution

| Component | Purpose |
|---|---|
| LangGraph agent | Plans the steps, retries on failure, pauses to ask the user |
| 3 MCP servers (database, glossary, charts) | The agent's tools, built from scratch |
| Safety layer | SELECT-only validation, read-only database role, limits |
| Evaluation harness | Measures accuracy, cost, and latency against baselines |
| Observability | Traces every agent step and its cost |

## What this project is not

- Not a replacement for data analysts. It handles routine questions. It
  does not decide which metrics matter or explain why a number changed.
- Not allowed to write to the business database, ever.
- Not a general-purpose chatbot.

## Inputs, intermediate outputs, outputs

- **Inputs:** a plain-English question, the target database, business
  definitions, settings (model, max retries, row limit, timeout)
- **Intermediate:** relevant tables, candidate SQL, safety verdict, raw
  result rows, result-check verdict, a trace of every step
- **Outputs:** a plain-English answer, the SQL used, a result table and
  chart, a saved run record, and an evaluation report with an ablation table

## Success metrics

These are targets set before measuring. They are replaced by measured
results in `docs/04_evaluation_report.md`.

| Metric | Target |
|---|---|
| Execution accuracy | The full agent beats the single-shot baseline on the same questions; both numbers reported |
| Unsafe SQL executed on the business database | 0 on the attack test set |
| Answers that show the SQL used | 100% |
| Self-correction | Report how often a retry fixes a wrong first attempt |
| Cost and latency per question | Measured and reported, with a per-run budget |
| Honest failure | On unanswerable questions the agent says so instead of guessing |

## Risks

- LLM output varies between runs, so key tests are repeated and variation is reported
- Public benchmarks may use SQLite while the app uses PostgreSQL (verify, then convert or adapt)
- Gemini free-tier limits and model deprecations