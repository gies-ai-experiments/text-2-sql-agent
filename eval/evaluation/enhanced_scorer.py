"""
Enhanced Scorer - More accurate SQL evaluation scoring.

Integrates advanced scoring components:
1. Query Complexity Analysis (adaptive expectations)
2. Adaptive Performance Thresholds (dialect & complexity aware)
3. Weighted Hallucination Scoring (severity-based)
4. Execution Plan Analysis (optimization detection)
5. Semantic Result Accuracy (value-level comparison)
6. Error Taxonomy (severity-based error scoring)
7. SQL Best Practices (code quality scoring)

Usage:
    from evaluation.enhanced_scorer import EnhancedScorer

    scorer = EnhancedScorer()
    score = scorer.score(comparison, execution_result,
                         sql=query, dialect="sqlite", expected=expected_results)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from evaluation.data_structures import (
    ComparisonResult,
    ExecutionResult,
    MultiDimensionalScore,
)
from evaluation.advanced_scoring import (
    QueryComplexityAnalyzer,
    QueryComplexityReport,
    AdaptivePerformanceScorer,
    PerformanceThresholds,
    WeightedHallucinationScorer,
    HallucinationType,
    ExecutionPlanAnalyzer,
    PlanAnalysisResult,
    SemanticAccuracyScorer,
    SemanticAccuracyResult,
    ErrorTaxonomyClassifier,
    SQLBestPracticesScorer,
    BestPracticesReport,
)


@dataclass
class EnhancedScore(MultiDimensionalScore):
    """
    Extended score with additional dimensions and detailed breakdown.

    New dimensions:
    - query_complexity: How complex is the query (informational)
    - best_practices: SQL code quality score
    - semantic_accuracy: Value-level result accuracy

    Enhanced existing dimensions:
    - efficiency: Now uses adaptive thresholds
    - safety: Now uses weighted hallucination severity
    """
    # Additional dimensions
    query_complexity_score: float = 0.0
    best_practices_score: float = 0.0
    semantic_accuracy_score: float = 0.0
    plan_quality_score: float = 0.0
    error_severity_score: float = 0.0

    # Detailed reports
    complexity_report: Dict[str, Any] = field(default_factory=dict)
    performance_thresholds: Dict[str, float] = field(default_factory=dict)
    hallucination_details: Dict[str, Any] = field(default_factory=dict)
    plan_analysis: Dict[str, Any] = field(default_factory=dict)
    semantic_analysis: Dict[str, Any] = field(default_factory=dict)
    error_analysis: Dict[str, Any] = field(default_factory=dict)
    best_practices_report: Dict[str, Any] = field(default_factory=dict)

    def compute_overall(self) -> float:
        """
        Compute weighted overall score with new dimensions.

        Enhanced formula:
            correctness     × 0.35 (was 0.40)
            efficiency      × 0.15 (was 0.20)
            safety          × 0.20 (was 0.25)
            completeness    × 0.10 (was 0.15)
            semantic_acc    × 0.10 (new)
            best_practices  × 0.05 (new)
            plan_quality    × 0.05 (new)
        """
        self.overall = (
            self.weights.get("correctness", 0.35) * self.correctness +
            self.weights.get("efficiency", 0.15) * self.efficiency +
            self.weights.get("safety", 0.20) * self.safety +
            self.weights.get("result_completeness", 0.10) * self.result_completeness +
            self.weights.get("semantic_accuracy", 0.10) * self.semantic_accuracy_score +
            self.weights.get("best_practices", 0.05) * self.best_practices_score +
            self.weights.get("plan_quality", 0.05) * self.plan_quality_score
        )
        return self.overall

    def to_dict(self) -> Dict[str, Any]:
        """Convert to detailed dictionary."""
        return {
            "overall": round(self.overall, 4),
            "dimensions": {
                "correctness": round(self.correctness, 4),
                "efficiency": round(self.efficiency, 4),
                "safety": round(self.safety, 4),
                "result_completeness": round(self.result_completeness, 4),
                "semantic_accuracy": round(self.semantic_accuracy_score, 4),
                "best_practices": round(self.best_practices_score, 4),
                "plan_quality": round(self.plan_quality_score, 4),
            },
            "sub_scores": {
                "validation_score": round(self.validation_score, 4),
                "performance_score": round(self.performance_score, 4),
                "hallucination_score": round(self.hallucination_score, 4),
                "error_severity_score": round(self.error_severity_score, 4),
                "query_complexity": round(self.query_complexity_score, 4),
            },
            "weights": self.weights,
            "analysis": {
                "complexity": self.complexity_report,
                "thresholds": self.performance_thresholds,
                "hallucinations": self.hallucination_details,
                "plan": self.plan_analysis,
                "semantic": self.semantic_analysis,
                "errors": self.error_analysis,
                "best_practices": self.best_practices_report,
            },
            "details": self.details,
        }


class EnhancedScorer:
    """
    Enhanced scorer with advanced scoring components.

    Provides more accurate evaluation through:
    - Query complexity-aware thresholds
    - Dialect-specific performance expectations
    - Severity-weighted hallucination detection
    - Value-level result accuracy
    - SQL best practices assessment
    """

    # Default weights for enhanced scoring
    DEFAULT_WEIGHTS = {
        "correctness": 0.35,
        "efficiency": 0.15,
        "safety": 0.20,
        "result_completeness": 0.10,
        "semantic_accuracy": 0.10,
        "best_practices": 0.05,
        "plan_quality": 0.05,
    }

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        use_adaptive_thresholds: bool = True,
        use_semantic_accuracy: bool = True,
        use_best_practices: bool = True,
    ):
        """
        Initialize the enhanced scorer.

        Args:
            weights: Custom dimension weights (must sum to 1.0)
            use_adaptive_thresholds: Use complexity-aware performance thresholds
            use_semantic_accuracy: Enable semantic result comparison
            use_best_practices: Enable SQL best practices scoring
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.use_adaptive_thresholds = use_adaptive_thresholds
        self.use_semantic_accuracy = use_semantic_accuracy
        self.use_best_practices = use_best_practices

        # Initialize scoring components
        self.complexity_analyzer = QueryComplexityAnalyzer()
        self.performance_scorer = AdaptivePerformanceScorer()
        self.hallucination_scorer = WeightedHallucinationScorer()
        self.plan_analyzer = ExecutionPlanAnalyzer()
        self.semantic_scorer = SemanticAccuracyScorer()
        self.error_classifier = ErrorTaxonomyClassifier()
        self.best_practices_scorer = SQLBestPracticesScorer()

    def score(
        self,
        comparison: ComparisonResult,
        execution_result: ExecutionResult,
        sql: Optional[str] = None,
        dialect: str = "sqlite",
        expected_results: Optional[List[Dict[str, Any]]] = None,
        plan_text: Optional[str] = None,
    ) -> EnhancedScore:
        """
        Compute enhanced multi-dimensional score.

        Args:
            comparison: Result comparison from DefaultResultComparator
            execution_result: Execution result from SQLExecutor
            sql: Original SQL query (for complexity/best practices analysis)
            dialect: Database dialect (for adaptive thresholds)
            expected_results: Expected results (for semantic accuracy)
            plan_text: Execution plan text (for plan analysis)

        Returns:
            EnhancedScore with detailed breakdown
        """
        score = EnhancedScore(weights=self.weights)

        # 1. Analyze query complexity (if SQL provided)
        complexity_report = None
        if sql:
            complexity_report = self.complexity_analyzer.analyze(
                sql,
                parsed_info={
                    "tables_accessed": execution_result.tables_accessed,
                    "columns_accessed": execution_result.columns_accessed,
                }
            )
            score.complexity_report = complexity_report.to_dict()
            score.query_complexity_score = complexity_report.complexity_score

        # 2. Compute correctness (from comparison)
        score.correctness = self._compute_correctness(comparison)

        # 3. Compute efficiency with adaptive thresholds
        complexity_level = complexity_report.complexity_level if complexity_report else "simple"
        score.efficiency, score.performance_thresholds = self._compute_efficiency(
            execution_result,
            complexity_level,
            dialect,
        )
        score.performance_score = score.efficiency

        # 4. Compute safety with weighted hallucination severity
        score.safety, score.hallucination_details = self._compute_safety(execution_result)
        score.validation_score = self._compute_validation_score(execution_result)

        # Extract hallucination score from details
        if "final_score" in score.hallucination_details:
            score.hallucination_score = score.hallucination_details["final_score"]
        else:
            score.hallucination_score = self._legacy_hallucination_score(execution_result)

        # 5. Compute result completeness
        score.result_completeness = self._compute_completeness(execution_result)

        # 6. Compute semantic accuracy (if expected results provided)
        if self.use_semantic_accuracy and expected_results:
            semantic_result = self.semantic_scorer.score(
                execution_result.data,
                expected_results,
            )
            score.semantic_accuracy_score = semantic_result.overall_score
            score.semantic_analysis = semantic_result.to_dict()
        else:
            # Fall back to comparison match score
            score.semantic_accuracy_score = comparison.match_score

        # 7. Analyze execution plan (if provided)
        if plan_text:
            plan_result = self.plan_analyzer.analyze(plan_text, dialect)
            score.plan_quality_score = plan_result.plan_score
            score.plan_analysis = plan_result.to_dict()
        else:
            score.plan_quality_score = 1.0  # Assume optimal if no plan

        # 8. Compute error severity score
        if execution_result.validation_errors:
            error_score, classifications = self.error_classifier.score_errors(
                execution_result.validation_errors
            )
            score.error_severity_score = error_score
            score.error_analysis = {
                "score": error_score,
                "errors": [c.to_dict() for c in classifications],
            }
        else:
            score.error_severity_score = 1.0

        # 9. Compute best practices score (if SQL provided)
        if self.use_best_practices and sql:
            bp_report = self.best_practices_scorer.score(sql)
            score.best_practices_score = bp_report.score
            score.best_practices_report = bp_report.to_dict()
        else:
            score.best_practices_score = 1.0

        # 10. Compute overall score
        score.compute_overall()

        # 11. Build detailed breakdown
        score.details = self._build_details(comparison, execution_result)

        return score

    def _compute_correctness(self, comparison: ComparisonResult) -> float:
        """Compute correctness from comparison result."""
        if comparison.is_match:
            return 1.0
        return comparison.match_score

    def _compute_efficiency(
        self,
        execution_result: ExecutionResult,
        complexity_level: str,
        dialect: str,
    ) -> tuple:
        """
        Compute efficiency with adaptive thresholds.

        Returns:
            Tuple of (score, thresholds_used)
        """
        if not execution_result.success:
            return 0.0, {}

        if self.use_adaptive_thresholds:
            thresholds = self.performance_scorer.get_thresholds(
                complexity_level=complexity_level,
                dialect=dialect,
                row_estimate=execution_result.rows_returned,
            )
            score = self.performance_scorer.score(
                execution_result.execution_time_ms,
                thresholds,
            )
            return score, thresholds.to_dict()
        else:
            # Legacy fixed thresholds
            time_ms = execution_result.execution_time_ms
            if time_ms <= 10:
                return 1.0, {"excellent": 10, "good": 100, "acceptable": 1000}
            elif time_ms <= 100:
                ratio = (time_ms - 10) / 90
                return 1.0 - (0.2 * ratio), {"excellent": 10, "good": 100, "acceptable": 1000}
            elif time_ms <= 1000:
                ratio = (time_ms - 100) / 900
                return 0.8 - (0.3 * ratio), {"excellent": 10, "good": 100, "acceptable": 1000}
            else:
                return max(0.0, 0.5 - ((time_ms - 1000) / 10000)), {"excellent": 10, "good": 100, "acceptable": 1000}

    def _compute_safety(
        self,
        execution_result: ExecutionResult,
    ) -> tuple:
        """
        Compute safety with weighted hallucination severity.

        Returns:
            Tuple of (score, hallucination_details)
        """
        validation_score = self._compute_validation_score(execution_result)

        # Extract hallucination info from validation errors
        phantom_tables = []
        phantom_columns = []
        phantom_functions = []

        for error in execution_result.validation_errors:
            error_lower = error.lower()
            if "table" in error_lower and ("not exist" in error_lower or "does not exist" in error_lower):
                # Extract table name
                phantom_tables.append(error)
            elif "column" in error_lower and ("not exist" in error_lower or "does not exist" in error_lower):
                phantom_columns.append(error)
            elif "function" in error_lower and ("not exist" in error_lower or "invalid" in error_lower):
                phantom_functions.append(error)

        # Use weighted scorer
        hallucination_score, details = self.hallucination_scorer.score(
            phantom_tables,
            phantom_columns,
            phantom_functions,
        )

        # Combine validation and hallucination scores
        safety_score = 0.4 * validation_score + 0.6 * hallucination_score

        return safety_score, details

    def _compute_validation_score(self, execution_result: ExecutionResult) -> float:
        """Compute validation score based on query validity."""
        if execution_result.is_valid:
            score = 1.0
            warning_count = len(execution_result.validation_warnings)
            score -= warning_count * 0.1
            return max(0.0, score)
        else:
            error_count = len(execution_result.validation_errors)
            if error_count == 0:
                return 0.5
            elif error_count == 1:
                return 0.3
            else:
                return 0.1

    def _legacy_hallucination_score(self, execution_result: ExecutionResult) -> float:
        """Legacy keyword-based hallucination scoring."""
        if execution_result.is_valid and not execution_result.validation_errors:
            return 1.0

        hallucination_keywords = [
            "does not exist",
            "unknown column",
            "unknown table",
            "invalid",
            "not found",
            "no such",
        ]

        hallucination_count = 0
        for error in execution_result.validation_errors:
            error_lower = error.lower()
            if any(keyword in error_lower for keyword in hallucination_keywords):
                hallucination_count += 1

        if hallucination_count == 0:
            return 1.0
        elif hallucination_count == 1:
            return 0.4
        else:
            return 0.1

    def _compute_completeness(self, execution_result: ExecutionResult) -> float:
        """Compute result completeness score."""
        if not execution_result.success:
            return 0.0

        score = 1.0

        for insight in execution_result.insights:
            insight_lower = insight.lower()
            if "no results" in insight_lower or "empty" in insight_lower:
                score -= 0.2
            elif "truncated" in insight_lower:
                score -= 0.1
            elif "null" in insight_lower:
                score -= 0.05
            elif "slow" in insight_lower or "long" in insight_lower:
                score -= 0.1

        # Bonus for having results
        if execution_result.rows_returned > 0:
            score = min(1.0, score + 0.1)

        return max(0.0, score)

    def _build_details(
        self,
        comparison: ComparisonResult,
        execution_result: ExecutionResult,
    ) -> Dict[str, Any]:
        """Build detailed breakdown for debugging."""
        return {
            "comparison": {
                "is_match": comparison.is_match,
                "match_score": comparison.match_score,
                "row_count_match": comparison.row_count_match,
                "column_count_match": comparison.column_count_match,
            },
            "execution": {
                "success": execution_result.success,
                "execution_time_ms": execution_result.execution_time_ms,
                "rows_returned": execution_result.rows_returned,
                "error": execution_result.error,
            },
            "validation": {
                "is_valid": execution_result.is_valid,
                "errors": execution_result.validation_errors,
                "warnings": execution_result.validation_warnings,
                "query_type": execution_result.query_type,
                "tables_accessed": execution_result.tables_accessed,
                "columns_accessed": execution_result.columns_accessed,
            },
            "analysis": {
                "insights": execution_result.insights,
                "summary": execution_result.summary,
            },
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_enhanced_scorer(
    preset: str = "default",
    **kwargs,
) -> EnhancedScorer:
    """
    Create an EnhancedScorer with preset configurations.

    Presets:
    - "default": Balanced scoring for general use
    - "strict": Higher weight on correctness and safety
    - "performance": Higher weight on efficiency
    - "quality": Higher weight on best practices

    Args:
        preset: Configuration preset name
        **kwargs: Override specific settings

    Returns:
        Configured EnhancedScorer
    """
    presets = {
        "default": {
            "weights": {
                "correctness": 0.35,
                "efficiency": 0.15,
                "safety": 0.20,
                "result_completeness": 0.10,
                "semantic_accuracy": 0.10,
                "best_practices": 0.05,
                "plan_quality": 0.05,
            }
        },
        "strict": {
            "weights": {
                "correctness": 0.40,
                "efficiency": 0.10,
                "safety": 0.25,
                "result_completeness": 0.10,
                "semantic_accuracy": 0.10,
                "best_practices": 0.025,
                "plan_quality": 0.025,
            }
        },
        "performance": {
            "weights": {
                "correctness": 0.30,
                "efficiency": 0.25,
                "safety": 0.15,
                "result_completeness": 0.10,
                "semantic_accuracy": 0.05,
                "best_practices": 0.05,
                "plan_quality": 0.10,
            }
        },
        "quality": {
            "weights": {
                "correctness": 0.30,
                "efficiency": 0.10,
                "safety": 0.20,
                "result_completeness": 0.10,
                "semantic_accuracy": 0.10,
                "best_practices": 0.15,
                "plan_quality": 0.05,
            }
        },
    }

    config = presets.get(preset, presets["default"]).copy()
    config.update(kwargs)

    return EnhancedScorer(**config)
