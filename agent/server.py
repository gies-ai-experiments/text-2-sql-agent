"""FastAPI backend server for the text2sql student frontend.

Endpoints:
    GET  /presets          - List available database presets
    GET  /schema/{preset}  - Return table/column schema for a preset
    POST /query            - Stream agent execution as SSE events

Usage:
    uvicorn agent.server:app --reload --port 8000
    python -m agent.server                          # runs on 0.0.0.0:8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue as thread_queue
import sqlite3
import time
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.config import (
    MODEL,
    SCORE_THRESHOLD,
    MAX_RETRIES,
    DEFAULT_DIALECT,
)
from agent.graph import build_graph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Preset registry
# ---------------------------------------------------------------------------

_AGENT_DIR = Path(__file__).resolve().parent

PRESETS: dict[str, dict] = {
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise Data Warehouse",
        "description": "19-table star schema with customers, orders, products, and more",
        "db_path": str(_AGENT_DIR / "test.db"),
    },
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PresetOut(BaseModel):
    id: str
    name: str
    description: str


class ColumnOut(BaseModel):
    name: str
    type: str


class TableOut(BaseModel):
    name: str
    columns: list[ColumnOut]


class SchemaOut(BaseModel):
    tables: list[TableOut]


class QueryIn(BaseModel):
    question: str
    preset: str = "enterprise"


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Text2SQL Agent API",
    description="Backend for the text2sql student frontend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db_path(preset_id: str) -> str:
    """Resolve the database file path for a preset, raising 404 if unknown."""
    preset = PRESETS.get(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Unknown preset: {preset_id}")
    db_path = preset["db_path"]
    if not Path(db_path).exists():
        raise HTTPException(
            status_code=503,
            detail=f"Database file not found for preset '{preset_id}'",
        )
    return db_path


def _read_schema(db_path: str) -> list[TableOut]:
    """Read all tables and their columns from a SQLite database using pragma."""
    tables: list[TableOut] = []
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Get all user tables (exclude sqlite internals)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        table_names = [row[0] for row in cursor.fetchall()]

        for table_name in table_names:
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = [
                ColumnOut(name=row[1], type=row[2] or "TEXT")
                for row in cursor.fetchall()
            ]
            tables.append(TableOut(name=table_name, columns=columns))
    finally:
        conn.close()

    return tables


def _build_initial_state(question: str, db_path: str) -> dict:
    """Construct the full AgentState dict required by the LangGraph agent."""
    return {
        "question": question,
        "dialect": "sqlite",
        "db_path": db_path,
        "schema_context": "",
        "plan": {"plan_type": "single", "tasks": [], "confidence": 0.0},
        "current_task": {"id": "", "description": "", "sql": "", "depends_on": []},
        "queries": [],
        "query_results": [],
        "retry_count": 0,
        "retry_feedback": "",
        "final_answer": "",
        "answer_relevance_score": 0.0,
    }


# ---------------------------------------------------------------------------
# SSE event formatting
# ---------------------------------------------------------------------------


def _sse_event(event: str, data: dict | None = None, **kwargs) -> dict:
    """Build an SSE-compatible dict with event type and JSON data."""
    payload = {"event": event}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return payload


def _extract_plan_event(update: dict) -> dict | None:
    """Extract a plan SSE event from a planner node update."""
    plan = update.get("plan")
    if plan is None:
        return None
    return _sse_event("plan", data={
        "plan_type": plan.get("plan_type", "single"),
        "tasks": plan.get("tasks", []),
        "confidence": plan.get("confidence", 0.0),
    })


def _extract_query_result_events(update: dict, queries: list[dict]) -> list[dict]:
    """Extract query_result SSE events from an executor_eval node update."""
    results = update.get("query_results", [])
    events = []

    # Build SQL lookup from accumulated queries
    sql_by_id = {q["id"]: q.get("sql", "") for q in queries}

    for result in results:
        task_id = result.get("task_id", "")
        eval_report = result.get("eval_report", {})
        events.append(_sse_event("query_result", data={
            "task_id": task_id,
            "sql": sql_by_id.get(task_id, ""),
            "score": round(result.get("score", 0.0), 4),
            "data": result.get("data", []),
            "rows_returned": result.get("rows_returned", 0),
            "status": result.get("status", "unknown"),
            "error": result.get("error", ""),
            "relevance": eval_report.get("relevance", {}),
        }))

    return events


def _extract_answer_event(update: dict) -> dict | None:
    """Extract an answer SSE event from a summarizer node update."""
    answer = update.get("final_answer")
    if answer is None:
        return None
    return _sse_event("answer", data={"final_answer": answer})


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------


_SENTINEL = object()  # signals the sync thread is done


async def _stream_agent(question: str, db_path: str) -> AsyncGenerator[str, None]:
    """Async generator that runs the LangGraph agent and yields SSE events.

    The LangGraph graph.stream() is synchronous, so we run it in a thread
    pool executor.  Events are pushed into a thread-safe queue as each graph
    node completes, so the SSE connection sends data incrementally instead of
    waiting for the full run to finish.
    """
    start = time.perf_counter()
    q: thread_queue.Queue = thread_queue.Queue()

    # Accumulated state for cross-event lookups (only accessed by the sync
    # thread inside _run_sync, so no concurrent-access issues).
    accumulated_queries: list[dict] = []

    def _process_graph_event(event: dict) -> list[str]:
        """Turn a single LangGraph stream event into SSE JSON strings."""
        sse_events: list[str] = []
        for node_name, update in event.items():
            if not update:
                sse_events.append(
                    json.dumps(_sse_event("node", node=node_name, status="done"))
                )
                continue

            if "queries" in update:
                accumulated_queries.extend(update["queries"])

            sse_events.append(
                json.dumps(_sse_event("node", node=node_name, status="done"))
            )

            if node_name == "planner":
                plan_event = _extract_plan_event(update)
                if plan_event:
                    sse_events.append(json.dumps(plan_event))

            if node_name == "executor_eval":
                for qr_event in _extract_query_result_events(update, accumulated_queries):
                    sse_events.append(json.dumps(qr_event))

            if node_name == "summarizer":
                answer_event = _extract_answer_event(update)
                if answer_event:
                    sse_events.append(json.dumps(answer_event))

        return sse_events

    def _run_sync() -> None:
        """Run the synchronous graph and push SSE strings into the queue."""
        try:
            graph = build_graph()
            initial_state = _build_initial_state(question, db_path)
            for event in graph.stream(initial_state, stream_mode="updates"):
                for sse_str in _process_graph_event(event):
                    q.put(sse_str)
        except Exception as exc:
            logger.exception("Agent execution failed: %s", exc)
            q.put(json.dumps(_sse_event("error", data={"message": str(exc)})))
        finally:
            q.put(_SENTINEL)

    # Launch the blocking graph in a background thread
    asyncio.get_running_loop().run_in_executor(None, _run_sync)

    # Yield SSE strings as they arrive — await in thread so we don't block
    while True:
        item = await asyncio.to_thread(q.get)
        if item is _SENTINEL:
            break
        yield item

    elapsed = round(time.perf_counter() - start, 2)
    yield json.dumps(_sse_event("done", data={"elapsed": elapsed}))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/presets", response_model=list[PresetOut])
async def list_presets():
    """Return the list of available database presets."""
    return [
        PresetOut(id=p["id"], name=p["name"], description=p["description"])
        for p in PRESETS.values()
    ]


@app.get("/schema/{preset_id}", response_model=SchemaOut)
async def get_schema(preset_id: str):
    """Return the table and column schema for a database preset."""
    db_path = _get_db_path(preset_id)
    tables = _read_schema(db_path)
    return SchemaOut(tables=tables)


@app.post("/query")
async def run_query(body: QueryIn):
    """Execute a natural language query against the agent and stream results as SSE.

    Returns a Server-Sent Events stream. Each event is a JSON line with an
    ``event`` field indicating the type:

    - ``node``         : A graph node completed processing
    - ``plan``         : The planner produced a query plan
    - ``query_result`` : A query was executed and scored
    - ``answer``       : The summarizer produced a final answer
    - ``done``         : All processing is complete (includes elapsed time)
    - ``error``        : An error occurred during processing
    """
    db_path = _get_db_path(body.preset)

    return EventSourceResponse(
        _stream_agent(body.question, db_path),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {
        "status": "ok",
        "model": MODEL,
        "score_threshold": SCORE_THRESHOLD,
        "max_retries": MAX_RETRIES,
        "dialect": DEFAULT_DIALECT,
    }


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )
