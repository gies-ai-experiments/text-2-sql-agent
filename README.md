# Text-to-SQL Agent

A production-grade natural language to SQL agent built with **LangGraph**, competing on the [AgentBeats](https://agentbeats.dev) platform. Ask a question in plain English — the agent decomposes it, writes SQL, executes it, self-evaluates across 7 dimensions, checks semantic relevance, and retries with targeted feedback if quality is low.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![A2A Compatible](https://img.shields.io/badge/A2A-compatible-green.svg)](https://agentbeats.dev)

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [System Architecture](#system-architecture)
3. [Node Reference](#node-reference)
4. [Quality Gate & Retry Loop](#quality-gate--retry-loop)
5. [Scoring Dimensions](#scoring-dimensions)
6. [Per-Query Relevance Checking](#per-query-relevance-checking)
7. [API Server & SSE Streaming](#api-server--sse-streaming)
8. [Frontend](#frontend)
9. [Evaluation Framework](#evaluation-framework)
10. [Setup & Running](#setup--running)
11. [Configuration](#configuration)
12. [Directory Structure](#directory-structure)

---

## What It Does

You type a question like:

> *"Which product categories generated the most revenue in Q4 2024, broken down by region?"*

The agent:
1. Inspects your database schema (cached — no redundant roundtrips)
2. Decides whether one query or multiple sequential queries are needed
3. Writes SQL for each sub-task (with predecessor results injected for multi-step questions)
4. Executes and scores each query across 7 dimensions
5. Independently checks whether each result is actually relevant to what you asked
6. Retries automatically with targeted, category-specific feedback if quality falls below threshold
7. Synthesizes all results into a final human-readable answer

---

## System Architecture

```
User Question
      │
      ▼
┌─────────────────────┐
│   schema_analyzer    │  Introspects DB via PRAGMA (no LLM)
│                      │  SHA-256 hash + TTL caching
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│       planner        │  GPT-5 produces a structured QueryPlan
│                      │  JSON Schema mode → guaranteed parseable
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    set_first_task    │  Points current_task → tasks[0], resets retries
└──────────┬──────────┘
           │
    ┌──────▼──────────────────────────────────────────────┐
    │                  Per-Task Loop                        │
    │                                                       │
    │  ┌──────────────────┐                                │
    │  │  query_generator  │  GPT-5 writes SQL              │
    │  │                  │  Injects retry_feedback if any  │
    │  └────────┬─────────┘                                │
    │           │                                           │
    │  ┌────────▼─────────┐                                │
    │  │   executor_eval   │  1. Execute SQL via SQLExecutor │
    │  │                  │  2. Score 7 dimensions          │
    │  │                  │  3. LLM relevance check         │
    │  │                  │  4. Blend: 85% eval + 15% rel  │
    │  └────────┬─────────┘                                │
    │           │                                           │
    │      ┌────┴─────────────────────┐                    │
    │      │    Quality Gate Router    │                    │
    │      │  score ≥ 0.70 ───────────┼──► check_remaining │
    │      │  score < 0.70            │                    │
    │      │  AND retries < 3 ────────┼──► retry_handler   │
    │      │  score < 0.70            │         │          │
    │      │  AND retries ≥ 3 ────────┼──► check_remaining │
    │      └──────────────────────────┘         │          │
    │                                    ┌──────▼─────────┐│
    │                                    │  retry_handler  ││
    │                                    │  (no LLM call) ││
    │                                    │  Categorizes   ││
    │                                    │  failure →     ││
    │                                    │  feedback str  ││
    │                                    └──────┬─────────┘│
    │                                           │           │
    │                     back to query_generator ──────────┘
    │                                                       │
    │  ┌──────────────────┐                                │
    │  │  check_remaining  │  Any tasks left?               │
    │  └────────┬─────────┘                                │
    │           │ yes → set_next_task → loop again          │
    └───────────┼───────────────────────────────────────── ┘
                │ no
                ▼
    ┌─────────────────────┐
    │      summarizer      │  GPT-5 synthesizes final answer
    └─────────────────────┘
```

---

## Node Reference

### `schema_analyzer`

**Role:** Database schema introspection — no LLM involved.

**How it works:**
- Opens the database using the eval framework's `SQLExecutor`
- Runs `PRAGMA table_info()` on every table to discover columns, types, primary keys, and foreign keys
- Formats the schema into compact, LLM-friendly text:
  ```
  Table: customers
    id (INTEGER, PK)
    name (TEXT)
    city_id (INTEGER, FK -> cities.id, nullable)
  ```
- **Caching:** Computes a SHA-256 hash of the full schema content (excluding `captured_at` for determinism). If the hash matches the cached value and the TTL hasn't expired (default 5 minutes), the cached formatted string is returned immediately — no DB roundtrip needed.

**Output:** `{"schema_context": "<formatted schema string>"}`

---

### `planner`

**Role:** Decides the query execution strategy.

**How it works:**
- Formats the user question and schema context into a prompt template (`prompts/planner.txt`)
- Calls GPT-5 with **strict JSON Schema mode** — the model's response is guaranteed to conform to the `QueryPlan` schema:

  ```json
  {
    "plan_type": "multi-sequential",
    "confidence": 0.88,
    "tasks": [
      {"id": "t1", "description": "Get total revenue by category", "sql": "", "depends_on": []},
      {"id": "t2", "description": "Break down t1 results by region", "sql": "", "depends_on": ["t1"]}
    ]
  }
  ```

- `plan_type` is either `"single"` (one SQL query) or `"multi-sequential"` (chained queries)
- Falls back to a single-task plan with `confidence: 0.0` if the LLM call fails — graph always continues
- Logs a warning if confidence < 0.5

**Output:** `{"plan": QueryPlan}`

---

### `set_first_task` / `set_next_task` / `check_remaining`

**Role:** Pure state manipulation — no LLM calls, no DB access.

- **`set_first_task`:** Sets `current_task` to `tasks[0]`, resets `retry_count` to 0 and `retry_feedback` to empty
- **`set_next_task`:** Compares completed task IDs against the plan's task list; advances `current_task` to the first task not yet in `query_results`
- **`check_remaining`:** Passthrough node used as a routing anchor. Its conditional edge (`route_after_remaining`) checks whether any tasks remain; if so, routes to `set_next_task`; otherwise routes to `summarizer`

---

### `query_generator`

**Role:** Writes the SQL for the current task.

**How it works:**
- Reads `current_task.description`, the full `schema_context`, and `retry_feedback` from state
- For multi-sequential plans: previous query results are injected into the prompt so the model can reference them (e.g., "Use the customer IDs from the previous step")
- Calls GPT-5 with the populated prompt template (`prompts/query_generator.txt`)
- Extracts the SQL from the response (code block first, then SQL keyword heuristic)
- Stores the SQL back into the current task

**Output:** Updates `current_task.sql` in state

---

### `executor_eval`

**Role:** The most integration-heavy node — runs SQL, scores it, checks relevance, returns a result.

**Five-stage pipeline:**

**Stage 1 — Execute:**
```python
executor = SQLExecutor(ExecutorConfig(dialect=dialect, db_path=db_path))
executor_result = executor.process_query(sql)
```
The eval framework's `SQLExecutor` handles connection management, error capture, and execution timing. Always closes the connection in a `finally` block.

**Stage 2 — Bridge to eval types:**
```python
agent_result = AgentResult.from_agent_output(executor_result.to_dict())
eval_exec_result = agent_result.to_execution_result()
```
Converts the agent's result format into the eval framework's internal `ExecutionResult` type.

**Stage 3 — Score:**
```python
comparison = ComparisonResult(is_match=executor_result.success, match_score=1.0 if success else 0.0)
score = EnhancedScorer().score(comparison, eval_exec_result, sql, dialect)
```
In tournament mode there's no gold SQL to compare against, so `ComparisonResult` reflects execution success. `EnhancedScorer` still evaluates all 7 dimensions.

**Stage 4 — Relevance check:**
```python
relevance_score, reasoning = check_query_relevance(question, task_description, sql, data)
```
An LLM judge evaluates whether the result actually helps answer the user's question. Defaults to `0.5` if the check fails.

**Stage 5 — Blend:**
```python
final_score = 0.85 * eval_score + 0.15 * relevance_score
```

**Output:** A `QueryResult` appended to the `query_results` accumulator channel.

> If *anything* goes wrong at any stage, the node returns a valid `QueryResult` with `status="error"` and `score=0.0` — the graph never crashes, and the quality gate decides whether to retry.

---

### `retry_handler`

**Role:** Categorize the failure, produce targeted feedback. No LLM call.

Inspects the most recent `QueryResult` and its `eval_report`. Walks a priority chain — first match wins:

| Priority | Category | Trigger | Feedback Produced |
|----------|----------|---------|-------------------|
| 1 | Execution error | `error` field non-empty in result or eval report | Exact DB error message |
| 2 | Hallucination | Phantom tables/columns in `eval_report.analysis.hallucinations` | Lists every non-existent object referenced |
| 3 | Safety violation | `dimensions.safety` < 0.5 | "SELECT only — no INSERT/UPDATE/DELETE/DROP" |
| 4 | Relevance | `eval_report.relevance.score` < 0.5 | Shows relevance score + LLM reasoning |
| 5 | Empty results | `rows_returned == 0` and `status == "success"` | Suggests reviewing WHERE/JOIN conditions |
| 6 | Generic | Catch-all | Score vs threshold + list of weak dimensions |

The `retry_feedback` string is injected verbatim into the `query_generator` prompt on the next attempt, so the model knows exactly what to fix.

**Output:** `{"retry_feedback": str, "retry_count": int + 1}`

---

### `summarizer`

**Role:** Synthesize all query results into a human-readable answer.

- Receives all `query_results` accumulated across all tasks
- Calls GPT-5 with a prompt that includes the original question, each task's description, and its result data
- Produces `final_answer` — a plain-English summary of what was found, including caveats if some queries hit max retries
- Stores `answer_relevance_score` in state for display

**Output:** `{"final_answer": str, "answer_relevance_score": float}`

---

## Quality Gate & Retry Loop

The routing function `route_after_quality_gate` runs after every `executor_eval`:

```python
def route_after_quality_gate(state):
    current_id = state["current_task"]["id"]
    result = [r for r in state["query_results"] if r["task_id"] == current_id][-1]
    score = result["score"]
    retries = state["retry_count"]

    if score >= SCORE_THRESHOLD:        # default 0.70
        return "check_remaining"
    elif retries < MAX_RETRIES:         # default 3
        return "retry_handler"
    else:
        return "check_remaining"        # give up, move on
```

**Important:** The router matches by `current_task["id"]`, not `results[-1]`. This ensures correctness if multiple tasks run (sequential plans append results to the same accumulator).

---

## Scoring Dimensions

`EnhancedScorer` evaluates every query on 7 weighted dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Correctness | 35% | Do the results match expected output? |
| Safety | 20% | No destructive ops (INSERT/UPDATE/DELETE/DROP/TRUNCATE) |
| Efficiency | 15% | Query complexity, unnecessary table scans |
| Completeness | 10% | All required rows and columns returned |
| Semantic Accuracy | 10% | Correct interpretation of the NL question |
| Best Practices | 5% | Formatting, aliasing, readability |
| Plan Quality | 5% | Quality of the model's reasoning trace |

Then the **relevance blend** is applied:

```
final_score = 0.85 × (weighted eval score) + 0.15 × (LLM relevance score)
```

The eval report stored in `QueryResult.eval_report` includes:
- `overall` — final blended score
- `overall_before_relevance` — score before relevance blend
- `dimensions` — per-dimension breakdown
- `relevance` — `{score, reasoning, weight}`
- `analysis` — hallucination detection results

---

## Per-Query Relevance Checking

Each executed query is independently judged by an LLM relevance checker (`nodes/query_relevance.py`):

```
question + task_description + generated SQL + result preview (≤20 rows)
                             ↓
                     LLM judge (GPT-5)
                             ↓
              relevance_score (0.0–1.0) + reasoning text
```

**Why separate from the main eval score?**
The 7-dimension scorer measures SQL quality (syntax, safety, efficiency). The relevance checker measures whether the *results themselves* answer the right question. A syntactically correct query can still return data that's completely irrelevant to what was asked.

**Integration with retry:**
If `relevance_score < 0.5`, the retry handler (priority 4) surfaces the reasoning to the query generator: *"Query result is not relevant to the original question (score: 0.31). Issue: The query returns all orders, but the question asked for orders placed by VIP customers only. Rewrite to directly address what was asked."*

---

## API Server & SSE Streaming

`agent/server.py` is a **FastAPI** backend that exposes the agent over HTTP with real-time streaming:

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/presets` | List available database presets |
| `GET` | `/schema/{preset_id}` | Table/column schema for a preset |
| `POST` | `/query` | Run the agent, stream results as SSE |
| `GET` | `/health` | Health check (model, threshold, config) |

### SSE Event Stream

`POST /query` accepts `{"question": "...", "preset": "enterprise"}` and returns a Server-Sent Events stream. Each line is a JSON object with an `event` field:

```json
{"event": "node",         "node": "schema_analyzer",  "status": "done"}
{"event": "node",         "node": "planner",           "status": "done"}
{"event": "plan",         "data": {"plan_type": "multi-sequential", "tasks": [...], "confidence": 0.91}}
{"event": "node",         "node": "query_generator",   "status": "done"}
{"event": "node",         "node": "executor_eval",     "status": "done"}
{"event": "query_result", "data": {"task_id": "t1", "sql": "SELECT ...", "score": 0.87, "rows_returned": 42, "data": [...], "relevance": {"score": 0.94, "reasoning": "..."}}}
{"event": "node",         "node": "summarizer",        "status": "done"}
{"event": "answer",       "data": {"final_answer": "Electronics generated $2.3M in Q4..."}}
{"event": "done",         "data": {"elapsed": 4.21}}
```

The LangGraph `graph.stream()` runs in a thread pool executor so it doesn't block the async event loop. Events are batched in memory and then streamed to the client.

**Start the server:**
```bash
uvicorn agent.server:app --reload --port 8000
# or
python -m agent.server
```

---

## Frontend

A **React + Vite** student interface in `frontend/` that connects to the API server:

- Type a natural language question
- Watch the graph execute live (SSE stream shows each node completing)
- See the generated SQL, query results, per-query scores and relevance, and the final synthesized answer
- Database schema sidebar for reference

**Start the frontend:**
```bash
cd frontend
npm install
npm run dev        # Vite dev server → http://localhost:5173
```

Make sure the backend is running on port 8000 first.

---

## Evaluation Framework

The `eval/` directory contains a **standardized SQL benchmark** used by the AgentBeats tournament:

- **7-dimensional scoring** (same scorer used by the agent for self-evaluation)
- **Hallucination detection:** Identifies phantom tables, columns, and invalid functions before execution
- **Error categorization:** Schema errors, analysis errors, SQL errors — with subcategories
- **Multi-dialect:** SQLite, DuckDB, PostgreSQL
- **Task library:** `easy`, `medium`, `hard`, and `enterprise` (19-table star schema) tasks with gold SQL

```bash
cd eval
pip install -r requirements.txt

# Run the full benchmark
python run_benchmark.py --output results/

# Enterprise schema only
python run_benchmark.py --schema enterprise --output results/

# Filter by difficulty
python run_benchmark.py --difficulty hard,enterprise --output results/
```

### A2A Protocol

The benchmark uses an Agent-to-Agent (A2A) REST protocol. The **green agent** (evaluator) sends:

```json
{
  "question": "Which customers placed orders over $1000?",
  "schema": {"tables": [...]},
  "dialect": "sqlite",
  "task_id": "abc123"
}
```

The **purple agent** (this repo) responds:

```json
{
  "sql": "SELECT c.name FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.total > 1000",
  "reasoning": "Joined customers and orders, filtered on total > 1000",
  "task_id": "abc123"
}
```

---

## Setup & Running

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the frontend)
- OpenAI API key with GPT-5 access

### Backend

```bash
# Install agent dependencies
pip install -r agent/requirements.txt

# Set your API key
export OPENAI_API_KEY=your_key_here

# Option 1: Run as a CLI (single question)
python -m agent.main "Which cities have the most customers?"

# Option 2: Start the API server (for the frontend)
uvicorn agent.server:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Benchmark

```bash
cd eval
pip install -r requirements.txt
python run_benchmark.py --output results/
```

---

## Configuration

All settings can be overridden via environment variables or `agent/.env` (loaded automatically, never committed):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `TEXT2SQL_MODEL` | `gpt-5` | LLM model name |
| `TEXT2SQL_SCORE_THRESHOLD` | `0.70` | Minimum score to pass without retry |
| `TEXT2SQL_MAX_RETRIES` | `3` | Maximum retry attempts per query |
| `TEXT2SQL_SCHEMA_CACHE_TTL` | `300` | Schema cache TTL in seconds |
| `TEXT2SQL_DIALECT` | `sqlite` | SQL dialect (`sqlite` or `postgresql`) |
| `TEXT2SQL_DB_PATH` | `:memory:` | Path to the SQLite database |

---

## Directory Structure

```
text2sql/
├── agent/
│   ├── config.py                  # Central config + .env loader
│   ├── state.py                   # TypedDict definitions: AgentState, QueryPlan, QueryResult
│   ├── graph.py                   # LangGraph StateGraph — nodes, edges, routing functions
│   ├── main.py                    # CLI entry point
│   ├── server.py                  # FastAPI server + SSE streaming
│   ├── nodes/
│   │   ├── schema_analyzer.py     # DB introspection + SHA-256/TTL schema caching
│   │   ├── planner.py             # Query strategy planning (GPT-5, JSON Schema mode)
│   │   ├── query_generator.py     # SQL generation with retry feedback injection
│   │   ├── executor_eval.py       # SQL execution + 7-dim scoring + relevance blend
│   │   ├── retry_handler.py       # Failure categorization → targeted feedback (no LLM)
│   │   ├── summarizer.py          # Final answer synthesis
│   │   ├── query_relevance.py     # Per-query LLM relevance judge
│   │   └── answer_judge.py        # Answer judge utilities (parser shared with query_relevance)
│   ├── prompts/                   # LLM prompt templates (.txt)
│   ├── tests/                     # pytest unit tests
│   └── requirements.txt
├── eval/
│   ├── agentx_a2a/
│   │   ├── green_agent/           # Benchmark evaluator (scoring, hallucination detection)
│   │   └── purple_agent/          # Reference sample agent
│   ├── tasks/                     # Benchmark task definitions + gold SQL
│   ├── run_benchmark.py           # CLI benchmark runner
│   └── scenario.toml              # AgentBeats tournament config
├── frontend/                      # React + Vite student UI
│   ├── src/
│   └── package.json
├── docs/                          # Additional documentation
├── CLAUDE.md                      # Project instructions for Claude Code
├── RECENT.md                      # Session memory and next steps
└── README.md                      # This file
```

---

## Key Design Decisions

**Why LangGraph?** The retry loop (query_generator → executor_eval → retry_handler → query_generator) and sequential task chaining are natural fits for a StateGraph with conditional edges. State is accumulated safely via LangGraph's reducer channels (`Annotated[list, operator.add]`).

**Why self-evaluation?** The agent imports directly from `eval/src/agentx` — the same `SQLExecutor` and `EnhancedScorer` used in the benchmark. No duplicated logic, and the agent's internal quality threshold mirrors the tournament scoring.

**Why no LLM in retry_handler?** The failure categories (syntax error, hallucination, safety, empty results) are deterministic from the eval report. Adding an LLM would be slower, costlier, and less predictable than a rule-based priority chain.

**Why blend relevance separately?** The 7-dimension scorer measures SQL quality mechanics. Relevance measures whether the *data* answers the question. These are orthogonal — a query can be syntactically perfect and completely off-topic, or slightly inefficient but spot-on.
