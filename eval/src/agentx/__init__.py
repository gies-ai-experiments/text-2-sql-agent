"""
AgentX - Multi-Dialect SQL Agent Evaluation Framework

A framework for evaluating LLM-powered SQL agents with:
- Multi-dialect support (SQLite, DuckDB, PostgreSQL, BigQuery, Snowflake)
- Hallucination detection (phantom tables, columns, functions)
- Multi-dimensional scoring (correctness, efficiency, safety)
- Dialect-aware SQL parsing and validation

Quick Start:
    from agentx import SQLAgent, AgentConfig

    # SQLite (zero setup)
    agent = SQLAgent(AgentConfig(dialect="sqlite"))

    # Execute a query
    result = agent.process_query("SELECT 1 + 1 as answer")
    print(result.data)  # [{'answer': 2}]

    # DuckDB
    agent = SQLAgent(AgentConfig(dialect="duckdb"))

    # PostgreSQL
    agent = SQLAgent(AgentConfig(
        dialect="postgresql",
        connection_string="postgresql://user:pass@localhost/db"
    ))
"""

from .dialects import Dialect, DialectConfig, get_dialect_config, get_supported_dialects
from .infrastructure import (
    ColumnInfo,
    TableInfo,
    SchemaSnapshot,
    DatabaseAdapter,
    create_adapter,
)
from .validation import (
    MultiDialectSQLParser,
    HallucinationDetector,
    HallucinationReport,
    ValidationResult,
)
from .executor import SQLExecutor, ExecutorConfig, ExecutorResult
from .logging import (
    get_logger,
    configure_logging,
    LogContext,
    EventLogger,
    event_logger,
)

__version__ = "0.1.0"

__all__ = [
    # Dialects
    "Dialect",
    "DialectConfig",
    "get_dialect_config",
    "get_supported_dialects",
    # Infrastructure
    "ColumnInfo",
    "TableInfo",
    "SchemaSnapshot",
    "DatabaseAdapter",
    "create_adapter",
    # Validation
    "MultiDialectSQLParser",
    "HallucinationDetector",
    "HallucinationReport",
    "ValidationResult",
    # Executor
    "SQLExecutor",
    "ExecutorConfig",
    "ExecutorResult",
    # Logging
    "get_logger",
    "configure_logging",
    "LogContext",
    "EventLogger",
    "event_logger",
]
