# Remove Multi-Parallel Plan Type Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove `multi-parallel` as a valid plan type to fix the `InvalidUpdateError` that crashes the agent when the planner emits parallel tasks.

**Architecture:** The existing `multi-sequential` path already processes tasks one-by-one through the retry loop and feeds results to the summarizer — it IS the queue. We just need to stop the planner from ever choosing `multi-parallel`. Three files change: the prompt (LLM instruction), the JSON schema (structural enforcement), and the graph router (code-level guard).

**Tech Stack:** LangGraph, OpenAI structured output (JSON schema mode), pytest

---

### Task 1: Remove `multi-parallel` from the planner prompt

**Files:**
- Modify: `agent/prompts/planner.txt`

**Step 1: Update the prompt**

Replace the `plan_type` line and the `multi-parallel` rule. The file should become:

```
You are a query planning agent. Given a natural language question and a database schema, decide how to answer the question with SQL.

Your output must be a JSON object with this exact structure:
{{
  "plan_type": "single" | "multi-sequential",
  "tasks": [
    {{
      "id": "q1",
      "description": "Natural language description of what this query should return",
      "sql": "",
      "depends_on": []
    }}
  ],
  "confidence": 0.0 to 1.0
}}

Rules:
- Use "single" when one SQL query can answer the question fully.
- Use "multi-sequential" when the question requires multiple queries (whether or not they depend on each other). Each query runs in order; later queries can reference earlier results.
- Keep the number of tasks minimal — prefer one query when possible.
- Leave "sql" as an empty string — the query generator will fill it in.
- Set confidence based on how well the schema supports answering the question.

== SCHEMA ==
{schema_context}

== QUESTION ==
{question}
```

**Step 2: Verify the file looks correct**

Open `agent/prompts/planner.txt` and confirm:
- `"multi-parallel"` does not appear anywhere
- The rules section mentions only `"single"` and `"multi-sequential"`

**Step 3: Commit**

```bash
git add agent/prompts/planner.txt
git commit -m "fix: remove multi-parallel from planner prompt"
```

---

### Task 2: Remove `multi-parallel` from the OpenAI JSON schema enum

**Files:**
- Modify: `agent/nodes/planner.py` (lines 38–41)

**Step 1: Update the enum in `PLAN_JSON_SCHEMA`**

Find this block in `planner.py`:
```python
"plan_type": {
    "type": "string",
    "enum": ["single", "multi-sequential", "multi-parallel"],
},
```

Change it to:
```python
"plan_type": {
    "type": "string",
    "enum": ["single", "multi-sequential"],
},
```

This means even if the LLM tries to return `multi-parallel`, the structured output call will fail validation and fall through to the fallback plan (single-task).

**Step 2: Update the docstring on the `planner` function**

Find line 5 of the module docstring:
```
produces a structured QueryPlan (single, multi-sequential, or
multi-parallel) via OpenAI's JSON Schema structured output mode.
```

Change to:
```
produces a structured QueryPlan (single or multi-sequential)
via OpenAI's JSON Schema structured output mode.
```

**Step 3: Commit**

```bash
git add agent/nodes/planner.py
git commit -m "fix: remove multi-parallel from planner JSON schema enum"
```

---

### Task 3: Guard `route_after_planner` in the graph

**Files:**
- Modify: `agent/graph.py` (lines 81–105)

This is the safety net — even if somehow `multi-parallel` arrives (e.g. a test injects it manually), the graph should not crash or use Send().

**Step 1: Update `route_after_planner`**

Replace the current function:
```python
def route_after_planner(state: AgentState) -> list[Send] | str:
    plan_type = state["plan"]["plan_type"]

    if plan_type == "multi-parallel":
        sends = []
        for task in state["plan"]["tasks"]:
            sends.append(
                Send("query_generator", {
                    **state,
                    "current_task": task,
                    "retry_count": 0,
                    "retry_feedback": "",
                })
            )
        return sends

    return "set_first_task"
```

