"""
Advanced Scoring Components for SQL Evaluation

Provides more accurate scoring through:
1. Query Complexity Analysis
2. Adaptive Performance Thresholds
3. Hallucination Severity Levels
4. Execution Plan Analysis
5. Semantic Result Accuracy
6. Dialect-Specific Efficiency Curves
7. Error Taxonomy with Severity
8. SQL Best Practices Scoring
"""

import re
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum


# =============================================================================
# 1. QUERY COMPLEXITY SCORING
# =============================================================================

@dataclass
class QueryComplexityReport:
    """Detailed breakdown of query complexity."""
    table_count: int = 0
    join_count: int = 0
    subquery_count: int = 0
    cte_count: int = 0
    has_aggregation: bool = False
    has_window_functions: bool = False
    has_distinct: bool = False
    has_union: bool = False
    has_case_when: bool = False
    where_condition_count: int = 0
    order_by_count: int = 0
    group_by_count: int = 0

    complexity_score: float = 0.0
    complexity_level: str = "simple"  # simple, moderate, complex, very_complex

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_count": self.table_count,
            "join_count": self.join_count,
            "subquery_count": self.subquery_count,
            "cte_count": self.cte_count,
            "has_aggregation": self.has_aggregation,
            "has_window_functions": self.has_window_functions,
            "has_distinct": self.has_distinct,
            "has_union": self.has_union,
            "has_case_when": self.has_case_when,
            "where_condition_count": self.where_condition_count,
            "order_by_count": self.order_by_count,
            "group_by_count": self.group_by_count,
            "complexity_score": self.complexity_score,
            "complexity_level": self.complexity_level,
        }


