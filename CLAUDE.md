# CLAUDE.md — text2sql

Building a Claude-powered Text-to-SQL agent that competes on the AgentBeats platform.

## Short-Term Memory

**Always read `RECENT.md` at the start of a session** — it contains what was done recently, current state of the codebase, and next steps. Update it at the end of every session or after any significant chunk of work.

## Architecture Plan

Full design doc: **[`agent/plans/2026-02-21-text2sql-agent-design.md`](agent/plans/2026-02-21-text2sql-agent-design.md)**

Key decisions:
- **Framework:** LangGraph (`StateGraph` with conditional edges + `Send` API for parallel fan-out)
- **LLM:** GPT-5 for all agentic nodes
- **Agents:** `schema_analyzer` → `planner` → `query_generator` → `executor_eval` → `retry_handler` / `summarizer`
- **Eval integration:** `executor_eval` imports directly from `eval/src/agentx` — no duplication
- **Quality gate:** Score ≥ 0.70; max 3 retries with targeted per-failure-type feedback
- **Planner output:** Structured JSON (`QueryPlan`) — guaranteed parseable
- **Schema caching:** TTL + hash invalidation to avoid DB roundtrip on every question
- **Sequential multi-query:** Each query's results are injected into the next query's prompt

## Directory Structure

```
text2sql/
├── agent/          # The SQL-generating agent we are building → see agent/CLAUDE.md
│   └── plans/      # Architecture and implementation plans
├── eval/           # Evaluation framework (already built — do not break) → see eval/CLAUDE.md
│   ├── agentx_a2a/
│   │   ├── green_agent/    # Benchmark evaluator (scoring, hallucination detection)
│   │   └── purple_agent/   # Sample agent (reference implementation)
│   ├── tasks/              # Benchmark task definitions + gold SQL
│   ├── run_benchmark.py    # CLI to run benchmarks
│   └── scenario.toml       # AgentBeats tournament config
└── CLAUDE.md       # This file
```

## Architecture Debates (MANDATORY)

**Never agree to an architecture proposal without challenging it first.**

Whenever the user proposes a system design, tech stack, or architecture — during brainstorming or otherwise — invoke the `debate` skill before endorsing or building on it. Find what's good, what's bad, what assumptions are unstated, and what will break. Be honest.

This fires at step 3 of brainstorming ("Propose 2–3 approaches") and any time the user says things like "I'm thinking of using X", "let's go with Y architecture", or "my plan is...".

## Progress Reporting (MANDATORY during implementation)

During any multi-file implementation task, maintain `PROGRESS.md` at the project root.

**After completing each file or major step, append a line:**
```
[HH:MM] ✓ agent/nodes/query_generator.py — query generation with retry feedback
[HH:MM] ✗ agent/nodes/executor_eval.py — blocked: missing import path, needs fixing
[HH:MM] ~ agent/graph.py — in progress
```

Rules:
- Use `✓` for done, `✗` for blocked/failed, `~` for in progress
- One line per file or logical step — keep it terse
- Update it in real time, not just at the end
- This file is read by other sessions to track progress without interrupting yours

## Completed Work

### 2026-02-21 — Full LangGraph Agent Implementation
- Built complete 10-node LangGraph StateGraph: `schema_analyzer` → `planner` → `query_generator` → `executor_eval` → `retry_handler` → `summarizer` with helper nodes (`set_first_task`, `set_next_task`, `check_remaining`)
- Integrated with eval infrastructure via bridge pattern: `ExecutorResult` → `AgentResult` → `EnhancedScorer.score()` for runtime self-evaluation
- Three execution modes: single query, multi-sequential (chained with predecessor injection), multi-parallel (Send() fan-out)
- Quality gate retry loop: score < 0.70 triggers categorized retry feedback (exec error > hallucination > safety > empty results > generic), max 3 attempts
- Code review fixes applied: parallel-safe quality gate routing by task ID, centralized sys.path setup, planner error handling, consistent OpenAI client pattern

## How It Works

- **Green agent**: Sends NL questions + schema, scores the SQL returned using 7 dimensions
- **Purple agent**: Our agent — receives tasks, returns SQL via A2A REST protocol
- **AgentBeats**: Runs both agents in Docker, computes a leaderboard score

## Running the Eval

```bash
cd eval
pip install -r requirements.txt
python run_benchmark.py --output results/
python run_benchmark.py --schema enterprise --output results/
```
