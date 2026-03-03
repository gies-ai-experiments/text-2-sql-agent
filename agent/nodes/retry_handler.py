"""Retry handler node — categorizes failures and produces targeted feedback.

Examines the most recent QueryResult and its eval_report to determine
*why* the query failed, then constructs specific, actionable feedback
for the query_generator on its next attempt.

Failure categories are checked in priority order:
  1. Execution error (syntax error, runtime error from the DB)
  2. Hallucination (phantom tables or columns not in the schema)
  3. Safety violation (non-SELECT statement detected)
  4. Relevance (query result is off-path from the user question)
  5. Empty results (query ran but returned 0 rows)
  6. Generic low score (catch-all with score + threshold)

No LLM call is made here — this is pure deterministic categorization.
"""

from __future__ import annotations

import logging

from agent.config import SCORE_THRESHOLD
from agent.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Failure categorization helpers
# ---------------------------------------------------------------------------


def _check_execution_error(result: dict, eval_report: dict) -> str | None:
    """Priority 1: Check for execution errors (syntax, runtime, etc.)."""
    # Check the result-level error first
    error = result.get("error")
    if error and str(error).strip():
        return (
            f"SQL execution error — fix the query and try again.\n"
            f"Error: {error}"
        )

    # Fall back to the eval report's execution details
    exec_details = eval_report.get("details", {}).get("execution", {})
    exec_error = exec_details.get("error")
    if exec_error and str(exec_error).strip():
        return (
            f"SQL execution error — fix the query and try again.\n"
            f"Error: {exec_error}"
        )

    return None


def _check_hallucination(eval_report: dict) -> str | None:
    """Priority 2: Check for hallucinated tables or columns."""
    hallucinations = eval_report.get("analysis", {}).get("hallucinations", {})
    if not hallucinations:
        return None

    parts: list[str] = [
        "Hallucination detected — the query references schema objects "
        "that do not exist in the database."
    ]

    phantom_tables = hallucinations.get("phantom_tables", [])
    if phantom_tables:
        parts.append(f"  Non-existent tables: {', '.join(phantom_tables)}")

    phantom_columns = hallucinations.get("phantom_columns", [])
    if phantom_columns:
        parts.append(f"  Non-existent columns: {', '.join(phantom_columns)}")

    parts.append(
        "Review the schema provided and use only tables and columns "
        "that actually exist."
    )
    return "\n".join(parts)


def _check_safety(eval_report: dict) -> str | None:
    """Priority 3: Check for safety violations (non-SELECT queries)."""
    safety_score = eval_report.get("dimensions", {}).get("safety", 1.0)
    if safety_score < 0.5:
        return (
            "Only SELECT queries are permitted. "
            "Do not use INSERT, UPDATE, DELETE, DROP, or other DDL/DML."
        )
    return None


def _check_relevance(eval_report: dict) -> str | None:
    """Priority 4: Check if the query result is off-path from the user question."""
    relevance = eval_report.get("relevance", {})
    relevance_score = relevance.get("score", 1.0)
    if relevance_score < 0.5:
        reasoning = relevance.get("reasoning", "")
        return (
            f"Query result is not relevant to the original question "
            f"(relevance score: {relevance_score:.2f}).\n"
            f"Issue: {reasoning}\n"
            f"Rewrite the query to directly address what was asked."
        )
    return None


def _check_empty_results(result: dict) -> str | None:
    """Priority 5: Check for queries that executed but returned no rows."""
    rows_returned = result.get("rows_returned", 0)
    status = result.get("status", "")
    if rows_returned == 0 and status == "success":
        return (
            "Query executed successfully but returned 0 rows. "
            "Review WHERE conditions and JOIN clauses to ensure they "
            "match existing data."
        )
    return None


def _build_generic_feedback(eval_report: dict) -> str:
    """Priority 5: Generic low-score feedback (catch-all)."""
    overall = eval_report.get("overall", 0.0)
    
    parts = [
        f"Query scored {overall:.2f}, below the required threshold "
        f"of {SCORE_THRESHOLD:.2f}."
    ]

    # Include per-dimension breakdown so the generator knows where to focus
    dimensions = eval_report.get("dimensions", {})
    if dimensions:
        weak = [
            f"{dim}: {score:.2f}"
            for dim, score in sorted(dimensions.items())
            if score < SCORE_THRESHOLD
        ]
        if weak:
            parts.append(f"  Weak dimensions: {', '.join(weak)}")

    parts.append("Revise the query to improve the score.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------


def retry_handler(state: AgentState) -> dict:
    """Categorize the most recent failure and produce targeted feedback.

    Returns
    -------
    dict
        ``{"retry_feedback": str, "retry_count": int}`` to be merged
        into AgentState.
    """
    query_results = state.get("query_results", [])
    if not query_results:
        logger.warning("retry_handler called with no query_results")
        return {
            "retry_feedback": "No query results available to analyze.",
            "retry_count": state.get("retry_count", 0) + 1,
        }

    result = query_results[-1]
    eval_report: dict = result.get("eval_report", {})

    # Walk the priority chain — first match wins
    feedback = (
        _check_execution_error(result, eval_report)
        or _check_hallucination(eval_report)
        or _check_safety(eval_report)
        or _check_relevance(eval_report)
        or _check_empty_results(result)
        or _build_generic_feedback(eval_report)
    )

    new_retry_count = state.get("retry_count", 0) + 1
    logger.info(
        "Retry %d — feedback category: %s",
        new_retry_count,
        feedback.split("\n")[0][:80],
    )

    return {
        "retry_feedback": feedback,
        "retry_count": new_retry_count,
    }