class QueryComplexityAnalyzer:
    """
    Analyzes SQL query complexity for adaptive scoring.

    Complexity factors:
    - Number of tables accessed
    - JOIN operations
    - Subqueries and CTEs
    - Aggregations and window functions
    - DISTINCT, UNION operations
    - WHERE condition complexity
    """

    # Complexity weights for each factor
    WEIGHTS = {
        "table": 0.08,           # Per table
        "join": 0.12,            # Per JOIN
        "subquery": 0.15,        # Per subquery
        "cte": 0.10,             # Per CTE
        "aggregation": 0.10,     # GROUP BY/HAVING
        "window_function": 0.15, # Window functions
        "distinct": 0.05,        # DISTINCT
        "union": 0.10,           # UNION/INTERSECT/EXCEPT
        "case_when": 0.05,       # CASE expressions
        "where_condition": 0.03, # Per WHERE condition
        "order_by": 0.02,        # Per ORDER BY column
        "group_by": 0.03,        # Per GROUP BY column
    }

    COMPLEXITY_LEVELS = {
        (0.0, 0.2): "simple",
        (0.2, 0.4): "moderate",
        (0.4, 0.7): "complex",
        (0.7, 1.0): "very_complex",
    }

    def analyze(self, sql: str, parsed_info: Optional[Dict] = None) -> QueryComplexityReport:
        """
        Analyze query complexity.

        Args:
            sql: Raw SQL string
            parsed_info: Optional dict with pre-parsed info (tables, columns, etc.)

        Returns:
            QueryComplexityReport with detailed breakdown
        """
        report = QueryComplexityReport()
        sql_upper = sql.upper()

        # Count tables (from parsed info or regex)
        if parsed_info and "tables_accessed" in parsed_info:
            report.table_count = len(parsed_info["tables_accessed"])
        else:
            report.table_count = self._count_tables(sql_upper)

        # Count JOINs
        report.join_count = self._count_joins(sql_upper)

        # Count subqueries
        report.subquery_count = self._count_subqueries(sql)

        # Count CTEs
        report.cte_count = self._count_ctes(sql_upper)

        # Check for aggregation
        report.has_aggregation = self._has_aggregation(sql_upper)

        # Check for window functions
        report.has_window_functions = self._has_window_functions(sql_upper)

        # Check for DISTINCT
        report.has_distinct = "SELECT DISTINCT" in sql_upper or " DISTINCT " in sql_upper

        # Check for UNION/INTERSECT/EXCEPT
        report.has_union = any(op in sql_upper for op in ["UNION", "INTERSECT", "EXCEPT"])

        # Check for CASE WHEN
        report.has_case_when = "CASE " in sql_upper and " WHEN " in sql_upper

        # Count WHERE conditions (approximate by AND/OR)
        report.where_condition_count = self._count_where_conditions(sql_upper)

        # Count ORDER BY columns
        report.order_by_count = self._count_order_by(sql_upper)

        # Count GROUP BY columns
        report.group_by_count = self._count_group_by(sql_upper)

        # Calculate complexity score
        report.complexity_score = self._calculate_score(report)

        # Determine complexity level
        report.complexity_level = self._get_complexity_level(report.complexity_score)

        return report

    def _count_tables(self, sql_upper: str) -> int:
        """Count tables referenced in FROM and JOIN clauses."""
        # Simple heuristic: count FROM and JOIN occurrences
        from_count = sql_upper.count(" FROM ")
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        return max(1, from_count + join_count)

    def _count_joins(self, sql_upper: str) -> int:
        """Count JOIN operations."""
        patterns = [
            r'\bINNER\s+JOIN\b',
            r'\bLEFT\s+(?:OUTER\s+)?JOIN\b',
            r'\bRIGHT\s+(?:OUTER\s+)?JOIN\b',
            r'\bFULL\s+(?:OUTER\s+)?JOIN\b',
            r'\bCROSS\s+JOIN\b',
            r'\bNATURAL\s+JOIN\b',
            r'(?<!\w)JOIN\b(?!\s+(?:INNER|LEFT|RIGHT|FULL|CROSS|NATURAL))',
        ]
        total = 0
        for pattern in patterns:
            total += len(re.findall(pattern, sql_upper))
        return total

    def _count_subqueries(self, sql: str) -> int:
        """Count nested SELECT statements (subqueries)."""
        # Count SELECT occurrences minus 1 (the main query)
        select_count = len(re.findall(r'\bSELECT\b', sql, re.IGNORECASE))
        return max(0, select_count - 1)

    def _count_ctes(self, sql_upper: str) -> int:
        """Count Common Table Expressions (WITH clauses)."""
        if "WITH " not in sql_upper:
            return 0
        # Count AS ( patterns after WITH
        with_section = sql_upper.split("WITH ", 1)[-1]
        if " SELECT " in with_section:
            with_section = with_section.split(" SELECT ", 1)[0]
        return len(re.findall(r'\bAS\s*\(', with_section))

    def _has_aggregation(self, sql_upper: str) -> bool:
        """Check for aggregation functions or GROUP BY."""
        agg_functions = ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX(", "GROUP_CONCAT(", "STRING_AGG("]
        has_agg_func = any(func in sql_upper for func in agg_functions)
        has_group_by = "GROUP BY" in sql_upper
        return has_agg_func or has_group_by

    def _has_window_functions(self, sql_upper: str) -> bool:
        """Check for window functions."""
        window_keywords = [" OVER(", " OVER (", "ROW_NUMBER(", "RANK(", "DENSE_RANK(",
                          "LEAD(", "LAG(", "FIRST_VALUE(", "LAST_VALUE(", "NTILE("]
        return any(kw in sql_upper for kw in window_keywords)

    def _count_where_conditions(self, sql_upper: str) -> int:
        """Approximate WHERE clause complexity."""
        if "WHERE " not in sql_upper:
            return 0
        # Extract WHERE clause (until GROUP BY, ORDER BY, LIMIT, or end)
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP BY|ORDER BY|LIMIT|HAVING|$)', sql_upper, re.DOTALL)
        if not where_match:
            return 1
        where_clause = where_match.group(1)
        # Count conditions by AND/OR
        and_count = where_clause.count(" AND ")
        or_count = where_clause.count(" OR ")
        return 1 + and_count + or_count

    def _count_order_by(self, sql_upper: str) -> int:
        """Count ORDER BY columns."""
        if "ORDER BY" not in sql_upper:
            return 0
        order_match = re.search(r'ORDER BY\s+(.+?)(?:LIMIT|OFFSET|$)', sql_upper, re.DOTALL)
        if not order_match:
            return 1
        return order_match.group(1).count(",") + 1

    def _count_group_by(self, sql_upper: str) -> int:
        """Count GROUP BY columns."""
        if "GROUP BY" not in sql_upper:
            return 0
        group_match = re.search(r'GROUP BY\s+(.+?)(?:HAVING|ORDER BY|LIMIT|$)', sql_upper, re.DOTALL)
        if not group_match:
            return 1
        return group_match.group(1).count(",") + 1

    def _calculate_score(self, report: QueryComplexityReport) -> float:
        """Calculate overall complexity score (0.0 to 1.0)."""
        score = 0.0

        # Table complexity (diminishing returns after 3)
        score += min(report.table_count, 5) * self.WEIGHTS["table"]

        # Join complexity
        score += min(report.join_count, 5) * self.WEIGHTS["join"]

        # Subquery complexity
        score += min(report.subquery_count, 3) * self.WEIGHTS["subquery"]

        # CTE complexity
        score += min(report.cte_count, 3) * self.WEIGHTS["cte"]

        # Feature flags
        if report.has_aggregation:
            score += self.WEIGHTS["aggregation"]
        if report.has_window_functions:
            score += self.WEIGHTS["window_function"]
        if report.has_distinct:
            score += self.WEIGHTS["distinct"]
        if report.has_union:
            score += self.WEIGHTS["union"]
        if report.has_case_when:
            score += self.WEIGHTS["case_when"]

        # Condition complexity
        score += min(report.where_condition_count, 5) * self.WEIGHTS["where_condition"]
        score += min(report.order_by_count, 3) * self.WEIGHTS["order_by"]
        score += min(report.group_by_count, 3) * self.WEIGHTS["group_by"]

        return min(1.0, score)

    def _get_complexity_level(self, score: float) -> str:
        """Map score to complexity level."""
        for (low, high), level in self.COMPLEXITY_LEVELS.items():
            if low <= score < high:
                return level
        return "very_complex"


# =============================================================================
# 2. ADAPTIVE PERFORMANCE THRESHOLDS
# =============================================================================

@dataclass
class PerformanceThresholds:
    """Performance thresholds adjusted for query complexity."""
    excellent_ms: float
    good_ms: float
    acceptable_ms: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "excellent": self.excellent_ms,
            "good": self.good_ms,
            "acceptable": self.acceptable_ms,
        }


class AdaptivePerformanceScorer:
    """
    Scores query performance with adaptive thresholds based on:
    - Query complexity
    - Dialect characteristics
    - Data volume (if known)
    """

    # Base thresholds (for simple queries)
    BASE_THRESHOLDS = {
        "excellent": 10.0,
        "good": 100.0,
        "acceptable": 1000.0,
    }

    # Dialect-specific multipliers
    DIALECT_MULTIPLIERS = {
        "sqlite": 0.5,       # Fast for small data
        "duckdb": 1.0,       # Analytics optimized
        "postgresql": 1.5,   # Network overhead
        "mysql": 1.5,        # Similar to PostgreSQL
        "bigquery": 10.0,    # Cloud latency
        "snowflake": 10.0,   # Cloud latency
    }

    # Complexity multipliers
    COMPLEXITY_MULTIPLIERS = {
        "simple": 1.0,
        "moderate": 2.0,
        "complex": 4.0,
        "very_complex": 8.0,
    }

    def get_thresholds(
        self,
        complexity_level: str = "simple",
        dialect: str = "sqlite",
        row_estimate: Optional[int] = None,
    ) -> PerformanceThresholds:
        """
        Get adaptive thresholds for the given context.

        Args:
            complexity_level: Query complexity level
            dialect: Database dialect
            row_estimate: Estimated number of rows to process

        Returns:
            PerformanceThresholds adjusted for context
        """
        # Start with base thresholds
        excellent = self.BASE_THRESHOLDS["excellent"]
        good = self.BASE_THRESHOLDS["good"]
        acceptable = self.BASE_THRESHOLDS["acceptable"]

        # Apply complexity multiplier
        complexity_mult = self.COMPLEXITY_MULTIPLIERS.get(complexity_level, 1.0)
        excellent *= complexity_mult
        good *= complexity_mult
        acceptable *= complexity_mult

        # Apply dialect multiplier
        dialect_mult = self.DIALECT_MULTIPLIERS.get(dialect.lower(), 1.0)
        excellent *= dialect_mult
        good *= dialect_mult
        acceptable *= dialect_mult

        # Apply row estimate adjustment (if known)
        if row_estimate is not None and row_estimate > 1000:
            row_mult = math.log10(row_estimate / 1000) + 1
            excellent *= row_mult
            good *= row_mult
            acceptable *= row_mult

        return PerformanceThresholds(
            excellent_ms=excellent,
            good_ms=good,
            acceptable_ms=acceptable,
        )

    def score(
        self,
        execution_time_ms: float,
        thresholds: PerformanceThresholds,
    ) -> float:
        """
        Score execution time against adaptive thresholds.

        Returns:
            Score from 0.0 to 1.0
        """
        if execution_time_ms <= thresholds.excellent_ms:
            return 1.0
        elif execution_time_ms <= thresholds.good_ms:
            # Linear interpolation: 1.0 -> 0.8
            ratio = (execution_time_ms - thresholds.excellent_ms) / \
                    (thresholds.good_ms - thresholds.excellent_ms)
            return 1.0 - (0.2 * ratio)
        elif execution_time_ms <= thresholds.acceptable_ms:
            # Linear interpolation: 0.8 -> 0.5
            ratio = (execution_time_ms - thresholds.good_ms) / \
                    (thresholds.acceptable_ms - thresholds.good_ms)
            return 0.8 - (0.3 * ratio)
        else:
            # Beyond acceptable: 0.5 -> 0.0
            excess = execution_time_ms - thresholds.acceptable_ms
            return max(0.0, 0.5 - (excess / (thresholds.acceptable_ms * 10)))


# =============================================================================
# 3. HALLUCINATION SEVERITY LEVELS
# =============================================================================

class HallucinationType(Enum):
    """Types of SQL hallucinations with severity levels."""
    PHANTOM_TABLE = "phantom_table"
    PHANTOM_COLUMN = "phantom_column"
    PHANTOM_FUNCTION = "phantom_function"
    WRONG_COLUMN_TYPE = "wrong_column_type"
    INVALID_JOIN_CONDITION = "invalid_join_condition"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"


@dataclass
class HallucinationSeverity:
    """Severity configuration for hallucination types."""

    # Severity weights (1.0 = most severe)
    SEVERITY_WEIGHTS = {
        HallucinationType.PHANTOM_TABLE: 1.0,           # Query will fail
        HallucinationType.PHANTOM_COLUMN: 0.8,          # Query will fail
        HallucinationType.PHANTOM_FUNCTION: 0.6,        # May work in some dialects
        HallucinationType.INVALID_JOIN_CONDITION: 0.7,  # Wrong results
        HallucinationType.WRONG_COLUMN_TYPE: 0.4,       # Subtle error
        HallucinationType.AMBIGUOUS_REFERENCE: 0.3,     # May work but unclear
    }


class WeightedHallucinationScorer:
    """
    Scores hallucinations with severity weighting.

    More severe hallucinations (phantom tables) have higher impact
    than less severe ones (ambiguous references).
    """

    def __init__(self, severity_weights: Optional[Dict[HallucinationType, float]] = None):
        self.severity_weights = severity_weights or HallucinationSeverity.SEVERITY_WEIGHTS

    def score(
        self,
        phantom_tables: List[str],
        phantom_columns: List[str],
        phantom_functions: List[str],
        additional_issues: Optional[Dict[HallucinationType, List[str]]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate weighted hallucination score.

        Args:
            phantom_tables: List of non-existent tables
            phantom_columns: List of non-existent columns
            phantom_functions: List of invalid functions
            additional_issues: Other hallucination types

        Returns:
            Tuple of (score 0-1 where 1 is clean, details dict)
        """
        weighted_penalty = 0.0
        details = {
            "phantom_tables": phantom_tables,
            "phantom_columns": phantom_columns,
            "phantom_functions": phantom_functions,
            "penalties": {},
        }

        # Calculate penalties
        if phantom_tables:
            penalty = len(phantom_tables) * self.severity_weights[HallucinationType.PHANTOM_TABLE]
            weighted_penalty += penalty
            details["penalties"]["phantom_tables"] = penalty

        if phantom_columns:
            penalty = len(phantom_columns) * self.severity_weights[HallucinationType.PHANTOM_COLUMN]
            weighted_penalty += penalty
            details["penalties"]["phantom_columns"] = penalty

        if phantom_functions:
            penalty = len(phantom_functions) * self.severity_weights[HallucinationType.PHANTOM_FUNCTION]
            weighted_penalty += penalty
            details["penalties"]["phantom_functions"] = penalty

        # Process additional issues
        if additional_issues:
            for issue_type, items in additional_issues.items():
                if items and issue_type in self.severity_weights:
                    penalty = len(items) * self.severity_weights[issue_type]
                    weighted_penalty += penalty
                    details["penalties"][issue_type.value] = penalty

        details["total_penalty"] = weighted_penalty

        # Convert penalty to score (0-1 where 1 is clean)
        # Use diminishing returns for multiple issues
        if weighted_penalty == 0:
            score = 1.0
        elif weighted_penalty < 1:
            score = 1.0 - (weighted_penalty * 0.6)
        elif weighted_penalty < 2:
            score = 0.4 - ((weighted_penalty - 1) * 0.3)
        else:
            score = max(0.0, 0.1 - ((weighted_penalty - 2) * 0.05))

        details["final_score"] = score
        return score, details


# =============================================================================
# 4. EXECUTION PLAN ANALYSIS
# =============================================================================

@dataclass
class PlanAnalysisResult:
    """Result of execution plan analysis."""
    plan_score: float = 1.0
    has_full_table_scan: bool = False
    has_index_scan: bool = False
    missing_indexes: List[str] = field(default_factory=list)
    estimated_rows: int = 0
    estimated_cost: float = 0.0
    warnings: List[str] = field(default_factory=list)
    optimizations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_score": self.plan_score,
            "has_full_table_scan": self.has_full_table_scan,
            "has_index_scan": self.has_index_scan,
            "missing_indexes": self.missing_indexes,
            "estimated_rows": self.estimated_rows,
            "estimated_cost": self.estimated_cost,
            "warnings": self.warnings,
            "optimizations": self.optimizations,
        }


class ExecutionPlanAnalyzer:
    """
    Analyzes SQL execution plans for optimization opportunities.

    Supports PostgreSQL EXPLAIN output format.
    Can be extended for other dialects.
    """

    # Plan patterns indicating issues
    SCAN_PATTERNS = {
        "full_scan": [
            r"Seq Scan",
            r"TABLE SCAN",
            r"FULL TABLE SCAN",
            r"Table Scan",
        ],
        "index_scan": [
            r"Index Scan",
            r"Index Only Scan",
            r"Bitmap Index Scan",
            r"INDEX SEEK",
        ],
    }

    # Cost thresholds
    COST_THRESHOLDS = {
        "low": 100,
        "medium": 1000,
        "high": 10000,
    }

    def analyze(
        self,
        plan_text: str,
        dialect: str = "postgresql",
    ) -> PlanAnalysisResult:
        """
        Analyze execution plan text.

        Args:
            plan_text: Output from EXPLAIN/EXPLAIN ANALYZE
            dialect: Database dialect

        Returns:
            PlanAnalysisResult with findings
        """
        result = PlanAnalysisResult()

        if not plan_text:
            return result

        plan_upper = plan_text.upper()

        # Check for full table scans
        for pattern in self.SCAN_PATTERNS["full_scan"]:
            if re.search(pattern, plan_text, re.IGNORECASE):
                result.has_full_table_scan = True
                result.warnings.append(f"Full table scan detected: {pattern}")

        # Check for index usage
        for pattern in self.SCAN_PATTERNS["index_scan"]:
            if re.search(pattern, plan_text, re.IGNORECASE):
                result.has_index_scan = True

        # Extract cost estimates (PostgreSQL format)
        cost_match = re.search(r"cost=[\d.]+\.\.(\d+\.?\d*)", plan_text)
        if cost_match:
            result.estimated_cost = float(cost_match.group(1))

        # Extract row estimates
        rows_match = re.search(r"rows=(\d+)", plan_text)
        if rows_match:
            result.estimated_rows = int(rows_match.group(1))

        # Calculate plan score
        result.plan_score = self._calculate_plan_score(result)

        # Generate optimization suggestions
        result.optimizations = self._generate_optimizations(result)

        return result

    def _calculate_plan_score(self, result: PlanAnalysisResult) -> float:
        """Calculate overall plan quality score."""
        score = 1.0

        # Penalize full table scans
        if result.has_full_table_scan:
            score -= 0.3

        # Reward index usage
        if result.has_index_scan:
            score += 0.1

        # Penalize high cost
        if result.estimated_cost > self.COST_THRESHOLDS["high"]:
            score -= 0.2
        elif result.estimated_cost > self.COST_THRESHOLDS["medium"]:
            score -= 0.1

        # Penalize processing many rows
        if result.estimated_rows > 100000:
            score -= 0.15
        elif result.estimated_rows > 10000:
            score -= 0.05

        return max(0.0, min(1.0, score))

    def _generate_optimizations(self, result: PlanAnalysisResult) -> List[str]:
        """Generate optimization suggestions."""
        optimizations = []

        if result.has_full_table_scan and not result.has_index_scan:
            optimizations.append("Consider adding an index on filtered columns")

        if result.estimated_rows > 10000:
            optimizations.append("Consider adding LIMIT or more specific WHERE conditions")

        if result.estimated_cost > self.COST_THRESHOLDS["medium"]:
            optimizations.append("Query cost is high - review join conditions and indexes")

        return optimizations


# =============================================================================
# 5. SEMANTIC RESULT ACCURACY
# =============================================================================

@dataclass
class SemanticAccuracyResult:
    """Result of semantic accuracy analysis."""
    overall_score: float = 0.0
    value_accuracy: float = 0.0
    distribution_similarity: float = 0.0
    null_handling_score: float = 0.0
    type_consistency_score: float = 0.0
    column_scores: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "value_accuracy": self.value_accuracy,
            "distribution_similarity": self.distribution_similarity,
            "null_handling_score": self.null_handling_score,
            "type_consistency_score": self.type_consistency_score,
            "column_scores": self.column_scores,
            "details": self.details,
        }


class SemanticAccuracyScorer:
    """
    Scores result accuracy beyond row/column matching.

    Analyzes:
    - Value accuracy (actual values match expected)
    - Distribution similarity (for numeric columns)
    - Null handling
    - Type consistency
    """

    def __init__(self, numeric_tolerance: float = 1e-6):
        self.numeric_tolerance = numeric_tolerance

    def score(
        self,
        actual: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
    ) -> SemanticAccuracyResult:
        """
        Calculate semantic accuracy between actual and expected results.

        Args:
            actual: Actual query results
            expected: Expected results

        Returns:
            SemanticAccuracyResult with detailed breakdown
        """
        result = SemanticAccuracyResult()

        if not actual or not expected:
            result.details["error"] = "Empty results"
            return result

        # Get common columns
        actual_cols = set(actual[0].keys()) if actual else set()
        expected_cols = set(expected[0].keys()) if expected else set()
        common_cols = actual_cols & expected_cols

        if not common_cols:
            result.details["error"] = "No common columns"
            return result

        # Score each column
        column_scores = {}
        for col in common_cols:
            actual_values = [row.get(col) for row in actual]
            expected_values = [row.get(col) for row in expected]

            col_score = self._score_column(actual_values, expected_values, col)
            column_scores[col] = col_score

        result.column_scores = column_scores

        # Calculate aggregate scores
        result.value_accuracy = self._calculate_value_accuracy(actual, expected, common_cols)
        result.distribution_similarity = self._calculate_distribution_similarity(actual, expected, common_cols)
        result.null_handling_score = self._calculate_null_score(actual, expected, common_cols)
        result.type_consistency_score = self._calculate_type_consistency(actual, expected, common_cols)

        # Overall score (weighted average)
        result.overall_score = (
            0.50 * result.value_accuracy +
            0.20 * result.distribution_similarity +
            0.15 * result.null_handling_score +
            0.15 * result.type_consistency_score
        )

        result.details = {
            "common_columns": list(common_cols),
            "actual_row_count": len(actual),
            "expected_row_count": len(expected),
        }

        return result

    def _score_column(
        self,
        actual_values: List[Any],
        expected_values: List[Any],
        column_name: str,
    ) -> float:
        """Score a single column's accuracy."""
        if not expected_values:
            return 1.0 if not actual_values else 0.0

        # Check if numeric
        if self._is_numeric_column(expected_values):
            return self._score_numeric_column(actual_values, expected_values)
        else:
            return self._score_categorical_column(actual_values, expected_values)

    def _is_numeric_column(self, values: List[Any]) -> bool:
        """Check if column contains numeric values."""
        non_null = [v for v in values if v is not None]
        if not non_null:
            return False
        return all(isinstance(v, (int, float)) for v in non_null)

    def _score_numeric_column(
        self,
        actual: List[Any],
        expected: List[Any],
    ) -> float:
        """Score numeric column accuracy."""
        actual_nums = [v for v in actual if v is not None and isinstance(v, (int, float))]
        expected_nums = [v for v in expected if v is not None and isinstance(v, (int, float))]

        if not expected_nums:
            return 1.0 if not actual_nums else 0.0

        if not actual_nums:
            return 0.0

        # Compare means
        actual_mean = sum(actual_nums) / len(actual_nums)
        expected_mean = sum(expected_nums) / len(expected_nums)

        if expected_mean == 0:
            mean_score = 1.0 if abs(actual_mean) < self.numeric_tolerance else 0.0
        else:
            mean_diff = abs(actual_mean - expected_mean) / abs(expected_mean)
            mean_score = max(0, 1 - mean_diff)

        # Compare ranges
        actual_range = max(actual_nums) - min(actual_nums) if len(actual_nums) > 1 else 0
        expected_range = max(expected_nums) - min(expected_nums) if len(expected_nums) > 1 else 0

        if expected_range == 0:
            range_score = 1.0 if actual_range == 0 else 0.5
        else:
            range_diff = abs(actual_range - expected_range) / expected_range
            range_score = max(0, 1 - range_diff)

        return 0.7 * mean_score + 0.3 * range_score

    def _score_categorical_column(
        self,
        actual: List[Any],
        expected: List[Any],
    ) -> float:
        """Score categorical column accuracy."""
        actual_set = set(str(v).lower() if v is not None else None for v in actual)
        expected_set = set(str(v).lower() if v is not None else None for v in expected)

        if not expected_set:
            return 1.0 if not actual_set else 0.0

        # Jaccard similarity
        intersection = len(actual_set & expected_set)
        union = len(actual_set | expected_set)

        return intersection / union if union > 0 else 0.0

    def _calculate_value_accuracy(
        self,
        actual: List[Dict],
        expected: List[Dict],
        columns: Set[str],
    ) -> float:
        """Calculate overall value matching accuracy."""
        if not expected:
            return 1.0 if not actual else 0.0

        total_matches = 0
        total_comparisons = 0

        for exp_row in expected:
            best_match = 0.0
            for act_row in actual:
                match_count = sum(
                    1 for col in columns
                    if self._values_match(act_row.get(col), exp_row.get(col))
                )
                best_match = max(best_match, match_count / len(columns))
            total_matches += best_match
            total_comparisons += 1

        return total_matches / total_comparisons if total_comparisons > 0 else 0.0

    def _values_match(self, actual: Any, expected: Any) -> bool:
        """Check if two values match."""
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False

        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return abs(actual - expected) <= self.numeric_tolerance

        return str(actual).lower() == str(expected).lower()

    def _calculate_distribution_similarity(
        self,
        actual: List[Dict],
        expected: List[Dict],
        columns: Set[str],
    ) -> float:
        """Calculate distribution similarity for numeric columns."""
        similarities = []

        for col in columns:
            actual_vals = [row.get(col) for row in actual if row.get(col) is not None]
            expected_vals = [row.get(col) for row in expected if row.get(col) is not None]

            if not self._is_numeric_column(expected_vals):
                continue

            if not actual_vals or not expected_vals:
                similarities.append(0.0)
                continue

            # Compare basic statistics
            actual_vals = [v for v in actual_vals if isinstance(v, (int, float))]
            expected_vals = [v for v in expected_vals if isinstance(v, (int, float))]

            if not actual_vals or not expected_vals:
                continue

            actual_mean = sum(actual_vals) / len(actual_vals)
            expected_mean = sum(expected_vals) / len(expected_vals)

            if expected_mean != 0:
                mean_sim = 1 - min(1, abs(actual_mean - expected_mean) / abs(expected_mean))
            else:
                mean_sim = 1.0 if actual_mean == 0 else 0.0

            similarities.append(mean_sim)

        return sum(similarities) / len(similarities) if similarities else 1.0

    def _calculate_null_score(
        self,
        actual: List[Dict],
        expected: List[Dict],
        columns: Set[str],
    ) -> float:
        """Score null handling consistency."""
        if not expected:
            return 1.0

        scores = []
        for col in columns:
            actual_nulls = sum(1 for row in actual if row.get(col) is None)
            expected_nulls = sum(1 for row in expected if row.get(col) is None)

            actual_ratio = actual_nulls / len(actual) if actual else 0
            expected_ratio = expected_nulls / len(expected)

            # Penalize large differences in null ratios
            diff = abs(actual_ratio - expected_ratio)
            scores.append(1 - diff)

        return sum(scores) / len(scores) if scores else 1.0

    def _calculate_type_consistency(
        self,
        actual: List[Dict],
        expected: List[Dict],
        columns: Set[str],
    ) -> float:
        """Score type consistency between results."""
        if not expected or not actual:
            return 1.0

        scores = []
        for col in columns:
            actual_types = set(type(row.get(col)).__name__ for row in actual if row.get(col) is not None)
            expected_types = set(type(row.get(col)).__name__ for row in expected if row.get(col) is not None)

            if not expected_types:
                scores.append(1.0)
                continue

            # Check type overlap
            if actual_types == expected_types:
                scores.append(1.0)
            elif actual_types & expected_types:
                scores.append(0.7)
            else:
                # Different types - check compatibility
                scores.append(0.3)

        return sum(scores) / len(scores) if scores else 1.0


# =============================================================================
# 6. ERROR TAXONOMY
# =============================================================================

class ErrorCategory(Enum):
    """Categories of SQL errors with severity."""
    SYNTAX_ERROR = "syntax_error"
    TABLE_NOT_FOUND = "table_not_found"
    COLUMN_NOT_FOUND = "column_not_found"
    TYPE_MISMATCH = "type_mismatch"
    AMBIGUOUS_COLUMN = "ambiguous_column"
    PERMISSION_DENIED = "permission_denied"
    CONSTRAINT_VIOLATION = "constraint_violation"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RESOURCE_LIMIT = "resource_limit"
    UNKNOWN = "unknown"


@dataclass
class ErrorClassification:
    """Classified error with severity."""
    category: ErrorCategory
    severity: float  # 0.0 to 1.0
    message: str
    recoverable: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "message": self.message,
            "recoverable": self.recoverable,
        }


class ErrorTaxonomyClassifier:
    """
    Classifies SQL errors by category and severity.

    Provides more nuanced scoring than simple error counting.
    """

    # Error patterns and their classifications
    ERROR_PATTERNS = {
        ErrorCategory.SYNTAX_ERROR: {
            "patterns": [
                r"syntax error",
                r"parse error",
                r"unexpected token",
                r"invalid syntax",
            ],
            "severity": 1.0,
            "recoverable": False,
        },
        ErrorCategory.TABLE_NOT_FOUND: {
            "patterns": [
                r"table .* does not exist",
                r"no such table",
                r"unknown table",
                r"relation .* does not exist",
            ],
            "severity": 0.9,
            "recoverable": False,
        },
        ErrorCategory.COLUMN_NOT_FOUND: {
            "patterns": [
                r"column .* does not exist",
                r"no such column",
                r"unknown column",
                r"field .* not found",
            ],
            "severity": 0.8,
            "recoverable": False,
        },
        ErrorCategory.TYPE_MISMATCH: {
            "patterns": [
                r"type mismatch",
                r"invalid input syntax for type",
                r"cannot cast",
                r"incompatible types",
            ],
            "severity": 0.6,
            "recoverable": True,
        },
        ErrorCategory.AMBIGUOUS_COLUMN: {
            "patterns": [
                r"ambiguous column",
                r"column reference .* is ambiguous",
            ],
            "severity": 0.5,
            "recoverable": True,
        },
        ErrorCategory.PERMISSION_DENIED: {
            "patterns": [
                r"permission denied",
                r"access denied",
                r"unauthorized",
            ],
            "severity": 0.7,
            "recoverable": False,
        },
        ErrorCategory.CONSTRAINT_VIOLATION: {
            "patterns": [
                r"constraint violation",
                r"duplicate key",
                r"unique constraint",
                r"foreign key",
            ],
            "severity": 0.6,
            "recoverable": True,
        },
        ErrorCategory.TIMEOUT: {
            "patterns": [
                r"timeout",
                r"query cancelled",
                r"statement timeout",
            ],
            "severity": 0.4,
            "recoverable": True,
        },
        ErrorCategory.CONNECTION_ERROR: {
            "patterns": [
                r"connection refused",
                r"connection reset",
                r"could not connect",
            ],
            "severity": 0.5,
            "recoverable": True,
        },
        ErrorCategory.RESOURCE_LIMIT: {
            "patterns": [
                r"out of memory",
                r"resource limit",
                r"too many connections",
            ],
            "severity": 0.4,
            "recoverable": True,
        },
    }

    def classify(self, error_message: str) -> ErrorClassification:
        """
        Classify an error message.

        Args:
            error_message: The error message to classify

        Returns:
            ErrorClassification with category and severity
        """
        error_lower = error_message.lower()

        for category, config in self.ERROR_PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    return ErrorClassification(
                        category=category,
                        severity=config["severity"],
                        message=error_message,
                        recoverable=config["recoverable"],
                    )

        # Unknown error
        return ErrorClassification(
            category=ErrorCategory.UNKNOWN,
            severity=0.7,  # Default severity for unknown errors
            message=error_message,
            recoverable=False,
        )

    def classify_multiple(self, errors: List[str]) -> List[ErrorClassification]:
        """Classify multiple error messages."""
        return [self.classify(e) for e in errors]

    def score_errors(self, errors: List[str]) -> Tuple[float, List[ErrorClassification]]:
        """
        Score a list of errors by severity.

        Returns:
            Tuple of (score 0-1 where 1 is no errors, classified errors)
        """
        if not errors:
            return 1.0, []

        classifications = self.classify_multiple(errors)

        # Calculate weighted severity
        total_severity = sum(c.severity for c in classifications)

        # Score with diminishing returns
        if total_severity == 0:
            score = 1.0
        elif total_severity < 1:
            score = 1.0 - (total_severity * 0.5)
        elif total_severity < 2:
            score = 0.5 - ((total_severity - 1) * 0.3)
        else:
            score = max(0.0, 0.2 - ((total_severity - 2) * 0.1))

        return score, classifications


# =============================================================================
# 7. SQL BEST PRACTICES SCORING
# =============================================================================

@dataclass
class BestPracticesReport:
    """Report on SQL best practices violations."""
    score: float = 1.0
    violations: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "violations": self.violations,
            "suggestions": self.suggestions,
        }


class SQLBestPracticesScorer:
    """
    Scores SQL queries for best practices compliance.

    Checks for:
    - SELECT * usage
    - Missing WHERE clauses
    - Proper aliasing
    - DISTINCT misuse
    - Cartesian products
    """

    # Violations and their penalties
    VIOLATIONS = {
        "select_star": {
            "pattern": r"SELECT\s+\*",
            "penalty": 0.1,
            "message": "Avoid SELECT * - specify required columns",
        },
        "no_where": {
            "check": "no_where_clause",
            "penalty": 0.15,
            "message": "Consider adding WHERE clause to filter results",
        },
        "distinct_without_reason": {
            "check": "unnecessary_distinct",
            "penalty": 0.05,
            "message": "DISTINCT may indicate a join issue or be unnecessary",
        },
        "implicit_join": {
            "pattern": r"FROM\s+\w+\s*,\s*\w+",
            "penalty": 0.1,
            "message": "Use explicit JOIN syntax instead of comma joins",
        },
        "no_table_alias": {
            "check": "missing_aliases",
            "penalty": 0.05,
            "message": "Consider using table aliases for clarity",
        },
    }

    def score(self, sql: str, parsed_info: Optional[Dict] = None) -> BestPracticesReport:
        """
        Score SQL query for best practices.

        Args:
            sql: The SQL query
            parsed_info: Optional parsed query information

        Returns:
            BestPracticesReport with score and violations
        """
        report = BestPracticesReport()
        sql_upper = sql.upper()

        # Check pattern-based violations
        for name, config in self.VIOLATIONS.items():
            if "pattern" in config:
                if re.search(config["pattern"], sql, re.IGNORECASE):
                    report.score -= config["penalty"]
                    report.violations.append(config["message"])

        # Check SELECT *
        if re.search(r"SELECT\s+\*", sql_upper):
            report.suggestions.append("Specify only the columns you need")

        # Check for missing WHERE (only on SELECT)
        if "SELECT" in sql_upper and "WHERE" not in sql_upper:
            # Don't penalize for simple lookups or aggregations
            if not re.search(r"(LIMIT\s+1|COUNT\s*\(|^SELECT\s+\d+)", sql_upper):
                report.score -= 0.05
                report.suggestions.append("Consider adding a WHERE clause")

        # Check for comma joins (implicit)
        if re.search(r"FROM\s+\w+\s*,\s*\w+", sql_upper):
            if "JOIN" not in sql_upper:
                report.score -= 0.1
                report.violations.append("Implicit comma joins detected - use explicit JOIN")

        # Check for proper aliasing in JOINs
        if "JOIN" in sql_upper:
            # Count JOINs vs aliases
            join_count = len(re.findall(r"\bJOIN\b", sql_upper))
            alias_count = len(re.findall(r"\bAS\s+\w+", sql_upper))
            if join_count > 0 and alias_count < join_count:
                report.suggestions.append("Use table aliases for joined tables")

        # Check DISTINCT usage
        if "DISTINCT" in sql_upper:
            if "GROUP BY" in sql_upper:
                report.score -= 0.05
                report.violations.append("DISTINCT with GROUP BY may be redundant")

        # Ensure score stays in valid range
        report.score = max(0.0, min(1.0, report.score))

        return report
