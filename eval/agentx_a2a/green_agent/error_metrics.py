"""
SQL Error Category Metrics for AgentX Green Agent.

Provides comprehensive error classification and metrics tracking
based on common SQL generation failure patterns.

Error categories are inspired by research on SQL generation failures:
- Schema Errors: Wrong schema linking, wrong column, wrong table
- Analysis Errors: Erroneous data analysis, incorrect planning, calculation errors
- SQL Errors: Syntax errors, condition filter errors, join errors, dialect issues
- Other: Prompt length issues, external knowledge misunderstanding
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import re


class ErrorCategory(Enum):
    """Top-level error categories for SQL generation failures."""
    SCHEMA_ERROR = "schema_error"
    ANALYSIS_ERROR = "analysis_error"
    SQL_ERROR = "sql_error"
    PROMPT_ERROR = "prompt_error"
    KNOWLEDGE_ERROR = "knowledge_error"
    NO_ERROR = "no_error"


class ErrorSubcategory(Enum):
    """Detailed error subcategories for granular tracking."""
    # Schema errors
    WRONG_SCHEMA_LINKING = "wrong_schema_linking"
    WRONG_COLUMN = "wrong_column"
    WRONG_TABLE = "wrong_table"

    # Analysis errors
    ERRONEOUS_DATA_ANALYSIS = "erroneous_data_analysis"
    INCORRECT_PLANNING = "incorrect_planning"
    INCORRECT_DATA_CALCULATION = "incorrect_data_calculation"

    # SQL errors
    SYNTAX_ERROR = "syntax_error"
    CONDITION_FILTER_ERROR = "condition_filter_error"
    JOIN_ERROR = "join_error"
    DIALECT_FUNCTION_ERROR = "incorrect_dialect_function_usage"

    # Other errors
    EXCESSIVE_PROMPT_LENGTH = "excessive_prompt_length"
    MISUNDERSTANDING_EXTERNAL_KNOWLEDGE = "misunderstanding_external_knowledge"

    # Success
    NO_ERROR = "no_error"


@dataclass
class ErrorClassification:
    """Classification result for a single SQL error."""
    category: ErrorCategory
    subcategory: ErrorSubcategory
    confidence: float  # 0.0 to 1.0
    details: str = ""
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "subcategory": self.subcategory.value,
            "confidence": round(self.confidence, 3),
            "details": self.details,
            "evidence": self.evidence,
        }


@dataclass
class ErrorMetricsSummary:
    """
    Summary of error metrics across multiple evaluations.

    Tracks counts and percentages for each error category and subcategory,
    enabling pie chart visualizations like the one shown in the UI.
    """
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0

    # Category counts
    category_counts: Dict[str, int] = field(default_factory=dict)

    # Subcategory counts
    subcategory_counts: Dict[str, int] = field(default_factory=dict)

    # Detailed breakdown per subcategory
    subcategory_details: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def add_classification(
        self,
        classification: ErrorClassification,
        task_id: str,
        sql_submitted: str,
    ) -> None:
        """Add a classification to the metrics summary."""
        self.total_tasks += 1

        if classification.subcategory == ErrorSubcategory.NO_ERROR:
            self.successful_tasks += 1
        else:
            self.failed_tasks += 1

        # Update category counts
        cat_key = classification.category.value
        self.category_counts[cat_key] = self.category_counts.get(cat_key, 0) + 1

        # Update subcategory counts
        subcat_key = classification.subcategory.value
        self.subcategory_counts[subcat_key] = self.subcategory_counts.get(subcat_key, 0) + 1

        # Store details
        if subcat_key not in self.subcategory_details:
            self.subcategory_details[subcat_key] = []

        self.subcategory_details[subcat_key].append({
            "task_id": task_id,
            "sql_snippet": sql_submitted[:200] if sql_submitted else "",
            "details": classification.details,
            "evidence": classification.evidence,
        })

    def get_percentages(self) -> Dict[str, float]:
        """Get percentages for each error subcategory (for pie chart)."""
        if self.failed_tasks == 0:
            return {}

        percentages = {}
        for subcat, count in self.subcategory_counts.items():
            if subcat != ErrorSubcategory.NO_ERROR.value:
                percentages[subcat] = round(count / self.failed_tasks * 100, 1)

        return percentages

    def get_category_percentages(self) -> Dict[str, float]:
        """Get percentages for each top-level error category."""
        if self.failed_tasks == 0:
            return {}

        percentages = {}
        for cat, count in self.category_counts.items():
            if cat != ErrorCategory.NO_ERROR.value:
                percentages[cat] = round(count / self.failed_tasks * 100, 1)

        return percentages

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": round(self.successful_tasks / self.total_tasks * 100, 1) if self.total_tasks > 0 else 0,
            "category_counts": self.category_counts,
            "subcategory_counts": self.subcategory_counts,
            "category_percentages": self.get_category_percentages(),
            "subcategory_percentages": self.get_percentages(),
            "detailed_breakdown": {
                subcat: {
                    "count": len(details),
                    "percentage": round(len(details) / self.failed_tasks * 100, 1) if self.failed_tasks > 0 else 0,
                    "examples": details[:5],  # First 5 examples
                }
                for subcat, details in self.subcategory_details.items()
                if subcat != ErrorSubcategory.NO_ERROR.value
            },
        }


class SQLErrorClassifier:
    """
    Classifier for SQL generation errors.

    Analyzes SQL queries, validation errors, and execution results
    to determine the root cause of failures.
    """

    # Pattern matchers for different error types
    SCHEMA_PATTERNS = {
        "wrong_table": [
            r"table\s+'?(\w+)'?\s+does\s+not\s+exist",
            r"no\s+such\s+table:?\s*'?(\w+)'?",
            r"relation\s+'?(\w+)'?\s+does\s+not\s+exist",
            r"unknown\s+table\s+'?(\w+)'?",
        ],
        "wrong_column": [
            r"column\s+'?(\w+)'?\s+does\s+not\s+exist",
            r"no\s+such\s+column:?\s*'?(\w+)'?",
            r"unknown\s+column\s+'?(\w+)'?",
            r"ambiguous\s+column\s+name:?\s*'?(\w+)'?",
        ],
        "wrong_schema_linking": [
            r"foreign\s+key\s+constraint",
            r"references\s+unknown",
            r"table\s+alias\s+'?(\w+)'?\s+not\s+found",
        ],
    }

    SQL_ERROR_PATTERNS = {
        "syntax_error": [
            r"syntax\s+error",
            r"parse\s+error",
            r"unexpected\s+token",
            r"missing\s+';'",
            r"near\s+\"(\w+)\":\s+syntax\s+error",
        ],
        "join_error": [
            r"ambiguous\s+column",
            r"join\s+(condition|clause)\s+.*(missing|invalid)",
            r"cannot\s+resolve\s+.*\s+in\s+join",
            r"invalid\s+join\s+specification",
        ],
        "condition_filter_error": [
            r"where\s+clause.*invalid",
            r"comparison\s+.*\s+incompatible",
            r"operator\s+does\s+not\s+exist",
            r"invalid\s+(comparison|operator)",
        ],
        "dialect_function_error": [
            r"function\s+'?(\w+)'?\s+does\s+not\s+exist",
            r"unknown\s+function",
            r"no\s+such\s+function",
            r"unsupported\s+function",
        ],
    }

    ANALYSIS_PATTERNS = {
        "incorrect_planning": [
            r"missing\s+group\s+by",
            r"aggregate.*without.*group",
            r"incorrect\s+aggregation",
        ],
        "incorrect_data_calculation": [
            r"division\s+by\s+zero",
            r"numeric\s+overflow",
            r"invalid\s+arithmetic",
        ],
    }

    def __init__(self):
        """Initialize the classifier."""
        # Compile regex patterns for performance
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        all_patterns = {
            **self.SCHEMA_PATTERNS,
            **self.SQL_ERROR_PATTERNS,
            **self.ANALYSIS_PATTERNS,
        }
        for key, patterns in all_patterns.items():
            self._compiled_patterns[key] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify(
        self,
        sql_submitted: str,
        gold_sql: Optional[str],
        execution_success: bool,
        validation_errors: List[str],
        phantom_tables: List[str],
        phantom_columns: List[str],
        error_message: Optional[str] = None,
        match_score: Optional[float] = None,
        correctness_score: Optional[float] = None,
    ) -> ErrorClassification:
        """
        Classify an SQL error based on available evidence.

        Args:
            sql_submitted: The SQL query submitted by the agent
            gold_sql: The expected correct SQL query
            execution_success: Whether the query executed successfully
            validation_errors: List of validation error messages
            phantom_tables: Tables referenced but don't exist
            phantom_columns: Columns referenced but don't exist
            error_message: Any error message from execution
            match_score: Score comparing results to expected
            correctness_score: Overall correctness score

        Returns:
            ErrorClassification with category, subcategory, and details
        """
        # No error case
        if execution_success and not validation_errors:
            if match_score is not None and match_score >= 0.95:
                return ErrorClassification(
                    category=ErrorCategory.NO_ERROR,
                    subcategory=ErrorSubcategory.NO_ERROR,
                    confidence=1.0,
                    details="Query executed successfully with correct results",
                )

        evidence = []
        all_errors = validation_errors + ([error_message] if error_message else [])
        error_text = " ".join(all_errors).lower()

        # Check for phantom tables (wrong table)
        if phantom_tables:
            return ErrorClassification(
                category=ErrorCategory.SCHEMA_ERROR,
                subcategory=ErrorSubcategory.WRONG_TABLE,
                confidence=0.95,
                details=f"Referenced non-existent table(s): {', '.join(phantom_tables)}",
                evidence=phantom_tables,
            )

        # Check for phantom columns (wrong column)
        if phantom_columns:
            return ErrorClassification(
                category=ErrorCategory.SCHEMA_ERROR,
                subcategory=ErrorSubcategory.WRONG_COLUMN,
                confidence=0.95,
                details=f"Referenced non-existent column(s): {', '.join(phantom_columns)}",
                evidence=phantom_columns,
            )

        # Check for wrong table patterns
        for pattern in self._compiled_patterns.get("wrong_table", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.SCHEMA_ERROR,
                    subcategory=ErrorSubcategory.WRONG_TABLE,
                    confidence=0.9,
                    details=f"Table error detected: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for wrong column patterns
        for pattern in self._compiled_patterns.get("wrong_column", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.SCHEMA_ERROR,
                    subcategory=ErrorSubcategory.WRONG_COLUMN,
                    confidence=0.9,
                    details=f"Column error detected: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for syntax errors
        for pattern in self._compiled_patterns.get("syntax_error", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.SQL_ERROR,
                    subcategory=ErrorSubcategory.SYNTAX_ERROR,
                    confidence=0.9,
                    details=f"Syntax error detected: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for join errors
        for pattern in self._compiled_patterns.get("join_error", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.SQL_ERROR,
                    subcategory=ErrorSubcategory.JOIN_ERROR,
                    confidence=0.85,
                    details=f"Join error detected: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for condition/filter errors
        for pattern in self._compiled_patterns.get("condition_filter_error", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.SQL_ERROR,
                    subcategory=ErrorSubcategory.CONDITION_FILTER_ERROR,
                    confidence=0.85,
                    details=f"Condition filter error: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for dialect/function errors
        for pattern in self._compiled_patterns.get("dialect_function_error", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.SQL_ERROR,
                    subcategory=ErrorSubcategory.DIALECT_FUNCTION_ERROR,
                    confidence=0.85,
                    details=f"Function/dialect error: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for planning errors
        for pattern in self._compiled_patterns.get("incorrect_planning", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.ANALYSIS_ERROR,
                    subcategory=ErrorSubcategory.INCORRECT_PLANNING,
                    confidence=0.8,
                    details=f"Planning error: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Check for calculation errors
        for pattern in self._compiled_patterns.get("incorrect_data_calculation", []):
            match = pattern.search(error_text)
            if match:
                return ErrorClassification(
                    category=ErrorCategory.ANALYSIS_ERROR,
                    subcategory=ErrorSubcategory.INCORRECT_DATA_CALCULATION,
                    confidence=0.8,
                    details=f"Calculation error: {match.group(0)}",
                    evidence=[match.group(0)],
                )

        # Schema linking analysis (compare SQL structure to gold)
        if gold_sql and sql_submitted:
            schema_issues = self._analyze_schema_linking(sql_submitted, gold_sql)
            if schema_issues:
                return ErrorClassification(
                    category=ErrorCategory.SCHEMA_ERROR,
                    subcategory=ErrorSubcategory.WRONG_SCHEMA_LINKING,
                    confidence=0.7,
                    details="Incorrect schema linking detected",
                    evidence=schema_issues,
                )

        # Data analysis errors (result mismatch)
        if match_score is not None and match_score < 0.5 and execution_success:
            return ErrorClassification(
                category=ErrorCategory.ANALYSIS_ERROR,
                subcategory=ErrorSubcategory.ERRONEOUS_DATA_ANALYSIS,
                confidence=0.7,
                details=f"Results do not match expected (score: {match_score:.2f})",
                evidence=[f"match_score={match_score}"],
            )

        # Execution failed but no specific pattern matched
        if not execution_success:
            if error_message:
                return ErrorClassification(
                    category=ErrorCategory.SQL_ERROR,
                    subcategory=ErrorSubcategory.SYNTAX_ERROR,
                    confidence=0.5,
                    details=f"Execution failed: {error_message[:200]}",
                    evidence=[error_message],
                )

        # Moderate match score indicates analysis issues
        if match_score is not None and 0.5 <= match_score < 0.8:
            return ErrorClassification(
                category=ErrorCategory.ANALYSIS_ERROR,
                subcategory=ErrorSubcategory.INCORRECT_PLANNING,
                confidence=0.6,
                details="Query structure differs from expected",
                evidence=[f"match_score={match_score}"],
            )

        # Default: success with minor issues
        return ErrorClassification(
            category=ErrorCategory.NO_ERROR,
            subcategory=ErrorSubcategory.NO_ERROR,
            confidence=0.5,
            details="No clear error pattern detected",
        )

    def _analyze_schema_linking(
        self,
        sql_submitted: str,
        gold_sql: str,
    ) -> List[str]:
        """
        Analyze schema linking differences between submitted and gold SQL.

        Returns list of identified issues.
        """
        issues = []

        # Extract table names
        submitted_tables = set(re.findall(r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)', sql_submitted, re.IGNORECASE))
        gold_tables = set(re.findall(r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)', gold_sql, re.IGNORECASE))

        # Flatten tuples and filter None
        submitted_tables = {t.lower() for tup in submitted_tables for t in tup if t}
        gold_tables = {t.lower() for tup in gold_tables for t in tup if t}

        missing_tables = gold_tables - submitted_tables
        extra_tables = submitted_tables - gold_tables

        if missing_tables:
            issues.append(f"Missing tables: {', '.join(missing_tables)}")
        if extra_tables:
            issues.append(f"Unexpected tables: {', '.join(extra_tables)}")

        # Extract column references (simplified)
        submitted_cols = set(re.findall(r'SELECT\s+(.*?)\s+FROM', sql_submitted, re.IGNORECASE | re.DOTALL))
        gold_cols = set(re.findall(r'SELECT\s+(.*?)\s+FROM', gold_sql, re.IGNORECASE | re.DOTALL))

        if submitted_cols != gold_cols:
            issues.append("Column selection differs from expected")

        return issues


def create_error_classifier() -> SQLErrorClassifier:
    """Factory function to create an error classifier."""
    return SQLErrorClassifier()
