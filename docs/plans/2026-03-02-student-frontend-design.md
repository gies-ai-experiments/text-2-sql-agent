# Student Frontend — Design Doc

**Date:** 2026-03-02
**Status:** Approved

## Architecture

```
React SPA (Vite + TS)  ←— SSE —→  FastAPI Backend  ←→  LangGraph Agent
      :5173                          :8000              agent/graph.py
```

## Backend (`agent/server.py`)

FastAPI app with three endpoints:

- `POST /query` — accepts `{question, db_preset}`, streams SSE events as each graph node completes
- `GET /presets` — returns available DB presets (basic, enterprise)
- `GET /schema/{preset}` — returns schema for a preset (tables + columns)

SSE event format:
```json
{"node": "planner", "data": {"plan_type": "multi-sequential", "tasks": [...]}}
{"node": "executor_eval", "data": {"task_id": "q1", "score": 0.98, "sql": "...", "data": [...]}}
{"node": "summarizer", "data": {"final_answer": "..."}}
{"node": "done", "data": {"elapsed": 45.2}}
```

## Frontend (`frontend/`)

React 18 + Vite + TypeScript + Tailwind CSS.

### Components

| Component | Purpose |
|-----------|---------|
| `QueryInput` | Text area, preset selector, submit |
| `PipelineProgress` | Horizontal step indicator with live checkmarks |
| `PlanView` | Shows planner decomposition (task list) |
| `SqlResultCard` | SQL block + data table + score badge per sub-query |
| `AnswerPanel` | Final answer with relevance score |
| `SchemaBrowser` | Collapsible sidebar showing tables/columns |

### Layout

```
+---------------------------------------------------+
| [Schema Browser]  |  Query Input + Preset Dropdown |
|                   |  [Submit]                      |
|                   +--------------------------------+
|                   |  Pipeline Progress Bar         |
|                   +--------------------------------+
|                   |  Plan View                     |
|                   +--------------------------------+
|                   |  SQL Result Card(s)            |
|                   +--------------------------------+
|                   |  Answer Panel                  |
+---------------------------------------------------+
```

## Tech Stack

- React 18, Vite, TypeScript, Tailwind CSS
- FastAPI, sse-starlette, uvicorn
- No auth (student tool)

## DB Presets

- `basic` — simple customers + orders schema
- `enterprise` — 19-table star schema data warehouse (agent/test.db)
