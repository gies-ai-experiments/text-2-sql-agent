#!/usr/bin/env python3
"""
Test suite for enhanced scoring components.

Tests:
1. Query Complexity Analyzer
2. Adaptive Performance Thresholds
3. Weighted Hallucination Scoring
4. Execution Plan Analysis
5. Semantic Result Accuracy
6. Error Taxonomy
7. SQL Best Practices
8. Full Enhanced Scorer Integration
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from evaluation.advanced_scoring import (
    QueryComplexityAnalyzer,
    AdaptivePerformanceScorer,
    WeightedHallucinationScorer,
    HallucinationType,
    ExecutionPlanAnalyzer,
    SemanticAccuracyScorer,
    ErrorTaxonomyClassifier,
    ErrorCategory,
    SQLBestPracticesScorer,
)
from evaluation.enhanced_scorer import EnhancedScorer, create_enhanced_scorer
from evaluation.data_structures import ComparisonResult, ExecutionResult


def test_query_complexity_analyzer():
    """Test query complexity analysis."""
    print("\n" + "=" * 60)
    print("TEST: Query Complexity Analyzer")
    print("=" * 60)

    analyzer = QueryComplexityAnalyzer()

    # Simple query
    simple_sql = "SELECT name FROM users WHERE id = 1"
    report = analyzer.analyze(simple_sql)
    print(f"\nSimple query: {simple_sql}")
    print(f"  Complexity: {report.complexity_score:.2f} ({report.complexity_level})")
    assert report.complexity_level == "simple", f"Expected simple, got {report.complexity_level}"

    # Moderate query with JOIN
    moderate_sql = """
        SELECT u.name, o.total
        FROM users u
        INNER JOIN orders o ON u.id = o.user_id
        WHERE o.total > 100
        ORDER BY o.total DESC
    """
    report = analyzer.analyze(moderate_sql)
    print(f"\nModerate query (JOIN):")
    print(f"  Complexity: {report.complexity_score:.2f} ({report.complexity_level})")
    print(f"  JOINs: {report.join_count}, Tables: {report.table_count}")
    assert report.join_count >= 1, "Should detect JOIN"

    # Complex query with subquery, aggregation, window function
    complex_sql = """
        WITH monthly_sales AS (
            SELECT user_id, DATE_TRUNC('month', created_at) as month,
                   SUM(amount) as total
            FROM orders
            GROUP BY user_id, DATE_TRUNC('month', created_at)
        )
        SELECT u.name, ms.month, ms.total,
               ROW_NUMBER() OVER (PARTITION BY u.id ORDER BY ms.total DESC) as rank
        FROM users u
        INNER JOIN monthly_sales ms ON u.id = ms.user_id
        LEFT JOIN user_preferences up ON u.id = up.user_id
        WHERE ms.total > 1000
        HAVING COUNT(*) > 1
        ORDER BY ms.total DESC
        LIMIT 100
    """
    report = analyzer.analyze(complex_sql)
    print(f"\nComplex query (CTE, window, multiple joins):")
    print(f"  Complexity: {report.complexity_score:.2f} ({report.complexity_level})")
    print(f"  CTEs: {report.cte_count}, Window functions: {report.has_window_functions}")
    print(f"  Aggregation: {report.has_aggregation}, JOINs: {report.join_count}")
    assert report.complexity_level in ["complex", "very_complex"], f"Expected complex, got {report.complexity_level}"
    assert report.has_window_functions, "Should detect window function"
    assert report.cte_count >= 1, "Should detect CTE"

    print("\n✅ Query complexity analyzer tests passed!")


def test_adaptive_performance():
    """Test adaptive performance thresholds."""
    print("\n" + "=" * 60)
    print("TEST: Adaptive Performance Thresholds")
    print("=" * 60)

    scorer = AdaptivePerformanceScorer()

    # Simple SQLite query
    thresholds = scorer.get_thresholds("simple", "sqlite")
    print(f"\nSimple SQLite thresholds:")
    print(f"  Excellent: {thresholds.excellent_ms:.1f}ms")
    print(f"  Good: {thresholds.good_ms:.1f}ms")
    print(f"  Acceptable: {thresholds.acceptable_ms:.1f}ms")

    # Complex BigQuery query
    thresholds_bq = scorer.get_thresholds("complex", "bigquery")
    print(f"\nComplex BigQuery thresholds:")
    print(f"  Excellent: {thresholds_bq.excellent_ms:.1f}ms")
    print(f"  Good: {thresholds_bq.good_ms:.1f}ms")
    print(f"  Acceptable: {thresholds_bq.acceptable_ms:.1f}ms")

    # BigQuery should have much higher thresholds
    assert thresholds_bq.excellent_ms > thresholds.excellent_ms * 10, "BigQuery should have higher thresholds"

    # Score a fast query
    score = scorer.score(5.0, thresholds)
    print(f"\n5ms query on simple SQLite: {score:.2f}")
    assert score == 1.0, "5ms should be excellent"

    # Score a slow query
    score_slow = scorer.score(500.0, thresholds)
    print(f"500ms query on simple SQLite: {score_slow:.2f}")
    assert score_slow < 0.8, "500ms should be below good"

    # Same time on BigQuery complex should score better
    score_bq = scorer.score(500.0, thresholds_bq)
    print(f"500ms query on complex BigQuery: {score_bq:.2f}")
    assert score_bq > score_slow, "Same time should score better on BigQuery"

    print("\n✅ Adaptive performance tests passed!")


def test_weighted_hallucination_scoring():
    """Test weighted hallucination severity scoring."""
    print("\n" + "=" * 60)
    print("TEST: Weighted Hallucination Scoring")
    print("=" * 60)

    scorer = WeightedHallucinationScorer()

    # No hallucinations
    score, details = scorer.score([], [], [])
    print(f"\nNo hallucinations: {score:.2f}")
    assert score == 1.0, "Clean query should score 1.0"

    # One phantom table (most severe)
    score, details = scorer.score(["fake_table"], [], [])
    print(f"One phantom table: {score:.2f}")
    print(f"  Penalty: {details['total_penalty']:.2f}")
    assert score < 0.5, "Phantom table should heavily penalize"

    # One phantom column (less severe)
    score_col, details_col = scorer.score([], ["fake_column"], [])
    print(f"One phantom column: {score_col:.2f}")
    assert score_col > score, "Phantom column should penalize less than table"

    # Multiple hallucinations
    score_multi, details_multi = scorer.score(
        ["fake_table"],
        ["col1", "col2"],
        ["fake_func"]
    )
    print(f"Multiple hallucinations: {score_multi:.2f}")
    print(f"  Total penalty: {details_multi['total_penalty']:.2f}")
    assert score_multi < score, "Multiple hallucinations should score worse"

    print("\n✅ Weighted hallucination scoring tests passed!")


def test_execution_plan_analyzer():
    """Test execution plan analysis."""
    print("\n" + "=" * 60)
    print("TEST: Execution Plan Analyzer")
    print("=" * 60)

    analyzer = ExecutionPlanAnalyzer()

    # Plan with index scan (good)
    good_plan = """
    Index Scan using users_pkey on users  (cost=0.29..8.30 rows=1 width=68)
      Index Cond: (id = 1)
    """
    result = analyzer.analyze(good_plan)
    print(f"\nIndex scan plan:")
    print(f"  Score: {result.plan_score:.2f}")
    print(f"  Has index scan: {result.has_index_scan}")
    assert result.has_index_scan, "Should detect index scan"
    assert result.plan_score >= 0.8, "Index scan should score well"

    # Plan with sequential scan (bad)
    bad_plan = """
    Seq Scan on users  (cost=0.00..12345.00 rows=100000 width=68)
      Filter: (age > 30)
    """
    result_bad = analyzer.analyze(bad_plan)
    print(f"\nSequential scan plan:")
    print(f"  Score: {result_bad.plan_score:.2f}")
    print(f"  Has full table scan: {result_bad.has_full_table_scan}")
    print(f"  Warnings: {result_bad.warnings}")
    assert result_bad.has_full_table_scan, "Should detect seq scan"
    assert result_bad.plan_score < result.plan_score, "Seq scan should score worse"

    print("\n✅ Execution plan analyzer tests passed!")


def test_semantic_accuracy_scorer():
    """Test semantic result accuracy scoring."""
    print("\n" + "=" * 60)
    print("TEST: Semantic Accuracy Scorer")
    print("=" * 60)

    scorer = SemanticAccuracyScorer()

    # Exact match
    expected = [
        {"name": "Alice", "age": 30, "salary": 50000.0},
        {"name": "Bob", "age": 25, "salary": 60000.0},
    ]
    actual = [
        {"name": "Alice", "age": 30, "salary": 50000.0},
        {"name": "Bob", "age": 25, "salary": 60000.0},
    ]
    result = scorer.score(actual, expected)
    print(f"\nExact match:")
    print(f"  Overall: {result.overall_score:.2f}")
    print(f"  Value accuracy: {result.value_accuracy:.2f}")
    assert result.overall_score > 0.95, "Exact match should score high"

    # Partial match (different values)
    actual_partial = [
        {"name": "Alice", "age": 31, "salary": 51000.0},  # Slightly different
        {"name": "Bob", "age": 25, "salary": 60000.0},
    ]
    result_partial = scorer.score(actual_partial, expected)
    print(f"\nPartial match (slightly different values):")
    print(f"  Overall: {result_partial.overall_score:.2f}")
    print(f"  Column scores: {result_partial.column_scores}")
    assert result_partial.overall_score < result.overall_score, "Partial match should score lower"

    # Wrong data
    actual_wrong = [
        {"name": "Charlie", "age": 50, "salary": 100000.0},
        {"name": "Diana", "age": 35, "salary": 80000.0},
    ]
    result_wrong = scorer.score(actual_wrong, expected)
    print(f"\nWrong data:")
    print(f"  Overall: {result_wrong.overall_score:.2f}")
    assert result_wrong.overall_score < result_partial.overall_score, "Wrong data should score worse"

    print("\n✅ Semantic accuracy scorer tests passed!")


def test_error_taxonomy():
    """Test error classification and severity scoring."""
    print("\n" + "=" * 60)
    print("TEST: Error Taxonomy Classifier")
    print("=" * 60)

    classifier = ErrorTaxonomyClassifier()

    # Classify different errors
    errors = [
        "Table 'users' does not exist",
        "Column 'invalid_col' does not exist",
        "syntax error at or near 'SELEC'",
        "permission denied for relation users",
        "query timeout exceeded",
    ]

    print("\nClassifying errors:")
    for error in errors:
        classification = classifier.classify(error)
        print(f"  '{error[:40]}...'")
        print(f"    -> {classification.category.value} (severity: {classification.severity})")

    # Score multiple errors
    score, classifications = classifier.score_errors([
        "Table 'fake' does not exist",
        "Column 'invalid' not found",
    ])
    print(f"\nMultiple errors score: {score:.2f}")
    assert score < 0.5, "Multiple errors should score low"

    # No errors should score 1.0
    score_clean, _ = classifier.score_errors([])
    assert score_clean == 1.0, "No errors should score 1.0"

    print("\n✅ Error taxonomy tests passed!")


def test_best_practices_scorer():
    """Test SQL best practices scoring."""
    print("\n" + "=" * 60)
    print("TEST: SQL Best Practices Scorer")
    print("=" * 60)

    scorer = SQLBestPracticesScorer()

    # Good query
    good_sql = "SELECT id, name, email FROM users WHERE active = 1 LIMIT 100"
    report = scorer.score(good_sql)
    print(f"\nGood query: {good_sql[:50]}...")
    print(f"  Score: {report.score:.2f}")
    print(f"  Violations: {report.violations}")
    assert report.score >= 0.9, "Good query should score high"

    # Query with SELECT *
    select_star = "SELECT * FROM users"
    report_star = scorer.score(select_star)
    print(f"\nSELECT *: {select_star}")
    print(f"  Score: {report_star.score:.2f}")
    print(f"  Violations: {report_star.violations}")
    assert report_star.score < report.score, "SELECT * should score lower"

    # Query with implicit join
    implicit_join = "SELECT * FROM users, orders WHERE users.id = orders.user_id"
    report_implicit = scorer.score(implicit_join)
    print(f"\nImplicit join:")
    print(f"  Score: {report_implicit.score:.2f}")
    print(f"  Violations: {report_implicit.violations}")
    assert "comma joins" in str(report_implicit.violations).lower() or "implicit" in str(report_implicit.violations).lower()

    print("\n✅ SQL best practices tests passed!")


def test_enhanced_scorer_integration():
    """Test full enhanced scorer integration."""
    print("\n" + "=" * 60)
    print("TEST: Enhanced Scorer Integration")
    print("=" * 60)

    scorer = EnhancedScorer()

    # Create mock execution result
    execution_result = ExecutionResult(
        success=True,
        data=[
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ],
        columns=["name", "age"],
        rows_returned=2,
        execution_time_ms=15.0,
        is_valid=True,
        validation_errors=[],
        validation_warnings=[],
        query_type="SELECT",
        tables_accessed=["users"],
        columns_accessed=["name", "age"],
        insights=[],
        summary="Returned 2 rows",
    )

    # Create comparison result
    comparison = ComparisonResult(
        is_match=True,
        match_score=1.0,
        row_count_match=True,
        column_count_match=True,
    )

    # Score with all features
    sql = "SELECT name, age FROM users WHERE active = 1"
    expected = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]

    score = scorer.score(
        comparison=comparison,
        execution_result=execution_result,
        sql=sql,
        dialect="sqlite",
        expected_results=expected,
    )

    print(f"\nEnhanced score for valid query:")
    print(f"  Overall: {score.overall:.2%}")
    print(f"  Correctness: {score.correctness:.2%}")
    print(f"  Efficiency: {score.efficiency:.2%}")
    print(f"  Safety: {score.safety:.2%}")
    print(f"  Semantic Accuracy: {score.semantic_accuracy_score:.2%}")
    print(f"  Best Practices: {score.best_practices_score:.2%}")
    print(f"  Query Complexity: {score.query_complexity_score:.2f}")

    assert score.overall > 0.9, "Valid query should score high"

    # Test with hallucinations
    execution_result_bad = ExecutionResult(
        success=False,
        data=[],
        is_valid=False,
        validation_errors=["Table 'fake_users' does not exist"],
        query_type="SELECT",
        tables_accessed=["fake_users"],
    )
    comparison_bad = ComparisonResult(is_match=False, match_score=0.0)

    score_bad = scorer.score(
        comparison=comparison_bad,
        execution_result=execution_result_bad,
        sql="SELECT * FROM fake_users",
        dialect="sqlite",
    )

    print(f"\nEnhanced score for invalid query:")
    print(f"  Overall: {score_bad.overall:.2%}")
    print(f"  Safety: {score_bad.safety:.2%}")
    print(f"  Hallucination details: {score_bad.hallucination_details.get('total_penalty', 0):.2f}")

    assert score_bad.overall < 0.3, "Invalid query should score low"

    print("\n✅ Enhanced scorer integration tests passed!")


def test_scorer_presets():
    """Test different scorer presets."""
    print("\n" + "=" * 60)
    print("TEST: Scorer Presets")
    print("=" * 60)

    presets = ["default", "strict", "performance", "quality"]

    for preset in presets:
        scorer = create_enhanced_scorer(preset)
        print(f"\n{preset.upper()} preset weights:")
        for dim, weight in scorer.weights.items():
            print(f"  {dim}: {weight:.1%}")

    print("\n✅ Scorer preset tests passed!")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ENHANCED SCORING COMPONENT TESTS")
    print("=" * 60)

    try:
        test_query_complexity_analyzer()
        test_adaptive_performance()
        test_weighted_hallucination_scoring()
        test_execution_plan_analyzer()
        test_semantic_accuracy_scorer()
        test_error_taxonomy()
        test_best_practices_scorer()
        test_enhanced_scorer_integration()
        test_scorer_presets()

        print("\n" + "=" * 60)
        print("ALL ENHANCED SCORING TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
