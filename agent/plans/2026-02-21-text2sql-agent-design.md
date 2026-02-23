# Text-to-SQL Multi-Agent System — Design

**Date:** 2026-02-21
**Status:** Approved
**LLM:** GPT-5
**Interface:** CLI
**Framework:** LangGraph

---

## Overview

A LangGraph-based multi-agent pipeline that accepts a natural language question, analyzes the database schema, plans one or more SQL queries, executes and evaluates each query against the existing eval infrastructure, and returns a natural language summary to the user.

---

## Graph Architecture

```
START
  │
  ▼
[schema_analyzer]      ← Introspects DB; reads from SchemaCache if warm
  │
  ▼
[planner]              ← Structured JSON output: plan type + query task list
  │
  ├── single query ────────────────────────────────────────────────────┐
  │                                                                     │
  └── multi-sequential ── loop over tasks ──► [query_generator]        │
      multi-parallel   ── Send() fan-out ──► [query_generator] × N     │
                                                     │                  │
                                               [executor_eval]          │
                                                     │                  │
                                       ┌─────────────┴──────────────┐  │
                                 score ≥ 0.70                score < 0.70
                                       │                            │
                                [summarizer] ◄─── max retries ─ [retry_handler]
                                       │                            │
                                      END              [query_generator] (with feedback)
```

**LangGraph features used:**
- `Send` API for parallel multi-query fan-out
- Conditional edges for the quality gate and retry routing
- Retry counter in state to cap loops

---

## State Schema

```python
class QueryTask(TypedDict):
    id: str
    description: str          # NL description of what this query should answer
    sql: str                  # Generated SQL (filled by query_generator)
    depends_on: list[str]     # IDs of tasks whose results feed this one (sequential)

class QueryResult(TypedDict):
    task_id: str
    data: list[dict]          # Rows returned
    rows_returned: int
    execution_time_ms: float
    score: float              # Overall eval score (0–1)
    eval_report: dict         # Full EnhancedScorer report
    status: str               # success | failed | error

class QueryPlan(TypedDict):
    plan_type: str            # "single" | "multi-sequential" | "multi-parallel"
    tasks: list[QueryTask]
    confidence: float         # 0–1, planner's confidence in the plan

class AgentState(TypedDict):
    question: str
    schema_context: str
    plan: QueryPlan
    queries: list[QueryTask]
    query_results: list[QueryResult]
    retry_count: int
    retry_feedback: str       # Categorized failure reason for query_generator
    final_answer: str
```

---

## Nodes

### 1. `schema_analyzer`

- Checks `SchemaCache` (TTL: 5 minutes, or invalidated by schema hash change)
- On cache miss: calls `SQLExecutor.refresh_schema()`, formats tables/columns/types/FK relationships into a compact prompt string
- Writes `schema_context` to state

### 2. `planner`

- Uses GPT-5 with **structured JSON output** (`response_format={"type": "json_schema", schema=QueryPlan}`)
- Guaranteed parseable — no text parsing required
- Decides: `single` / `multi-sequential` / `multi-parallel` based on question complexity
- Outputs `confidence` field; low confidence logged to CLI with a warning
- For `multi-sequential`: sets `depends_on` to encode ordering

### 3. `query_generator`

- Generates SQL for one `QueryTask`
- For sequential tasks: injects `query_results` of all `depends_on` tasks into the prompt as context (intermediate result injection)
- On retry: receives categorized `retry_feedback` in the prompt
- Uses GPT-5

### 4. `executor_eval`

- Calls `SQLExecutor.process_query(sql)` from `eval/src/agentx`
- Calls `EnhancedScorer.score(...)` for multi-dimensional scoring
- Writes `QueryResult` (including full eval report) to state
- No new eval code — reuses existing infrastructure directly

### 5. `retry_handler`

Categorizes the failure from the eval report and constructs targeted feedback:

| Failure type | Feedback sent to `query_generator` |
|---|---|
| Phantom table/column (hallucination) | "Table `X` does not exist. Available tables: `A`, `B`, `C`" |
| Safety violation | "Query attempted `DELETE`/`DROP`. Only `SELECT` is permitted." |
| Low correctness / empty result | "Query returned 0 rows. Expected non-empty result. Review WHERE clause." |
| Syntax error | Verbatim error from the DB adapter |

Routes:
- `retry_count < 3` → back to `query_generator` with feedback
- `retry_count >= 3` → `summarizer` (with whatever results exist, noting degraded confidence)

### 6. `summarizer`

- Receives all `QueryResult` objects + original `question`
- Uses GPT-5 to produce a clear natural language answer
- Includes inline caveats if any queries hit max retries or returned low scores
- Streams output to the CLI

---

## File Structure

```
text2sql/
├── eval/                              # Existing — untouched
│   └── ...
│
├── docs/
│   └── plans/
│       └── 2026-02-21-text2sql-agent-design.md
│
└── agent/
    ├── main.py                        # CLI: python agent/main.py "question here"
    ├── graph.py                       # StateGraph definition, compilation, Send() fan-out
    ├── state.py                       # AgentState, QueryPlan, QueryTask, QueryResult
    ├── config.py                      # SCORE_THRESHOLD=0.70, MAX_RETRIES=3, MODEL="gpt-5"
    │
    ├── nodes/
    │   ├── schema_analyzer.py
    │   ├── planner.py
    │   ├── query_generator.py
    │   ├── executor_eval.py           # Imports from eval/src/agentx
    │   ├── retry_handler.py
    │   └── summarizer.py
    │
    └── prompts/
        ├── schema_analyzer.txt
        ├── planner.txt
        ├── query_generator.txt
        └── summarizer.txt
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | LangGraph | Conditional edges + Send() API needed for multi-query routing |
| LLM | GPT-5 | User preference |
| Plan format | Structured JSON output | Guaranteed parseable; removes parsing bugs |
| Eval integration | Direct import from `eval/src/agentx` | No duplication; existing infrastructure becomes runtime quality gate |
| Retry strategy | Targeted per-failure-type feedback | Turns retry into a learning loop, not random regeneration |
| Multi-query context | Inject predecessor results into prompt | Enables chained reasoning across sequential queries |
| Schema caching | TTL + hash invalidation | Avoids DB roundtrip on every question |
| Score threshold | 0.70 (configurable in `config.py`) | Balances quality vs. retry overhead |
| Max retries | 3 per query | Prevents runaway loops; degrades gracefully |

---

## Dependencies

```
langgraph
openai
langsmith          # Optional but recommended for tracing
```

Plus existing `eval/` dependencies (already installed).

---

## CLI Usage

```bash
python agent/main.py "Which cities have the most customers?"
python agent/main.py "Show top 5 customers by revenue and their last order date"
python agent/main.py --dialect postgresql "Average order value by month in 2024"
```
