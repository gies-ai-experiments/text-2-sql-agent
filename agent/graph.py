"""LangGraph StateGraph definition for the text-to-SQL agent.

Nodes: schema_analyzer, planner, set_first_task, set_next_task,
       query_generator, executor_eval, retry_handler, check_remaining,
       summarizer

Routing:
    START → schema_analyzer → planner → route_after_planner
        all plan types → set_first_task → query_generator

    query_generator → executor_eval → route_after_quality_gate
        score ≥ threshold → check_remaining
        score < threshold AND retries < max → retry_handler → query_generator
        score < threshold AND retries ≥ max → check_remaining

    check_remaining → route_after_remaining
        more sequential tasks → set_next_task → query_generator
        all done → summarizer

    summarizer → END
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END, START

from agent.config import SCORE_THRESHOLD, MAX_RETRIES
from agent.state import AgentState

logger = logging.getLogger(__name__)

# -- Node imports --
from agent.nodes.schema_analyzer import schema_analyzer
from agent.nodes.planner import planner
from agent.nodes.query_generator import query_generator
from agent.nodes.executor_eval import executor_eval
from agent.nodes.retry_handler import retry_handler
from agent.nodes.summarizer import summarizer


# ---------------------------------------------------------------------------
# Helper nodes (pure state manipulation, no LLM calls)
# ---------------------------------------------------------------------------

def set_first_task(state: AgentState) -> dict:
    """Set current_task to the first task in the plan and reset retry state."""
    tasks = state["plan"]["tasks"]
    return {
        "current_task": tasks[0],
        "retry_count": 0,
        "retry_feedback": "",
    }


def set_next_task(state: AgentState) -> dict:
    """Advance to the next incomplete sequential task."""
    plan_tasks = state["plan"]["tasks"]
    completed_ids = {r["task_id"] for r in state.get("query_results", [])}

    for task in plan_tasks:
        if task["id"] not in completed_ids:
            return {
                "current_task": task,
                "retry_count": 0,
                "retry_feedback": "",
            }

    # All tasks done — shouldn't reach here, but handle gracefully
    return {}


def check_remaining(state: AgentState) -> dict:
    """Passthrough node used as an attachment point for conditional edges."""
    return {}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

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


def route_after_quality_gate(state: AgentState) -> str:
    """Route based on the current task's query result score.

    Matches on ``current_task["id"]`` so that parallel Send() branches
    each examine their own result, not the last item in the accumulator.
    """
    results = state.get("query_results", [])
    if not results:
        return "check_remaining"

    # Find the result for the current task (not just results[-1],
    # which could be from a different parallel branch).
    current_id = state["current_task"]["id"]
    matching = [r for r in results if r.get("task_id") == current_id]
    latest = matching[-1] if matching else results[-1]

    score = latest.get("score", 0.0)
    retry_count = state.get("retry_count", 0)

    if score >= SCORE_THRESHOLD:
        return "check_remaining"
    elif retry_count < MAX_RETRIES:
        return "retry_handler"
    else:
        return "check_remaining"


def route_after_remaining(state: AgentState) -> str:
    """Check if there are more sequential tasks to process."""
    plan_type = state["plan"]["plan_type"]

    if plan_type == "multi-sequential":
        plan_tasks = state["plan"]["tasks"]
        completed_ids = {r["task_id"] for r in state.get("query_results", [])}
        remaining = [t for t in plan_tasks if t["id"] not in completed_ids]
        if remaining:
            return "set_next_task"

    return "summarizer"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    # -- Add nodes --
    graph.add_node("schema_analyzer", schema_analyzer)
    graph.add_node("planner", planner)
    graph.add_node("set_first_task", set_first_task)
    graph.add_node("set_next_task", set_next_task)
    graph.add_node("query_generator", query_generator)
    graph.add_node("executor_eval", executor_eval)
    graph.add_node("retry_handler", retry_handler)
    graph.add_node("check_remaining", check_remaining)
    graph.add_node("summarizer", summarizer)

    # -- Add edges --
    graph.add_edge(START, "schema_analyzer")
    graph.add_edge("schema_analyzer", "planner")
    graph.add_conditional_edges("planner", route_after_planner, [
        "set_first_task",
    ])
    graph.add_edge("set_first_task", "query_generator")
    graph.add_edge("query_generator", "executor_eval")
    graph.add_conditional_edges("executor_eval", route_after_quality_gate, [
        "check_remaining", "retry_handler",
    ])
    graph.add_edge("retry_handler", "query_generator")
    graph.add_conditional_edges("check_remaining", route_after_remaining, [
        "set_next_task", "summarizer",
    ])
    graph.add_edge("set_next_task", "query_generator")
    graph.add_edge("summarizer", END)

    return graph.compile()


# Module-level compiled graph for import convenience
app = build_graph()