With:
```python
def route_after_planner(state: AgentState) -> str:
    """Route to set_first_task for all plan types.

    multi-parallel has been removed — all multi-query plans run
    sequentially through the existing set_first_task → check_remaining
    → set_next_task loop.
    """
    plan_type = state["plan"]["plan_type"]
    if plan_type not in ("single", "multi-sequential"):
        logger.warning("Unexpected plan_type %r — falling back to set_first_task", plan_type)
    return "set_first_task"
```

Also add `import logging` and `logger = logging.getLogger(__name__)` at the top of `graph.py` if not already present.

**Step 2: Update the conditional edges registration**

Find:
```python
graph.add_conditional_edges("planner", route_after_planner, [
    "set_first_task", "query_generator",
])
```

Change to:
```python
graph.add_conditional_edges("planner", route_after_planner, [
    "set_first_task",
])
```

`"query_generator"` was only there as the Send() target — it's no longer a valid destination from this router.

**Step 3: Commit**

```bash
git add agent/graph.py
git commit -m "fix: remove Send() fan-out from route_after_planner, always route to set_first_task"
```

---

### Task 4: Write a regression test

**Files:**
- Modify: `agent/tests/test_retry_handler.py` OR create `agent/tests/test_graph_routing.py`

**Step 1: Write the test**

Create `agent/tests/test_graph_routing.py`:

```python
"""Tests for graph routing functions."""

from agent.graph import route_after_planner
from agent.state import AgentState


def _make_state(plan_type: str, num_tasks: int = 2) -> AgentState:
    tasks = [
        {"id": f"q{i}", "description": f"task {i}", "sql": "", "depends_on": []}
        for i in range(1, num_tasks + 1)
    ]
    return {
        "question": "test question",
        "dialect": "sqlite",
        "db_path": "test.db",
        "schema_context": "",
        "plan": {"plan_type": plan_type, "tasks": tasks, "confidence": 0.9},
        "current_task": tasks[0],
        "queries": [],
        "query_results": [],
        "retry_count": 0,
        "retry_feedback": "",
        "final_answer": "",
    }


def test_single_routes_to_set_first_task():
    state = _make_state("single", num_tasks=1)
    result = route_after_planner(state)
    assert result == "set_first_task"


def test_multi_sequential_routes_to_set_first_task():
    state = _make_state("multi-sequential", num_tasks=2)
    result = route_after_planner(state)
    assert result == "set_first_task"


def test_unexpected_plan_type_falls_back_to_set_first_task():
    """multi-parallel or any unknown type must not trigger Send()."""
    state = _make_state("multi-parallel", num_tasks=2)
    result = route_after_planner(state)
    assert result == "set_first_task"
    assert not isinstance(result, list), "Send() fan-out must never be returned"
```

**Step 2: Run the tests**

```bash
cd /Users/ash/Desktop/text2sql
python -m pytest agent/tests/test_graph_routing.py -v
```

Expected output:
```
PASSED test_single_routes_to_set_first_task
PASSED test_multi_sequential_routes_to_set_first_task
PASSED test_unexpected_plan_type_falls_back_to_set_first_task
```

**Step 3: Commit**

```bash
git add agent/tests/test_graph_routing.py
git commit -m "test: add regression tests for route_after_planner never using Send()"
```

---

### Task 5: Smoke test the fix

**Step 1: Run the query that was crashing**

```bash
cd /Users/ash/Desktop/text2sql/agent
python -m agent.main --db test.db \
  "Identify customers in each segment whose average order value is above their segment's average and whose support ticket count is below their segment's average"
```

Expected: agent completes without `InvalidUpdateError`, prints a natural language answer.

**Step 2: Run with a simpler multi-query question to verify sequential works**

```bash
python -m agent.main --db test.db \
  "Compare sales by region AND by product category"
```

Expected: planner emits `multi-sequential`, both tasks run in order, summarizer merges them.

---

### Summary of Changes

| File | Change |
|---|---|
| `agent/prompts/planner.txt` | Remove `multi-parallel` from plan_type options and rules |
| `agent/nodes/planner.py` | Remove `"multi-parallel"` from JSON schema enum |
| `agent/graph.py` | Replace Send() fan-out with simple `return "set_first_task"` |
| `agent/tests/test_graph_routing.py` | New regression tests for routing |
