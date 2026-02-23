"""Tests for the retry_handler LangGraph node.

Covers all five failure priority categories plus edge cases like
empty query_results and retry_count incrementation.
"""

from __future__ import annotations

import pytest

from agent.nodes.retry_handler import retry_handler


# ---------------------------------------------------------------------------
# Helpers to build minimal AgentState dicts
# ---------------------------------------------------------------------------


def _make_state(
    result: dict,
    retry_count: int = 0,
) -> dict:
    """Build a minimal AgentState-compatible dict with one query result."""
    return {
        "query_results": [result],
        "retry_count": retry_count,
    }


def _make_result(
    *,
    error: str = "",
    status: str = "success",
    rows_returned: int = 1,
    eval_report: dict | None = None,
) -> dict:
    """Build a minimal QueryResult-compatible dict."""
    return {
        "task_id": "test-task-1",
        "data": [],
        "rows_returned": rows_returned,
        "execution_time_ms": 10.0,
        "score": 0.0,
        "eval_report": eval_report or {},
        "status": status,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Priority 1: Execution error
# ---------------------------------------------------------------------------


class TestExecutionError:
    """Priority 1 — execution errors from DB or eval report."""

    def test_result_level_error(self):
        """Error string in the result dict itself."""
        result = _make_result(
            error="near \"SELCET\": syntax error",
            status="error",
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "SQL execution error" in out["retry_feedback"]
        assert "SELCET" in out["retry_feedback"]

    def test_eval_report_execution_error(self):
        """Error buried in eval_report.details.execution.error."""
        result = _make_result(
            eval_report={
                "details": {
                    "execution": {
                        "success": False,
                        "error": "no such table: orders_archive",
                    }
                }
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "SQL execution error" in out["retry_feedback"]
        assert "orders_archive" in out["retry_feedback"]

    def test_result_error_takes_priority_over_eval_error(self):
        """When both result.error and eval_report error exist, result wins."""
        result = _make_result(
            error="result-level error",
            eval_report={
                "details": {
                    "execution": {
                        "success": False,
                        "error": "eval-level error",
                    }
                }
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "result-level error" in out["retry_feedback"]

    def test_empty_error_string_not_treated_as_error(self):
        """An empty or whitespace-only error string is not a real error."""
        result = _make_result(error="   ", status="success", rows_returned=1)
        state = _make_state(result)
        out = retry_handler(state)

        # Should fall through to generic, not execution error
        assert "SQL execution error" not in out["retry_feedback"]


# ---------------------------------------------------------------------------
# Priority 2: Hallucination
# ---------------------------------------------------------------------------


class TestHallucination:
    """Priority 2 — phantom tables/columns detected by the evaluator."""

    def test_phantom_tables(self):
        result = _make_result(
            eval_report={
                "analysis": {
                    "hallucinations": {
                        "phantom_tables": ["order_items", "users"],
                    }
                }
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "Hallucination" in out["retry_feedback"]
        assert "order_items" in out["retry_feedback"]
        assert "users" in out["retry_feedback"]

    def test_phantom_columns(self):
        result = _make_result(
            eval_report={
                "analysis": {
                    "hallucinations": {
                        "phantom_columns": ["customer_name", "total_amt"],
                    }
                }
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "Hallucination" in out["retry_feedback"]
        assert "customer_name" in out["retry_feedback"]
        assert "total_amt" in out["retry_feedback"]

    def test_both_phantom_tables_and_columns(self):
        result = _make_result(
            eval_report={
                "analysis": {
                    "hallucinations": {
                        "phantom_tables": ["lineage"],
                        "phantom_columns": ["foobar"],
                    }
                }
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "lineage" in out["retry_feedback"]
        assert "foobar" in out["retry_feedback"]

    def test_empty_hallucinations_dict_is_not_hallucination(self):
        """An empty hallucinations dict means no hallucination detected."""
        result = _make_result(
            eval_report={"analysis": {"hallucinations": {}}},
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "Hallucination" not in out["retry_feedback"]

    def test_execution_error_takes_priority_over_hallucination(self):
        """Priority 1 (exec error) should win over priority 2 (hallucination)."""
        result = _make_result(
            error="syntax error at position 42",
            eval_report={
                "analysis": {
                    "hallucinations": {
                        "phantom_tables": ["ghost_table"],
                    }
                }
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "SQL execution error" in out["retry_feedback"]
        assert "Hallucination" not in out["retry_feedback"]


# ---------------------------------------------------------------------------
# Priority 3: Safety violation
# ---------------------------------------------------------------------------


class TestSafety:
    """Priority 3 — non-SELECT queries (safety score < 0.5)."""

    def test_low_safety_score(self):
        result = _make_result(
            eval_report={
                "dimensions": {"safety": 0.0},
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "Only SELECT queries are permitted" in out["retry_feedback"]

    def test_safety_at_threshold(self):
        """Safety score exactly 0.5 should NOT trigger (< 0.5 required)."""
        result = _make_result(
            eval_report={
                "dimensions": {"safety": 0.5},
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "Only SELECT queries" not in out["retry_feedback"]

    def test_safety_above_threshold(self):
        result = _make_result(
            eval_report={
                "dimensions": {"safety": 0.8},
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "Only SELECT queries" not in out["retry_feedback"]


# ---------------------------------------------------------------------------
# Priority 4: Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    """Priority 4 — query executed successfully but returned 0 rows."""

    def test_zero_rows_success(self):
        result = _make_result(rows_returned=0, status="success")
        state = _make_state(result)
        out = retry_handler(state)

        assert "returned 0 rows" in out["retry_feedback"]
        assert "WHERE" in out["retry_feedback"]

    def test_zero_rows_error_status_not_empty_results(self):
        """Zero rows with error status should not trigger empty-results."""
        result = _make_result(
            rows_returned=0,
            status="error",
            error="some error",
        )
        state = _make_state(result)
        out = retry_handler(state)

        # Should be caught by priority 1 (execution error), not priority 4
        assert "SQL execution error" in out["retry_feedback"]

    def test_nonzero_rows_not_empty_results(self):
        result = _make_result(rows_returned=5, status="success")
        state = _make_state(result)
        out = retry_handler(state)

        assert "returned 0 rows" not in out["retry_feedback"]


# ---------------------------------------------------------------------------
# Priority 5: Generic low score
# ---------------------------------------------------------------------------


class TestGenericLowScore:
    """Priority 5 — catch-all for low scores with no specific failure."""

    def test_generic_includes_overall_score(self):
        result = _make_result(
            rows_returned=3,
            eval_report={
                "overall": 0.45,
                "dimensions": {
                    "correctness": 0.3,
                    "efficiency": 0.9,
                    "safety": 1.0,
                },
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "0.45" in out["retry_feedback"]
        assert "correctness" in out["retry_feedback"]

    def test_generic_lists_weak_dimensions(self):
        result = _make_result(
            rows_returned=3,
            eval_report={
                "overall": 0.55,
                "dimensions": {
                    "correctness": 0.4,
                    "completeness": 0.5,
                    "safety": 1.0,
                    "efficiency": 0.9,
                },
            },
        )
        state = _make_state(result)
        out = retry_handler(state)

        assert "correctness" in out["retry_feedback"]
        assert "completeness" in out["retry_feedback"]
        # Above threshold -- should not appear as weak
        assert "efficiency" not in out["retry_feedback"]


# ---------------------------------------------------------------------------
# Retry count
# ---------------------------------------------------------------------------


class TestRetryCount:
    """retry_count should always increment by 1."""

    def test_increments_from_zero(self):
        result = _make_result()
        state = _make_state(result, retry_count=0)
        out = retry_handler(state)
        assert out["retry_count"] == 1

    def test_increments_from_nonzero(self):
        result = _make_result()
        state = _make_state(result, retry_count=2)
        out = retry_handler(state)
        assert out["retry_count"] == 3

    def test_missing_retry_count_defaults_to_zero(self):
        """If retry_count is absent from state, treat it as 0."""
        state = {"query_results": [_make_result()]}
        out = retry_handler(state)
        assert out["retry_count"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and defensive behaviour."""

    def test_no_query_results(self):
        """retry_handler called with empty query_results list."""
        state = {"query_results": [], "retry_count": 0}
        out = retry_handler(state)

        assert "No query results" in out["retry_feedback"]
        assert out["retry_count"] == 1

    def test_missing_query_results_key(self):
        """State dict missing query_results entirely."""
        state = {"retry_count": 0}
        out = retry_handler(state)

        assert "No query results" in out["retry_feedback"]
        assert out["retry_count"] == 1

    def test_multiple_results_uses_last(self):
        """When multiple query results exist, use the last one."""
        old_result = _make_result(error="old error", status="error")
        new_result = _make_result(
            rows_returned=0,
            status="success",
        )
        state = {
            "query_results": [old_result, new_result],
            "retry_count": 1,
        }
        out = retry_handler(state)

        # Should see empty-results feedback (from new_result), not exec error
        assert "returned 0 rows" in out["retry_feedback"]
        assert "old error" not in out["retry_feedback"]

    def test_missing_eval_report(self):
        """Result with no eval_report should still produce feedback."""
        result = _make_result(rows_returned=3)
        del result["eval_report"]
        state = _make_state(result)
        out = retry_handler(state)

        # Falls through to generic low score
        assert "retry_feedback" in out
        assert out["retry_count"] == 1

    def test_return_keys(self):
        """Output dict should contain exactly retry_feedback and retry_count."""
        result = _make_result()
        state = _make_state(result)
        out = retry_handler(state)

        assert set(out.keys()) == {"retry_feedback", "retry_count"}
