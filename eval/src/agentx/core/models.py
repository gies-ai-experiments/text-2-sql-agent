"""Shared models for cross-developer interface contracts."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


# ============================================================
# SCHEMA MODELS (Dev 1 produces, Dev 2/3/4 consume)
# ============================================================

@dataclass
class ColumnInfo:
    """Column metadata from schema introspection."""
    name: str
    dtype: str
    nullable: bool
    primary_key: bool = False
    foreign_key: Optional[str] = None  # "table.column" format


@dataclass
class TableInfo:
    """Table metadata from schema introspection."""
    name: str
    columns: List[ColumnInfo]
    row_count: Optional[int] = None


@dataclass
class SchemaSnapshot:
    """Complete schema snapshot for validation."""
    dialect: str
    database: str
    tables: Dict[str, TableInfo]
    captured_at: datetime = field(default_factory=datetime.utcnow)

    def has_table(self, name: str) -> bool:
        return name.lower() in {t.lower() for t in self.tables}

    def has_column(self, table: str, column: str) -> bool:
        tbl = self.tables.get(table)
        if not tbl:
            return False
        return column.lower() in {c.name.lower() for c in tbl.columns}


# ============================================================
# VALIDATION MODELS (Dev 2 produces, Dev 3/4 consume)
# ============================================================

@dataclass
class IdentifierSet:
    """Extracted SQL identifiers."""
    tables: List[str]
    columns: List[str]  # "table.column" or just "column"
    functions: List[str]
    aliases: Dict[str, str]  # alias -> actual name


@dataclass
class HallucinationReport:
    """Report of phantom identifiers in SQL."""
    phantom_tables: List[str]
    phantom_columns: List[str]
    phantom_functions: List[str]
    total_hallucinations: int = 0
    hallucination_score: float = 0.0  # 0.0 = none, 1.0 = all phantom

    def __post_init__(self):
        self.total_hallucinations = (
            len(self.phantom_tables) +
            len(self.phantom_columns) +
            len(self.phantom_functions)
        )


@dataclass
class ValidationResult:
    """Result of SQL validation against schema."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    hallucination_report: Optional[HallucinationReport] = None


# ============================================================
# EXECUTION MODELS (Dev 4 produces)
# ============================================================

@dataclass
class ExecutionResult:
    """Result of SQL execution."""
    success: bool
    rows: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    timing_ms: float
    error: Optional[str] = None


@dataclass
class QueryPlan:
    """Query execution plan from EXPLAIN."""
    raw_plan: str
    estimated_cost: Optional[float] = None
    estimated_rows: Optional[int] = None


# ============================================================
# SCORING MODELS (Dev 4 produces)
# ============================================================

class ErrorCategory(Enum):
    """Error taxonomy categories."""
    SCHEMA_LINK = "schema_link"
    JOIN_ERROR = "join_error"
    SYNTAX_ERROR = "syntax_error"
    GROUNDING_ERROR = "grounding_error"
    TRUNCATION_ERROR = "truncation_error"
    DATA_ANALYSIS = "data_analysis"
    DOC_MISINTERPRET = "doc_misinterpret"
    UNKNOWN = "unknown"


@dataclass
class ComparisonResult:
    """Result of comparing actual vs expected results."""
    match: bool
    match_score: float  # 0.0 to 1.0
    strategy: str  # "exact", "set_based", "fuzzy", "schema_only"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiDimensionalScore:
    """Multi-dimensional evaluation score."""
    correctness: float          # 0.0 to 1.0, weight 40%
    hallucination_penalty: float  # 0.0 to 1.0, weight 25%
    efficiency: float           # 0.0 to 1.0, weight 15%
    grounding: float            # 0.0 to 1.0, weight 20%

    @property
    def weighted_total(self) -> float:
        return (
            self.correctness * 0.40 +
            (1.0 - self.hallucination_penalty) * 0.25 +
            self.efficiency * 0.15 +
            self.grounding * 0.20
        )


# ============================================================
# TASK MODELS (Shared)
# ============================================================

@dataclass
class Task:
    """Evaluation task definition."""
    id: str
    question: str
    database: str
    dialect: str
    difficulty: str  # "easy", "medium", "hard", "enterprise"
    gold_sql: str
    expected_result: Optional[List[Dict[str, Any]]] = None
    tags: List[str] = field(default_factory=list)


# ============================================================
# TOOL MODELS (Dev 3 produces, Dev 4 consumes)
# ============================================================

@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionTrace:
    """Trace of agent session."""
    task_id: str
    tool_calls: List[Dict[str, Any]]
    final_sql: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_tool_calls: int = 0