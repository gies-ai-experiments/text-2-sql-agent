#!/usr/bin/env python3
"""
Test script for the multi-dialect evaluation pipeline integration.

Tests the full flow:
    SQLExecutor -> ExecutionResult -> Scorer -> MultiDimensionalScore
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agentx import SQLExecutor, ExecutorConfig
from evaluation.data_structures import AgentResult, ComparisonResult
from evaluation.scorer import DefaultScorer


def test_sqlite_pipeline():
    """Test the full pipeline with SQLite."""
    print("\n" + "=" * 60)
    print("TEST: Full Evaluation Pipeline (SQLite)")
    print("=" * 60)

    # Create SQLite executor with test data
    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

    # Create test schema
    executor.adapter.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER
        )
    """)
    executor.adapter.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@test.com', 30)")
    executor.adapter.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@test.com', 25)")
    executor.adapter.execute("INSERT INTO users VALUES (3, 'Charlie', 'charlie@test.com', 35)")

    executor.refresh_schema()

    # Execute a query through the pipeline
    print("\n--- Step 1: Execute query through SQLExecutor ---")
    result = executor.process_query(
        "SELECT name, age FROM users WHERE age > 25 ORDER BY age",
        verbose=True
    )

    print(f"\nExecutor result:")
    print(f"  Status: {result.overall_status}")
    print(f"  Data: {result.data}")

    # Convert to evaluation format
    print("\n--- Step 2: Convert to AgentResult -> ExecutionResult ---")
    agent_result = AgentResult.from_agent_output(result.to_dict())
    execution_result = agent_result.to_execution_result()

    print(f"  success: {execution_result.success}")
    print(f"  rows_returned: {execution_result.rows_returned}")
    print(f"  is_valid: {execution_result.is_valid}")
    print(f"  execution_time_ms: {execution_result.execution_time_ms:.2f}")

    # Score with expected results
    print("\n--- Step 3: Score execution ---")
    expected_results = [
        {"name": "Alice", "age": 30},
        {"name": "Charlie", "age": 35},
    ]

    # Create comparison result (perfect match for this test)
    comparison = ComparisonResult(
        is_match=True,
        match_score=1.0,
        row_count_match=True,
        column_count_match=True,
    )

    scorer = DefaultScorer()
    score = scorer.score(comparison, execution_result)

    print(f"\n  SCORES:")
    print(f"  {'=' * 40}")
    print(f"  Overall:        {score.overall:.2%}")
    print(f"  Correctness:    {score.correctness:.2%}")
    print(f"  Efficiency:     {score.efficiency:.2%}")
    print(f"  Safety:         {score.safety:.2%}")
    print(f"  Completeness:   {score.result_completeness:.2%}")

    # Verify scores are reasonable
    assert score.overall > 0.9, f"Expected overall > 0.9, got {score.overall}"
    assert score.correctness == 1.0, f"Expected correctness == 1.0, got {score.correctness}"
    assert score.safety > 0.9, f"Expected safety > 0.9, got {score.safety}"

    executor.close()
    print("\n✅ SQLite pipeline test passed!")


def test_hallucination_scoring():
    """Test that hallucinations are penalized in scoring."""
    print("\n" + "=" * 60)
    print("TEST: Hallucination Scoring")
    print("=" * 60)

    # Create SQLite executor with test data
    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

    executor.adapter.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL
        )
    """)
    executor.adapter.execute("INSERT INTO products VALUES (1, 'Widget', 9.99)")

    executor.refresh_schema()

    # Test with hallucinated table
    print("\n--- Query with phantom table ---")
    result = executor.process_query("SELECT * FROM fake_table", verbose=False)

    print(f"  Status: {result.overall_status}")
    print(f"  Validation errors: {result.validation.get('errors', [])}")

    agent_result = AgentResult.from_agent_output(result.to_dict())
    execution_result = agent_result.to_execution_result()

    comparison = ComparisonResult(is_match=False, match_score=0.0)
    scorer = DefaultScorer()
    score = scorer.score(comparison, execution_result)

    print(f"\n  SCORES (with hallucination):")
    print(f"  Overall:     {score.overall:.2%}")
    print(f"  Safety:      {score.safety:.2%}")
    print(f"  Hallucination penalty: {score.hallucination_score:.2%}")

    # Verify hallucination is penalized
    assert score.safety < 0.5, f"Expected safety < 0.5 for hallucination, got {score.safety}"
    assert score.hallucination_score < 0.5, f"Expected hallucination < 0.5, got {score.hallucination_score}"

    executor.close()
    print("\n✅ Hallucination scoring test passed!")


def test_duckdb_pipeline():
    """Test the pipeline with DuckDB."""
    print("\n" + "=" * 60)
    print("TEST: Full Evaluation Pipeline (DuckDB)")
    print("=" * 60)

    try:
        executor = SQLExecutor(ExecutorConfig(dialect="duckdb"))
    except ImportError:
        print("  ⚠️ DuckDB not installed, skipping test")
        return

    # Create test schema
    executor.adapter.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            product TEXT,
            amount DOUBLE,
            quantity INTEGER
        )
    """)
    executor.adapter.execute("INSERT INTO sales VALUES (1, 'Widget', 99.99, 10)")
    executor.adapter.execute("INSERT INTO sales VALUES (2, 'Gadget', 149.99, 5)")

    executor.refresh_schema()

    # Execute analytics query
    result = executor.process_query(
        "SELECT product, SUM(amount * quantity) as total FROM sales GROUP BY product",
        verbose=True
    )

    print(f"\nDuckDB result:")
    print(f"  Status: {result.overall_status}")
    print(f"  Data: {result.data}")

    agent_result = AgentResult.from_agent_output(result.to_dict())
    execution_result = agent_result.to_execution_result()

    comparison = ComparisonResult(is_match=True, match_score=1.0, row_count_match=True, column_count_match=True)
    scorer = DefaultScorer()
    score = scorer.score(comparison, execution_result)

    print(f"\n  SCORES:")
    print(f"  Overall: {score.overall:.2%}")

    assert score.overall > 0.9, f"Expected overall > 0.9, got {score.overall}"

    executor.close()
    print("\n✅ DuckDB pipeline test passed!")


def main():
    """Run all pipeline integration tests."""
    print("\n" + "=" * 60)
    print("EVALUATION PIPELINE INTEGRATION TESTS")
    print("=" * 60)

    try:
        test_sqlite_pipeline()
        test_hallucination_scoring()
        test_duckdb_pipeline()

        print("\n" + "=" * 60)
        print("ALL PIPELINE TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
