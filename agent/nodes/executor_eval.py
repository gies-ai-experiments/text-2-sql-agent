"""
Executor + Evaluator LangGraph node.

Executes the generated SQL via the eval infrastructure's SQLExecutor,
then scores the result using EnhancedScorer.  This is the most
integration-heavy node — it bridges the agent's state types to the
eval framework's data structures.

Data flow:
    AgentState.current_task["sql"]
        → SQLExecutor.process_query()
        → AgentResult.from_agent_output()
        → EnhancedScorer.score()
        → QueryResult  (appended to state.query_results)
"""

from __future__ import annotations

import logging

from agentx import SQLExecutor, ExecutorConfig
from evaluation.enhanced_scorer import EnhancedScorer
from evaluation.data_structures import ComparisonResult, AgentResult

from agent.state import AgentState, QueryResult
from agent.nodes.query_relevance import check_query_relevance

logger = logging.getLogger(__name__)

# Weight for blending relevance into the overall score.
# overall_final = (1 - RELEVANCE_WEIGHT) * eval_score + RELEVANCE_WEIGHT * relevance_score
RELEVANCE_WEIGHT = 0.15


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def executor_eval(state: AgentState) -> dict:
    """Execute SQL and score the result.

    Reads ``current_task`` from the graph state, runs the query through the
    eval framework's :class:`SQLExecutor`, converts the output to the
    evaluation data-structures, scores it with :class:`EnhancedScorer`, and
    returns a single-element ``query_results`` list that LangGraph will
    append to the accumulator channel.

    If *anything* goes wrong (import error, DB connection failure, scoring
    crash, etc.) the node still returns a valid ``QueryResult`` with
    ``status="error"`` and ``score=0.0`` so downstream nodes can decide
    whether to retry.
    """
    current_task = state["current_task"]
    sql: str = current_task["sql"]
    dialect: str = state["dialect"]
    db_path: str = state["db_path"]

    try:
        # -- 1. Execute --------------------------------------------------
        executor = SQLExecutor(ExecutorConfig(dialect=dialect, db_path=db_path))
        try:
            executor_result = executor.process_query(sql)
        finally:
            executor.close()

        # -- 2. Bridge to scoring types ----------------------------------
        agent_result = AgentResult.from_agent_output(executor_result.to_dict())
        eval_exec_result = agent_result.to_execution_result()

        # -- 3. Self-eval score (no gold reference in live mode) ---------
        #
        # In tournament mode we don't have expected results to compare
        # against, so we build a minimal ComparisonResult that reflects
        # whether execution itself succeeded.
        comparison = ComparisonResult(
            is_match=executor_result.success,
            match_score=1.0 if executor_result.success else 0.0,
            row_count_match=True,
            column_count_match=True,
        )

        scorer = EnhancedScorer()
        score = scorer.score(
            comparison=comparison,
            execution_result=eval_exec_result,
            sql=sql,
            dialect=dialect,
        )

        # -- 4. Per-query relevance check ---------------------------------
        data = executor_result.data
        relevance_score = 0.5  # default if check fails
        relevance_reasoning = ""
        try:
            relevance_score, relevance_reasoning = check_query_relevance(
                question=state.get("question", ""),
                task_description=current_task.get("description", ""),
                sql=sql,
                data=data,
            )
        except Exception as rel_exc:
            logger.warning("Relevance check failed: %s", rel_exc)

        # Blend relevance into overall score
        blended_score = (
            (1 - RELEVANCE_WEIGHT) * score.overall
            + RELEVANCE_WEIGHT * relevance_score
        )

        # Include relevance in the eval report
        eval_dict = score.to_dict()
        eval_dict["relevance"] = {
            "score": relevance_score,
            "reasoning": relevance_reasoning,
            "weight": RELEVANCE_WEIGHT,
        }
        eval_dict["overall_before_relevance"] = score.overall
        eval_dict["overall"] = round(blended_score, 4)

        # -- 5. Build QueryResult ----------------------------------------
        result = QueryResult(
            task_id=current_task["id"],
            data=data,
            rows_returned=len(data),
            execution_time_ms=executor_result.execution.get("execution_time_ms", 0.0),
            score=blended_score,
            eval_report=eval_dict,
            status="success" if executor_result.success else "failed",
            error=executor_result.error or "",
        )

        logger.info(
            "executor_eval  task=%s  status=%s  score=%.4f  rows=%d  time=%.1fms",
            result["task_id"],
            result["status"],
            result["score"],
            result["rows_returned"],
            result["execution_time_ms"],
        )

    except Exception as exc:
        logger.exception("executor_eval failed for task %s", current_task.get("id", "?"))
        result = QueryResult(
            task_id=current_task.get("id", "unknown"),
            data=[],
            rows_returned=0,
            execution_time_ms=0.0,
            score=0.0,
            eval_report={},
            status="error",
            error=str(exc),
        )

    return {"query_results": [result]}
