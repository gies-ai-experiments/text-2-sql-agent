# CLAUDE.md — Agent

This is the Claude-powered **purple agent** for the AgentBeats SQL Benchmark Tournament. It receives natural language questions + a database schema and returns valid SQL, competing against other LLM agents on a 7-dimension scoring rubric.

## Meta: Keeping This File Alive

**After every long working session, and periodically during development, update this file with:**
- Anything surprising discovered about the benchmark, scoring, or eval behaviour
- Prompt strategies or SQL patterns that improved scores
- Failure modes — query types the agent struggled with and why
- Architectural decisions made and the reasoning behind them
- Performance findings (latency, token usage, retry behaviour)
- Anything that would save time if rediscovered in a future session

Add findings under the **Learnings & Discoveries** section at the bottom. Keep entries concise — a few bullet points per topic is enough. This file is read at the start of every session, so stale or wrong entries are worse than no entry.

## Agent Interface (A2A Protocol)

The agent exposes an HTTP server. Task payload sent by the green evaluator:

```json
{
  "question": "Which customers placed orders over $1000?",
  "schema": { "tables": [...], "columns": [...] },
  "dialect": "sqlite",
  "task_id": "abc123"
}
```

Expected response:

```json
{
  "sql": "SELECT ...",
  "reasoning": "...",
  "task_id": "abc123"
}
```

Reference sample agent: `../eval/agentx_a2a/purple_agent/sql_generator_agent.py`

## Scoring Dimensions (what to optimise for)

| Dimension | Weight | Notes |
|-----------|--------|-------|
| Correctness | 35% | Results match expected output |
| Safety | 20% | No destructive ops, no injection |
| Efficiency | 15% | Query complexity, index usage |
| Completeness | 10% | All rows/columns returned |
| Semantic Accuracy | 10% | Correct interpretation of the question |
| Best Practices | 5% | Formatting, aliasing, readability |
| Plan Quality | 5% | Quality of reasoning/plan |

## Schemas to Handle

- **Basic**: `customers`, `orders` (simple relational)
- **Enterprise**: 19-table star schema data warehouse

Task difficulties: `easy`, `medium`, `hard`, `enterprise`

## Query Complexity Goals

This agent must handle real-world business queries, not just simple lookups. Examples of what it needs to get right:

- Multi-table JOINs with complex filter conditions
- Window functions (ranking, running totals, period-over-period comparisons)
- CTEs for multi-step logic (cohort analysis, funnel metrics, attribution)
- Aggregations with HAVING, GROUP BY ROLLUP/CUBE
- Subqueries and correlated subqueries
- Date/time arithmetic (last N days, fiscal quarters, week-over-week)
- Conditional aggregation (CASE WHEN inside SUM/COUNT)
- Self-joins for hierarchical or sequential data
- Set operations (UNION, INTERSECT, EXCEPT)

The benchmark includes `hard` and `enterprise` tiers specifically testing these patterns against a 19-table star schema. Scoring well requires correct SQL on these — not just easy single-table selects.

## Key Conventions

- Default dialect: **SQLite** (also supports PostgreSQL)
- LLM to use: `claude-opus-4-6` (Anthropic — most capable)
- Do not hallucinate table/column names — validate against the schema provided in the task
- Return clean SQL without trailing semicolon (the evaluator handles that)
- Extract SQL from LLM response: code block first, then SQL keyword heuristic

## Running Locally

```bash
# Install deps
pip install -r requirements.txt

# Start the A2A server
python server.py --port 8080

# Run the benchmark against this agent
cd ../eval
python run_benchmark.py --agent-url http://localhost:8080 --output results/
```

## Deployment

Built as a Docker image and published to GHCR:

```
ghcr.io/ashcastelinocs124/text-2-sql-agent-purple:latest
```

Configured in `../eval/scenario.toml` for the AgentBeats tournament.

---

## Learnings & Discoveries

> Updated periodically throughout the project. Most recent findings at the top.

### 2026-02-21 — Initial agent implementation

**Architecture:**
- `agent/__init__.py` centralizes `sys.path` setup for eval imports — don't add path manipulation in individual node files
- `ExecutorResult.execution` dict is an internal API — use `len(data)` for `rows_returned` instead of reaching into it
- Parallel Send() fan-out: `route_after_quality_gate` must match results by `current_task["id"]`, not `results[-1]`, since the accumulator merges across branches

**Eval integration bridge:**
- Self-eval path (no gold reference): `ComparisonResult(is_match=executor_result.success, match_score=1.0 if success else 0.0)` — mirrors execution success as comparison score
- `EnhancedScorer.score()` returns `EnhancedScore` — use `.to_dict()` for the retry_handler to inspect `dimensions`, `analysis.hallucinations`, `details`

**Prompt templates:**
- Use `{{` double braces for literal JSON braces in `.format()` templates (e.g., `planner.txt`) — easy to break if someone edits the prompt
- `schema_analyzer` does pure Python formatting, no LLM call needed — no prompt template required

