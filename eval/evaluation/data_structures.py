"""
Data structures for evaluation components.

All data flows through these structures:
    SQLAgent output → AgentResult → ExecutionResult → Scorer → MultiDimensionalScore
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionResult:
    """
    Captures the outcome of SQL execution from SQLAgent.

    Contains:
        - Execution results (success, data, timing)
        - Validation metadata (is_valid, errors, warnings)
        - Analysis metadata (insights, summary)
    """
    # Execution results
    success: bool
    data: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    rows_returned: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None

    # Validation metadata (from SQLAgent)
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    query_type: Optional[str] = None
    tables_accessed: List[str] = field(default_factory=list)
    columns_accessed: List[str] = field(default_factory=list)

    # Analysis metadata (from SQLAgent)
    insights: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ComparisonResult:
    """
    Result of comparing actual vs expected query results.
    
    Used for correctness scoring.
    """
    is_match: bool
    match_score: float = 0.0  # 0.0 to 1.0
    row_count_match: bool = False
    column_count_match: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryPlan:
    """
    Holds SQL execution plan metadata.
    
    Optional - only used if query plan analysis is enabled.
    """
    plan_text: str = ""
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    plan_nodes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MultiDimensionalScore:
    """
    Multi-dimensional weighted score for a task.

    Dimensions:
        - correctness (40%): Did the query return correct results?
        - efficiency (20%): How fast did it execute?
        - safety (25%): Was the query valid? Any hallucinations?
        - result_completeness (15%): Quality of results (nulls, truncation, etc.)

    The overall score is a weighted sum of all dimensions.
    """
    # Core dimension scores (0.0 to 1.0)
    correctness: float = 0.0
    efficiency: float = 0.0
    safety: float = 0.0
    result_completeness: float = 0.0

    # Sub-scores (for detailed analysis)
    validation_score: float = 0.0
    performance_score: float = 0.0
    hallucination_score: float = 0.0

    # Final weighted score
    overall: float = 0.0

    # Configurable weights
    weights: Dict[str, float] = field(default_factory=lambda: {
        "correctness": 0.40,
        "efficiency": 0.20,
        "safety": 0.25,
        "result_completeness": 0.15
    })

    # Detailed breakdown for debugging
    details: Dict[str, Any] = field(default_factory=dict)

    def compute_overall(self) -> float:
        """
        Compute weighted overall score.
        
        Formula:
            overall = (correctness × 0.40) + (efficiency × 0.20) + 
                      (safety × 0.25) + (result_completeness × 0.15)
        """
        self.overall = (
            self.weights.get("correctness", 0.4) * self.correctness +
            self.weights.get("efficiency", 0.2) * self.efficiency +
            self.weights.get("safety", 0.25) * self.safety +
            self.weights.get("result_completeness", 0.15) * self.result_completeness
        )
        return self.overall


@dataclass
class AgentResult:
    """
    Wrapper for SQLAgent's process_query() output.

    Converts SQLAgent's dictionary output to typed ExecutionResult.
    """
    query: str
    timestamp: str
    overall_status: str  # "SUCCESS" or "FAILED"

    # Raw data from SQLAgent
    validation: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_agent_output(cls, agent_output: Dict[str, Any]) -> "AgentResult":
        """Create AgentResult from SQLAgent's process_query() output."""
        return cls(
            query=agent_output.get("query", ""),
            timestamp=agent_output.get("timestamp", ""),
            overall_status=agent_output.get("overall_status", "FAILED"),
            validation=agent_output.get("validation", {}),
            execution=agent_output.get("execution", {}),
            analysis=agent_output.get("analysis", {}),
        )

    def to_execution_result(self) -> ExecutionResult:
        """
        Convert to ExecutionResult for scoring.
        
        Maps SQLAgent output fields to ExecutionResult fields.
        """
        validation = self.validation
        execution = self.execution
        analysis = self.analysis

        return ExecutionResult(
            # Execution results
            success=execution.get("success", False),
            data=execution.get("data", []),
            columns=execution.get("columns", []),
            rows_returned=execution.get("rows_returned", 0),
            execution_time_ms=execution.get("execution_time_ms", 0.0),
            error=execution.get("error"),
            
            # Validation metadata
            is_valid=validation.get("is_valid", False),
            validation_errors=validation.get("errors", []),
            validation_warnings=validation.get("warnings", []),
            query_type=validation.get("query_type"),
            tables_accessed=validation.get("tables_accessed", []),
            columns_accessed=validation.get("columns_accessed", []),
            
            # Analysis metadata
            insights=analysis.get("insights", []),
            summary=analysis.get("summary", ""),
        )