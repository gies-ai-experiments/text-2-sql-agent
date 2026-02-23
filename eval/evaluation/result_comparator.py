"""
ResultComparator compares actual query results against expected results.

Provides flexible comparison with:
- Exact matching
- Row order tolerance
- Numeric tolerance for floating-point values
- Partial matching with scores
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
import math

from evaluation.data_structures import ComparisonResult


class ResultComparator(ABC):
    """
    Abstract interface for comparing actual vs expected query results.
    """

    @abstractmethod
    def compare(
        self,
        actual: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
    ) -> ComparisonResult:
        """
        Compare actual results against expected results.

        Parameters:
            actual   -> List of row dictionaries from query execution.
            expected -> List of row dictionaries representing expected output.

        Returns:
            ComparisonResult with match status and detailed breakdown.
        """
        pass


class DefaultResultComparator(ResultComparator):
    """
    Default implementation of ResultComparator.

    Features:
    - Configurable numeric tolerance for float comparisons
    - Optional row order sensitivity
    - Partial match scoring
    """

    def __init__(
        self,
        numeric_tolerance: float = 1e-6,
        ignore_row_order: bool = True,
        ignore_column_order: bool = True,
        case_sensitive: bool = False,
    ):
        """
        Initialize the comparator with configuration options.

        Parameters:
            numeric_tolerance   -> Tolerance for floating-point comparisons.
            ignore_row_order    -> If True, rows can be in any order.
            ignore_column_order -> If True, columns can be in any order.
            case_sensitive      -> If True, string comparisons are case-sensitive.
        """
        self.numeric_tolerance = numeric_tolerance
        self.ignore_row_order = ignore_row_order
        self.ignore_column_order = ignore_column_order
        self.case_sensitive = case_sensitive

    def compare(
        self,
        actual: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
    ) -> ComparisonResult:
        """Compare actual results against expected results."""

        # Handle empty cases
        if not actual and not expected:
            return ComparisonResult(
                is_match=True,
                match_score=1.0,
                row_count_match=True,
                column_count_match=True,
                details={"message": "Both results are empty"},
            )

        if not actual:
            return ComparisonResult(
                is_match=False,
                match_score=0.0,
                row_count_match=False,
                column_count_match=False,
                details={"message": "Actual result is empty", "expected_rows": len(expected)},
            )

        if not expected:
            return ComparisonResult(
                is_match=False,
                match_score=0.0,
                row_count_match=False,
                column_count_match=False,
                details={"message": "Expected result is empty", "actual_rows": len(actual)},
            )

        # Get columns
        actual_columns = set(actual[0].keys()) if actual else set()
        expected_columns = set(expected[0].keys()) if expected else set()

        # Check column match
        column_count_match = len(actual_columns) == len(expected_columns)
        missing_columns = expected_columns - actual_columns
        extra_columns = actual_columns - expected_columns
        common_columns = actual_columns & expected_columns

        # Check row count match
        row_count_match = len(actual) == len(expected)

        # Calculate column match ratio
        if expected_columns:
            column_match_ratio = len(common_columns) / len(expected_columns)
        else:
            column_match_ratio = 1.0 if not actual_columns else 0.0

        # Compare rows
        row_match_result = self._compare_rows(actual, expected, common_columns)

        # Calculate overall match score
        match_score = self._calculate_match_score(
            column_match_ratio=column_match_ratio,
            row_match_ratio=row_match_result["row_match_ratio"],
            row_count_match=row_count_match,
            column_count_match=column_count_match,
        )

        # Determine if it's an exact match
        is_match = (
            match_score >= 0.99 and
            row_count_match and
            column_count_match and
            not missing_columns and
            not extra_columns
        )

        return ComparisonResult(
            is_match=is_match,
            match_score=match_score,
            row_count_match=row_count_match,
            column_count_match=column_count_match,
            details={
                "actual_row_count": len(actual),
                "expected_row_count": len(expected),
                "actual_columns": list(actual_columns),
                "expected_columns": list(expected_columns),
                "missing_columns": list(missing_columns),
                "extra_columns": list(extra_columns),
                "common_columns": list(common_columns),
                "column_match_ratio": column_match_ratio,
                "row_match_ratio": row_match_result["row_match_ratio"],
                "matched_rows": row_match_result["matched_rows"],
                "unmatched_rows": row_match_result["unmatched_rows"],
            },
        )

    def _compare_rows(
        self,
        actual: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
        columns: Set[str],
    ) -> Dict[str, Any]:
        """
        Compare rows between actual and expected results.

        Returns:
            Dictionary with row_match_ratio, matched_rows, unmatched_rows.
        """
        if not columns:
            return {
                "row_match_ratio": 0.0,
                "matched_rows": 0,
                "unmatched_rows": len(expected),
            }

        if self.ignore_row_order:
            return self._compare_rows_unordered(actual, expected, columns)
        else:
            return self._compare_rows_ordered(actual, expected, columns)

    def _compare_rows_unordered(
        self,
        actual: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
        columns: Set[str],
    ) -> Dict[str, Any]:
        """Compare rows without considering order."""
        matched_rows = 0
        expected_matched = [False] * len(expected)

        for actual_row in actual:
            for i, expected_row in enumerate(expected):
                if expected_matched[i]:
                    continue
                if self._rows_match(actual_row, expected_row, columns):
                    matched_rows += 1
                    expected_matched[i] = True
                    break

        total_expected = len(expected)
        row_match_ratio = matched_rows / total_expected if total_expected > 0 else 1.0

        return {
            "row_match_ratio": row_match_ratio,
            "matched_rows": matched_rows,
            "unmatched_rows": total_expected - matched_rows,
        }

    def _compare_rows_ordered(
        self,
        actual: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
        columns: Set[str],
    ) -> Dict[str, Any]:
        """Compare rows considering order."""
        matched_rows = 0
        min_len = min(len(actual), len(expected))

        for i in range(min_len):
            if self._rows_match(actual[i], expected[i], columns):
                matched_rows += 1

        total_expected = len(expected)
        row_match_ratio = matched_rows / total_expected if total_expected > 0 else 1.0

        return {
            "row_match_ratio": row_match_ratio,
            "matched_rows": matched_rows,
            "unmatched_rows": total_expected - matched_rows,
        }

    def _rows_match(
        self,
        actual_row: Dict[str, Any],
        expected_row: Dict[str, Any],
        columns: Set[str],
    ) -> bool:
        """Check if two rows match for the given columns."""
        for col in columns:
            actual_val = actual_row.get(col)
            expected_val = expected_row.get(col)

            if not self._values_match(actual_val, expected_val):
                return False

        return True

    def _values_match(self, actual: Any, expected: Any) -> bool:
        """Check if two values match with appropriate tolerance."""
        # Handle None
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False

        # Handle numeric comparison with tolerance
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            if math.isnan(actual) and math.isnan(expected):
                return True
            return abs(actual - expected) <= self.numeric_tolerance

        # Handle string comparison
        if isinstance(actual, str) and isinstance(expected, str):
            if self.case_sensitive:
                return actual == expected
            return actual.lower() == expected.lower()

        # Default equality
        return actual == expected

    def _calculate_match_score(
        self,
        column_match_ratio: float,
        row_match_ratio: float,
        row_count_match: bool,
        column_count_match: bool,
    ) -> float:
        """
        Calculate overall match score.

        Weights:
        - Row match ratio: 50%
        - Column match ratio: 30%
        - Row count match: 10%
        - Column count match: 10%
        """
        score = (
            0.50 * row_match_ratio +
            0.30 * column_match_ratio +
            0.10 * (1.0 if row_count_match else 0.0) +
            0.10 * (1.0 if column_count_match else 0.0)
        )
        return round(score, 4)