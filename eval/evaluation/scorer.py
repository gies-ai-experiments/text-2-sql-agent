"""
Scorer computes weighted multi-dimensional scores from SQLAgent output.

Dimensions:
- correctness (40%): from comparison with expected results
- efficiency (20%): from execution time
- safety (25%): from validation errors / hallucination detection
- result_completeness (15%): from analysis insights

Final score = weighted sum of all dimensions.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from evaluation.data_structures import (
    ComparisonResult,
    MultiDimensionalScore,
    ExecutionResult,
)


class Scorer(ABC):
    """
    Interface for computing weighted multi-dimensional scores.
    """

    @abstractmethod
    def score(
        self,
        comparison: ComparisonResult,
        execution_result: ExecutionResult,
    ) -> MultiDimensionalScore:
        """
        Compute a weighted multi-dimensional score.

        Parameters:
            comparison       -> Result of comparing actual vs expected output.
            execution_result -> Execution result with validation/analysis metadata from SQLAgent.

        Returns:
            MultiDimensionalScore with individual scores and weighted overall score.
        """
        pass


class DefaultScorer(Scorer):
    """
    Default implementation of Scorer.
    
    Computes scores from SQLAgent output and applies configurable weights.
    
    Default weights:
        - correctness: 40%
        - efficiency: 20%
        - safety: 25%
        - result_completeness: 15%
    """

    def __init__(
        self,
        performance_thresholds: Optional[Dict[str, float]] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the scorer.

        Parameters:
            performance_thresholds -> Thresholds for efficiency scoring (ms).
            weights                -> Weights for each scoring dimension (must sum to 1.0).
        """
        self.performance_thresholds = performance_thresholds or {
            "excellent": 10.0,    # < 10ms = 1.0
            "good": 100.0,        # < 100ms = 0.8+
            "acceptable": 1000.0, # < 1000ms = 0.5+
        }
        self.weights = weights or {
            "correctness": 0.40,
            "efficiency": 0.20,
            "safety": 0.25,
            "result_completeness": 0.15,
        }

    def score(
        self,
        comparison: ComparisonResult,
        execution_result: ExecutionResult,
    ) -> MultiDimensionalScore:
        """
        Compute weighted multi-dimensional score.
        
        Steps:
            1. Compute individual dimension scores from SQLAgent data
            2. Apply weights to each dimension
            3. Sum weighted scores for final overall score
        """
        score = MultiDimensionalScore(weights=self.weights)

        # 1. Correctness (from comparison with expected results)
        score.correctness = self._compute_correctness(comparison)

        # 2. Efficiency (from execution time)
        score.efficiency = self._compute_efficiency(execution_result)
        score.performance_score = score.efficiency

        # 3. Safety (from validation + hallucination detection)
        score.safety = self._compute_safety(execution_result)
        score.validation_score = self._compute_validation_score(execution_result)
        score.hallucination_score = self._compute_hallucination_score(execution_result)

        # 4. Result completeness (from analysis insights)
        score.result_completeness = self._compute_completeness(execution_result)

        # 5. Compute weighted overall score
        score.compute_overall()

        # 6. Add detailed breakdown
        score.details = self._build_details(comparison, execution_result)

        return score

    def _compute_correctness(self, comparison: ComparisonResult) -> float:
        """
        Compute correctness score from comparison result.
        
        - Exact match: 1.0
        - Partial match: match_score (0.0 to 1.0)
        - No comparison: 0.0
        """
        if comparison.is_match:
            return 1.0
        return comparison.match_score

    def _compute_efficiency(self, execution_result: ExecutionResult) -> float:
        """
        Compute efficiency score from execution time.
        
        Scoring:
            - < 10ms (excellent): 1.0
            - < 100ms (good): 0.8 - 1.0
            - < 1000ms (acceptable): 0.5 - 0.8
            - > 1000ms (slow): 0.0 - 0.5
        """
        if not execution_result.success:
            return 0.0

        time_ms = execution_result.execution_time_ms

        if time_ms <= self.performance_thresholds["excellent"]:
            return 1.0
        elif time_ms <= self.performance_thresholds["good"]:
            # Linear interpolation: 1.0 → 0.8
            ratio = (time_ms - self.performance_thresholds["excellent"]) / \
                    (self.performance_thresholds["good"] - self.performance_thresholds["excellent"])
            return 1.0 - (0.2 * ratio)
        elif time_ms <= self.performance_thresholds["acceptable"]:
            # Linear interpolation: 0.8 → 0.5
            ratio = (time_ms - self.performance_thresholds["good"]) / \
                    (self.performance_thresholds["acceptable"] - self.performance_thresholds["good"])
            return 0.8 - (0.3 * ratio)
        else:
            # Slow query: 0.5 → 0.0
            excess = time_ms - self.performance_thresholds["acceptable"]
            return max(0.0, 0.5 - (excess / 10000))

    def _compute_safety(self, execution_result: ExecutionResult) -> float:
        """
        Compute overall safety score.
        
        Combines:
            - Validation score (40%)
            - Hallucination score (60%)
        """
        validation_score = self._compute_validation_score(execution_result)
        hallucination_score = self._compute_hallucination_score(execution_result)

        return 0.4 * validation_score + 0.6 * hallucination_score

    def _compute_validation_score(self, execution_result: ExecutionResult) -> float:
        """
        Compute validation score based on query validity.
        
        Scoring:
            - Valid with no warnings: 1.0
            - Valid with warnings: 0.9 - 1.0 (deduct 0.1 per warning)
            - Invalid: 0.1 - 0.5 (based on error count)
        """
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

    def _compute_hallucination_score(self, execution_result: ExecutionResult) -> float:
        """
        Compute hallucination score based on validation errors.
        
        Hallucinations include:
            - Non-existent table references
            - Non-existent column references
            - Invalid schema references
        
        Scoring:
            - No hallucinations: 1.0
            - 1 hallucination: 0.4
            - 2+ hallucinations: 0.1
        """
        if execution_result.is_valid and not execution_result.validation_errors:
            return 1.0

        hallucination_keywords = [
            "does not exist",
            "unknown column",
            "unknown table",
            "invalid",
            "not found",
            "no such",
            "doesn't exist",
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
        """
        Compute result completeness score from analysis insights.
        
        Penalties:
            - "no results": -0.2
            - "truncated": -0.1
            - "null": -0.05
            - "slow": -0.1
        
        Bonus:
            - Has rows: +0.1 (capped at 1.0)
        """
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
        """Build detailed breakdown for debugging and analysis."""
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