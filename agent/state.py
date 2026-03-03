"""TypedDict definitions for LangGraph agent state."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class QueryTask(TypedDict):
    id: str
    description: str
    sql: str
    depends_on: list[str]


class QueryResult(TypedDict):
    task_id: str
    data: list[dict]
    rows_returned: int
    execution_time_ms: float
    score: float
    eval_report: dict
    status: str  # "success" | "failed" | "error"
    error: str


class QueryPlan(TypedDict):
    plan_type: str  # "single" | "multi-sequential" | "multi-parallel"
    tasks: list[QueryTask]
    confidence: float


class AgentState(TypedDict):
    question: str
    dialect: str
    db_path: str
    schema_context: str
    plan: QueryPlan
    current_task: QueryTask
    queries: Annotated[list[QueryTask], operator.add]
    query_results: Annotated[list[QueryResult], operator.add]
    retry_count: int
    retry_feedback: str
    final_answer: str
    answer_relevance_score: float
