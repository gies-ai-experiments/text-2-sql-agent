"""
Evaluation Pipeline - Runs SQL through SQLExecutor and sends to Scorer

Multi-dialect support: SQLite, DuckDB, PostgreSQL, BigQuery

Usage:
    # SQLite (default, zero setup)
    python run_evaluation_pipeline.py "SELECT * FROM users"

    # DuckDB
    python run_evaluation_pipeline.py "SELECT * FROM users" --dialect duckdb --db-path data.duckdb

    # PostgreSQL
    python run_evaluation_pipeline.py "SELECT * FROM users" --dialect postgresql --connection-string "postgresql://..."

    # With expected results
    python run_evaluation_pipeline.py --file query.sql --expected expected_results.json
"""

import argparse
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from typing import Dict, Any, List, Optional

from agentx import SQLExecutor, ExecutorConfig
from evaluation.data_structures import (
    AgentResult,
    ExecutionResult,
    ComparisonResult,
)
from evaluation.result_comparator import DefaultResultComparator
from evaluation.scorer import DefaultScorer


def load_sql_from_file(filepath: str) -> str:
    """Load SQL query from a file."""
    with open(filepath, 'r') as f:
        return f.read().strip()


def load_expected_results(filepath: str) -> List[Dict[str, Any]]:
    """Load expected results from a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def create_executor(
    dialect: str,
    db_path: Optional[str] = None,
    connection_string: Optional[str] = None,
) -> SQLExecutor:
    """
    Create a SQLExecutor for the specified dialect.

    Args:
        dialect: Database dialect (sqlite, duckdb, postgresql, bigquery)
        db_path: Path to database file (for SQLite, DuckDB)
        connection_string: Connection string (for PostgreSQL)

    Returns:
        Configured SQLExecutor
    """
    config = ExecutorConfig(
        dialect=dialect,
        db_path=db_path,
        connection_string=connection_string,
    )
    return SQLExecutor(config)


def run_sql_executor(
    sql: str,
    dialect: str = "sqlite",
    db_path: Optional[str] = None,
    connection_string: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run SQL through the SQLExecutor.

    Returns the raw executor output dictionary.
    """
    executor = create_executor(dialect, db_path, connection_string)
    try:
        result = executor.process_query(sql, verbose=True)
        return result.to_dict()
    finally:
        executor.close()


def convert_to_execution_result(agent_output: Dict[str, Any]) -> ExecutionResult:
    """
    Convert SQLExecutor output to ExecutionResult for scoring.
    """
    agent_result = AgentResult.from_agent_output(agent_output)
    return agent_result.to_execution_result()


def compare_results(
    actual: List[Dict[str, Any]],
    expected: List[Dict[str, Any]],
) -> ComparisonResult:
    """
    Compare actual results with expected results.
    """
    comparator = DefaultResultComparator()
    return comparator.compare(actual, expected)


def score_execution(
    comparison: ComparisonResult,
    execution_result: ExecutionResult,
) -> Dict[str, Any]:
    """
    Score the execution using the DefaultScorer.

    Returns a dictionary with all score dimensions.
    """
    scorer = DefaultScorer()
    score = scorer.score(comparison, execution_result)

    return {
        "overall": round(score.overall, 4),
        "dimensions": {
            "correctness": round(score.correctness, 4),
            "efficiency": round(score.efficiency, 4),
            "safety": round(score.safety, 4),
            "result_completeness": round(score.result_completeness, 4),
        },
        "sub_scores": {
            "validation_score": round(score.validation_score, 4),
            "performance_score": round(score.performance_score, 4),
            "hallucination_score": round(score.hallucination_score, 4),
        },
        "weights": score.weights,
        "details": score.details,
    }


