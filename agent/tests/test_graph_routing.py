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
