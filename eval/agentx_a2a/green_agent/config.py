"""
Configuration dataclasses for the AgentX Green Agent.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """Status of assessment task updates."""
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AssessmentConfig:
    """
    Configuration for an assessment session.

    Parsed from the assessment_request config field.
    """
    # Task selection
    difficulty: List[str] = field(default_factory=lambda: ["easy", "medium"])
    task_count: int = 10
    tags: Optional[List[str]] = None
    schema_type: str = "basic"  # "basic" or "enterprise"

    # Scoring
    scorer_preset: str = "default"  # "default", "strict", "performance", "quality"

    # Execution
    dialect: str = "sqlite"
    timeout_seconds: float = 30.0

    # Tournament mode
    same_tasks: bool = True  # All agents get same tasks
    parallel_evaluation: bool = True  # Evaluate agents in parallel

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssessmentConfig":
        """Parse configuration from assessment_request."""
        return cls(
            difficulty=data.get("difficulty", ["easy", "medium"]),
            task_count=data.get("task_count", 10),
            tags=data.get("tags"),
            schema_type=data.get("schema", "basic"),
            scorer_preset=data.get("scorer_preset", "default"),
            dialect=data.get("dialect", "sqlite"),
            timeout_seconds=data.get("timeout_seconds", 30.0),
            same_tasks=data.get("same_tasks", True),
            parallel_evaluation=data.get("parallel_evaluation", True),
        )


@dataclass
class TaskUpdate:
    """
    A2A Task Update for streaming progress during assessment.

    Emitted during orchestration to show assessment progress.
    """
    status: str  # "submitted", "working", "completed", "failed"
    message: str
    progress: Optional[float] = None  # 0.0 to 1.0
    data: Optional[Dict[str, Any]] = None
    artifact: Optional["AssessmentArtifact"] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for A2A protocol."""
        result = {
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.progress is not None:
            result["progress"] = self.progress
        if self.data is not None:
            result["data"] = self.data
        if self.artifact is not None:
            result["artifact"] = self.artifact.to_dict()
        return result


@dataclass
class ScoreSummary:
    """
    Summary of 7-dimension scores for a participant.

    Maps directly to EnhancedScore from evaluation/enhanced_scorer.py.
    """
    overall: float
    correctness: float
    efficiency: float
    safety: float
    completeness: float
    semantic_accuracy: float
    best_practices: float
    plan_quality: float

    # Sub-scores for detailed analysis
    hallucination_score: float = 1.0
    validation_score: float = 1.0
    performance_score: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "overall": round(self.overall, 4),
            "correctness": round(self.correctness, 4),
            "efficiency": round(self.efficiency, 4),
            "safety": round(self.safety, 4),
            "completeness": round(self.completeness, 4),
            "semantic_accuracy": round(self.semantic_accuracy, 4),
            "best_practices": round(self.best_practices, 4),
            "plan_quality": round(self.plan_quality, 4),
            "hallucination_score": round(self.hallucination_score, 4),
            "validation_score": round(self.validation_score, 4),
            "performance_score": round(self.performance_score, 4),
        }


@dataclass
class TaskResult:
    """Result of a single task evaluation for one participant."""
    task_id: str
    question: str
    sql_submitted: str
    gold_sql: Optional[str]
    scores: ScoreSummary
    execution_success: bool
    execution_time_ms: float
    rows_returned: int
    validation_errors: List[str] = field(default_factory=list)
    phantom_tables: List[str] = field(default_factory=list)
    phantom_columns: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    # Error classification for metrics tracking
    error_category: Optional[str] = None
    error_subcategory: Optional[str] = None
    error_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "task_id": self.task_id,
            "question": self.question,
            "sql_submitted": self.sql_submitted,
            "gold_sql": self.gold_sql,
            "scores": self.scores.to_dict(),
            "execution_success": self.execution_success,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "rows_returned": self.rows_returned,
            "validation_errors": self.validation_errors,
            "phantom_tables": self.phantom_tables,
            "phantom_columns": self.phantom_columns,
            "error_message": self.error_message,
        }
        # Include error classification if present
        if self.error_category:
            result["error_classification"] = {
                "category": self.error_category,
                "subcategory": self.error_subcategory,
                "details": self.error_details,
            }
        return result


@dataclass
class ParticipantSummary:
    """Summary of results for one participant (Purple Agent)."""
    participant_id: str
    endpoint: str
    total_tasks: int
    successful: int
    failed: int
    scores: ScoreSummary
    task_results: List[TaskResult] = field(default_factory=list)
    # Error metrics for this participant
    error_metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "participant_id": self.participant_id,
            "endpoint": self.endpoint,
            "total_tasks": self.total_tasks,
            "successful": self.successful,
            "failed": self.failed,
            "scores": self.scores.to_dict(),
            "task_results": [r.to_dict() for r in self.task_results],
        }
        if self.error_metrics:
            result["error_metrics"] = self.error_metrics
        return result


@dataclass
class RankedParticipant:
    """Participant with ranking information."""
    rank: int
    participant_id: str
    overall_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rank": self.rank,
            "participant_id": self.participant_id,
            "overall_score": round(self.overall_score, 4),
        }


@dataclass
class AssessmentArtifact:
    """
    Final A2A Artifact containing assessment results.

    Produced at the end of an assessment with rankings
    and detailed scores for all participants.
    """
    assessment_id: str
    completed_at: str
    config: Dict[str, Any]
    rankings: List[RankedParticipant]
    participants: Dict[str, ParticipantSummary]
    task_comparison: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Aggregate error metrics across all participants
    error_metrics_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for A2A artifact."""
        result = {
            "assessment_id": self.assessment_id,
            "completed_at": self.completed_at,
            "config": self.config,
            "rankings": [r.to_dict() for r in self.rankings],
            "participants": {
                pid: p.to_dict() for pid, p in self.participants.items()
            },
            "task_comparison": self.task_comparison,
            "metadata": self.metadata,
        }
        if self.error_metrics_summary:
            result["error_metrics_summary"] = self.error_metrics_summary
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=2)