def run_evaluation_pipeline(
    sql: str,
    dialect: str = "sqlite",
    db_path: Optional[str] = None,
    connection_string: Optional[str] = None,
    expected_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Complete evaluation pipeline:
    1. Run SQL through SQLExecutor (multi-dialect)
    2. Convert output to ExecutionResult
    3. Compare with expected results (if provided)
    4. Score the execution
    5. Return comprehensive results
    """
    print("\n" + "=" * 80)
    print("EVALUATION PIPELINE")
    print("=" * 80)
    print(f"Dialect: {dialect.upper()}")

    # Step 1: Run SQL through executor
    print(f"\nStep 1: Running SQL through SQLExecutor ({dialect})...")
    agent_output = run_sql_executor(sql, dialect, db_path, connection_string)

    # Step 2: Convert to ExecutionResult
    print("\nStep 2: Converting to ExecutionResult...")
    execution_result = convert_to_execution_result(agent_output)
    print(f"   Execution success: {execution_result.success}")
    print(f"   Rows returned: {execution_result.rows_returned}")
    print(f"   Execution time: {execution_result.execution_time_ms:.2f}ms")

    # Step 3: Compare results
    print("\nStep 3: Comparing results...")
    actual_data = execution_result.data

    if expected_results is not None:
        comparison = compare_results(actual_data, expected_results)
        print(f"   Expected rows: {len(expected_results)}")
        print(f"   Match: {comparison.is_match}")
        print(f"   Match score: {comparison.match_score:.2%}")
    else:
        # No expected results - create a "self-comparison" (perfect match)
        comparison = ComparisonResult(
            is_match=True,
            match_score=1.0,
            row_count_match=True,
            column_count_match=True,
            details={"message": "No expected results provided - using self-comparison"},
        )
        print("   No expected results provided - assuming correctness")

    # Step 4: Score execution
    print("\nStep 4: Scoring execution...")
    scores = score_execution(comparison, execution_result)

    print(f"\n   {'=' * 40}")
    print(f"   SCORES")
    print(f"   {'=' * 40}")
    print(f"   Overall Score: {scores['overall']:.2%}")
    print(f"   {'-' * 40}")
    print(f"   Correctness:    {scores['dimensions']['correctness']:.2%} (weight: 40%)")
    print(f"   Efficiency:     {scores['dimensions']['efficiency']:.2%} (weight: 20%)")
    print(f"   Safety:         {scores['dimensions']['safety']:.2%} (weight: 25%)")
    print(f"   Completeness:   {scores['dimensions']['result_completeness']:.2%} (weight: 15%)")
    print(f"   {'=' * 40}")

    # Compile final output
    pipeline_result = {
        "query": sql,
        "dialect": dialect,
        "agent_status": agent_output.get("overall_status", "UNKNOWN"),
        "execution_result": {
            "success": execution_result.success,
            "rows_returned": execution_result.rows_returned,
            "execution_time_ms": execution_result.execution_time_ms,
            "is_valid": execution_result.is_valid,
            "validation_errors": execution_result.validation_errors,
        },
        "comparison": {
            "is_match": comparison.is_match,
            "match_score": comparison.match_score,
            "details": comparison.details,
        },
        "scores": scores,
    }

    return pipeline_result


def main():
    parser = argparse.ArgumentParser(
        description="Run SQL through multi-dialect SQLExecutor and score with Evaluation pipeline"
    )
    parser.add_argument(
        "sql",
        nargs="?",
        help="SQL query to execute (or use --file)",
    )
    parser.add_argument(
        "--file", "-f",
        help="Path to a .sql file containing the query",
    )
    parser.add_argument(
        "--expected", "-e",
        help="Path to a JSON file containing expected results",
    )
    parser.add_argument(
        "--dialect", "-D",
        default="sqlite",
        choices=["sqlite", "duckdb", "postgresql", "bigquery"],
        help="SQL dialect to use (default: sqlite)",
    )
    parser.add_argument(
        "--db-path",
        help="Path to database file (for SQLite, DuckDB). Use ':memory:' for in-memory.",
    )
    parser.add_argument(
        "--connection-string", "-c",
        help="Database connection string (for PostgreSQL)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to save the results as JSON",
    )

    args = parser.parse_args()

    # Get SQL query
    if args.file:
        sql = load_sql_from_file(args.file)
    elif args.sql:
        sql = args.sql
    else:
        print("Error: Please provide a SQL query or use --file")
        sys.exit(1)

    # Load expected results if provided
    expected_results = None
    if args.expected:
        expected_results = load_expected_results(args.expected)

    # Run the pipeline
    result = run_evaluation_pipeline(
        sql=sql,
        dialect=args.dialect,
        db_path=args.db_path,
        connection_string=args.connection_string,
        expected_results=expected_results,
    )

    # Save output if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {args.output}")

    # Print final summary
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Dialect: {result['dialect'].upper()}")
    print(f"Final Score: {result['scores']['overall']:.2%}")
    print("=" * 80 + "\n")

    return result


if __name__ == "__main__":
    main()
