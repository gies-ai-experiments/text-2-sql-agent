"""
A2A Protocol Data Models.

Defines the request/response formats for agent communication.
These models follow common patterns for agent-to-agent communication.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import uuid


class TaskStatus(Enum):
    """Status of an evaluation task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Difficulty(Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ENTERPRISE = "enterprise"


@dataclass
class AgentInfo:
    """
    Information about an agent participating in evaluation.

    Agents should register with this info before submitting evaluations.
    """
    agent_id: str
    agent_name: str
    agent_version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = ""

    def __post_init__(self):
        if not self.registered_at:
            self.registered_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        return cls(**data)


@dataclass
class BenchmarkInfo:
    """
    Information about the benchmark system.

    Returned by the /info endpoint.
    """
    name: str = "AgentX SQL Benchmark"
    version: str = "1.0.0"
    description: str = "Multi-dialect SQL evaluation framework for LLM agents"
    supported_dialects: List[str] = field(default_factory=lambda: [
        "sqlite", "duckdb", "postgresql", "bigquery"
    ])
    scoring_dimensions: List[str] = field(default_factory=lambda: [
        "correctness", "efficiency", "safety", "completeness",
        "semantic_accuracy", "best_practices", "plan_quality"
    ])
    api_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskDefinition:
    """
    Definition of an evaluation task.

    This is what agents receive when requesting tasks.
    """
    task_id: str
    question: str  # Natural language question
    dialect: str
    difficulty: str
    schema_info: Dict[str, Any]  # Available tables and columns
    tags: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    time_limit_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskDefinition":
        return cls(**data)


@dataclass
class TaskRequest:
    """
    Request for evaluation tasks.

    Agents can filter by dialect, difficulty, or tags.
    """
    agent_id: str
    dialect: Optional[str] = None
    difficulty: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = 10
    exclude_completed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRequest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskResponse:
    """
    Response containing evaluation tasks.
    """
    tasks: List[TaskDefinition]
    total_available: int
    session_id: str = ""

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "total_available": self.total_available,
            "session_id": self.session_id,
        }


@dataclass
class EvaluationRequest:
    """
    Request to evaluate an agent's SQL query.

    The agent submits their generated SQL for a specific task.
    """
    agent_id: str
    task_id: str
    sql: str
    session_id: Optional[str] = None
    execution_trace: Optional[List[Dict[str, Any]]] = None  # Optional reasoning trace
    metadata: Dict[str, Any] = field(default_factory=dict)
    submitted_at: str = ""

    def __post_init__(self):
        if not self.submitted_at:
            self.submitted_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationRequest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ScoreBreakdown:
    """
    Detailed score breakdown across all dimensions.
    """
    overall: float
    correctness: float
    efficiency: float
    safety: float
    completeness: float
    semantic_accuracy: float
    best_practices: float
    plan_quality: float

    # Sub-scores
    validation_score: float = 1.0
    hallucination_score: float = 1.0
    performance_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationResult:
    """
    Result of evaluating a single SQL query.
    """
    task_id: str
    status: str  # "success", "failed", "error"
    scores: Optional[ScoreBreakdown] = None

    # Execution details
    execution_success: bool = False
    rows_returned: int = 0
    execution_time_ms: float = 0.0

    # Validation details
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)

    # Hallucination details
    phantom_tables: List[str] = field(default_factory=list)
    phantom_columns: List[str] = field(default_factory=list)

    # Comparison with gold (if available)
    matches_gold: Optional[bool] = None
    match_score: float = 0.0

    # Analysis
    insights: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # Error info
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.scores:
            result["scores"] = self.scores.to_dict()
        return result


@dataclass
class EvaluationResponse:
    """
    Response containing evaluation results.
    """
    request_id: str
    agent_id: str
    results: List[EvaluationResult]
    summary: Dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = ""

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        if not self.evaluated_at:
            self.evaluated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class BatchEvaluationRequest:
    """
    Request to evaluate multiple SQL queries at once.
    """
    agent_id: str
    submissions: List[Dict[str, str]]  # List of {task_id, sql}
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchEvaluationRequest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LeaderboardEntry:
    """
    Entry in the benchmark leaderboard.
    """
    agent_id: str
    agent_name: str
    total_tasks: int
    completed_tasks: int
    average_score: float
    scores_by_dimension: Dict[str, float]
    scores_by_difficulty: Dict[str, float]
    last_submission: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SessionState:
    """
    State of an evaluation session.
    """
    session_id: str
    agent_id: str
    started_at: str
    tasks_assigned: List[str]
    tasks_completed: List[str]
    current_scores: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
