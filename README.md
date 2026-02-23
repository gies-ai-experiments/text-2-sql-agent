# Text-2-SQL Agent

**A LangGraph-powered text-to-SQL agent and a production-grade evaluation framework** for the [AgentBeats](https://agentbeats.dev) platform. Turn natural language questions into correct, efficient SQL — and measure how well any agent does it with 7-dimensional scoring and hallucination detection.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![A2A Compatible](https://img.shields.io/badge/A2A-compatible-green.svg)](https://agentbeats.dev)

---

## What’s in this repo

| Part | Purpose |
|------|--------|
| **`agent/`** | The **purple agent**: multi-node LangGraph pipeline that answers NL questions with SQL, uses the eval stack as a runtime quality gate, and retries with targeted feedback when scores are low. |
| **`eval/`** | The **benchmark framework**: 7-dimension scoring, pre-execution hallucination detection, multi-dialect support (SQLite, DuckDB, PostgreSQL), and A2A protocol for running reproducible tournaments. |

The agent imports directly from `eval/src/agentx` — one codebase, no duplicated scoring logic.

---

## The Agent (`agent/`)

A **LangGraph** pipeline that:

1. **Schema** — Introspects the DB (with caching) and builds a compact schema context.
2. **Plan** — Uses an LLM to produce a structured **query plan** (single, multi-sequential, or multi-parallel) as JSON.
3. **Generate** — Generates SQL per task; for sequential plans, injects prior query results into the prompt.
4. **Execute & score** — Runs SQL through the eval stack (`SQLExecutor` + `EnhancedScorer`) for execution and 7-dimension scoring.
5. **Quality gate** — If score ≥ 0.70, proceeds; otherwise **retry** with categorized feedback (hallucination, safety, empty result, syntax, etc.), up to 3 attempts.
6. **Summarize** — Produces a natural-language answer (and surfaces caveats if some queries hit max retries).

**Features:**

- **Single and multi-query**: One question can be decomposed into several SQL tasks (sequential or parallel via LangGraph `Send`).
- **Targeted retries**: Failures are classified and turned into concrete prompts for the generator (e.g. “Table X does not exist. Available: A, B, C”).
- **Config**: Score threshold (default 0.70), max retries (3), model (e.g. GPT-5), dialect, DB path — see `agent/config.py` and optional `agent/.env`.

### Run the agent (CLI)

```bash
cd agent
pip install -r requirements.txt
# Optional: copy .env.example to .env and set OPENAI_API_KEY

python -m agent.main "Which cities have the most customers?"
python -m agent.main --dialect sqlite --db-path :memory: "Top 5 customers by revenue"
python -m agent.main --verbose "Show total orders per month in 2024"
```

From repo root you can run:

```bash
python -m agent.main "Your question here"
```

---

## The Eval Framework (`eval/`)

A **standardized SQL benchmark** that goes beyond pass/fail:

- **7-dimensional scoring**: Correctness (35%), Safety (20%), Efficiency (15%), Completeness (10%), Semantic Accuracy (10%), Best Practices (5%), Plan Quality (5%).
- **Hallucination detection**: Identifies phantom tables, columns, and invalid functions *before* execution.
- **Error categorization**: Schema errors, analysis errors, SQL errors — with subcategories for debugging.
- **Multi-dialect**: SQLite, DuckDB, PostgreSQL; tasks and gold queries for basic and **enterprise** (19-table star schema) benchmarks.
- **A2A protocol**: Green agent (evaluator) sends tasks; purple agents (SQL generators) return SQL; framework scores and ranks.

Full docs, API reference, and Docker setup: **[`eval/README.md`](eval/README.md)**.

### Run a benchmark

```bash
cd eval
pip install -r requirements.txt
cp .env.example .env   # optional: add API keys if using purple agents

# Default (basic schema, all difficulties)
python run_benchmark.py --output results/

# Enterprise schema
python run_benchmark.py --schema enterprise --output results/

# Filter by difficulty
python run_benchmark.py --difficulty easy,medium,hard --output results/
```

---

## Quick start (both)

```bash
# 1. Agent: answer a question with SQL (uses in-memory SQLite by default)
cd agent && pip install -r requirements.txt
python -m agent.main "How many customers are in each region?"

# 2. Eval: run the benchmark and write reports to results/
cd eval && pip install -r requirements.txt
python run_benchmark.py --output results/
```

---

## Project structure

```
├── agent/                    # LangGraph text-to-SQL agent
│   ├── main.py               # CLI entrypoint
│   ├── graph.py              # StateGraph, quality gate, Send() fan-out
│   ├── state.py              # AgentState, QueryPlan, QueryTask, QueryResult
│   ├── config.py             # Thresholds, model, dialect
│   ├── nodes/                # schema_analyzer, planner, query_generator,
│   │                         # executor_eval, retry_handler, summarizer
│   ├── prompts/              # Planner, query generator, summarizer
│   ├── plans/                # Design docs (e.g. text2sql-agent-design.md)
│   └── requirements.txt
│
├── eval/                     # Benchmark & scoring framework
│   ├── run_benchmark.py      # CLI to run benchmarks
│   ├── src/agentx/            # Executor, validation, scoring, dialects
│   ├── evaluation/           # EnhancedScorer, comparators, presets
│   ├── agentx_a2a/           # Green/purple agents, A2A server
│   ├── tasks/                # Schemas, gold_queries (basic + enterprise)
│   ├── scenario.toml         # AgentBeats tournament config
│   └── README.md             # Full eval docs
│
├── CLAUDE.md                 # Project overview and conventions
├── RECENT.md                 # Session memory and next steps
└── README.md                 # This file
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [CLAUDE.md](CLAUDE.md) | Project overview, architecture summary, directory map |
| [RECENT.md](RECENT.md) | Recent work and next steps |
| [agent/CLAUDE.md](agent/CLAUDE.md) | Agent interface (A2A), scoring dimensions, conventions |
| [agent/plans/2026-02-21-text2sql-agent-design.md](agent/plans/2026-02-21-text2sql-agent-design.md) | LangGraph design: state, nodes, quality gate, retries |
| [eval/README.md](eval/README.md) | Full benchmark docs: scoring, Docker, API, reproducibility |

---

## Requirements

- **Python 3.10+**
- **Agent**: `langgraph`, `openai` (and env `OPENAI_API_KEY` for the default model)
- **Eval**: see `eval/requirements.txt`; supports SQLite (zero config), DuckDB, PostgreSQL

No env files or secrets are committed; use `.env.example` in `agent/` and `eval/` as templates.
