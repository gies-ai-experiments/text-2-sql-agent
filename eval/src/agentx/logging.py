"""
Structured JSON Logging for AgentX.

Provides consistent, machine-readable logging across all components.

Features:
- JSON-formatted log output
- Structured fields for filtering and analysis
- Request/response correlation IDs
- Performance metrics logging
- Error context capture

Usage:
    from agentx.logging import get_logger, LogContext

    logger = get_logger(__name__)

    # Basic logging
    logger.info("Processing query", sql=sql, dialect=dialect)

    # With context
    with LogContext(request_id="abc-123", agent_id="agent-1"):
        logger.info("Evaluation started")
        # ... all logs within context include request_id and agent_id
"""

import json
import logging
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional
from threading import local
import uuid

# Thread-local storage for context
_context = local()


def get_context() -> Dict[str, Any]:
    """Get current logging context."""
    return getattr(_context, "data", {})


def set_context(**kwargs):
    """Set logging context values."""
    if not hasattr(_context, "data"):
        _context.data = {}
    _context.data.update(kwargs)


def clear_context():
    """Clear logging context."""
    _context.data = {}


@contextmanager
def LogContext(**kwargs):
    """
    Context manager for structured logging context.

    Usage:
        with LogContext(request_id="abc", agent_id="123"):
            logger.info("Processing")  # Includes request_id and agent_id
    """
    old_context = getattr(_context, "data", {}).copy()
    set_context(**kwargs)
    try:
        yield
    finally:
        _context.data = old_context


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.123456",
        "level": "INFO",
        "logger": "agentx.server",
        "message": "Query processed",
        "context": {"request_id": "abc-123"},
        "data": {"sql": "SELECT ...", "duration_ms": 15.2}
    }
    """

    def __init__(self, include_traceback: bool = True):
        super().__init__()
        self.include_traceback = include_traceback

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context from thread-local storage
        context = get_context()
        if context:
            log_data["context"] = context

        # Add extra fields from the record
        extra_data = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName",
            }:
                extra_data[key] = self._serialize(value)

        if extra_data:
            log_data["data"] = extra_data

        # Add exception info
        if record.exc_info and self.include_traceback:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info[0] else None,
            }

        # Add source location
        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, default=str)

    def _serialize(self, value: Any) -> Any:
        """Serialize value for JSON output."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, (list, tuple)):
            return [self._serialize(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        elif hasattr(value, "to_dict"):
            return value.to_dict()
        elif hasattr(value, "__dict__"):
            return {k: self._serialize(v) for k, v in value.__dict__.items() if not k.startswith("_")}
        else:
            return str(value)


class StructuredLogger(logging.Logger):
    """
    Logger with structured logging support.

    Allows passing extra fields directly to log methods:
        logger.info("Query executed", sql=sql, duration_ms=15.2)
    """

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1, **kwargs):
        """Override to support keyword arguments as extra fields."""
        if extra is None:
            extra = {}
        extra.update(kwargs)
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)


# Register our custom logger class
logging.setLoggerClass(StructuredLogger)


def get_logger(name: str, level: int = logging.INFO, json_output: bool = True) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Logging level
        json_output: Whether to output JSON (False for human-readable)

    Returns:
        Configured StructuredLogger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    logger.addHandler(handler)

    return logger


def configure_logging(
    level: int = logging.INFO,
    json_output: bool = True,
    include_traceback: bool = True,
):
    """
    Configure global logging settings.

    Args:
        level: Logging level
        json_output: Whether to use JSON format
        include_traceback: Include tracebacks in error logs
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers = []

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        handler.setFormatter(JSONFormatter(include_traceback=include_traceback))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    root_logger.addHandler(handler)


# =============================================================================
# SPECIALIZED LOG EVENTS
# =============================================================================

@dataclass
class QueryEvent:
    """Structured event for query processing."""
    event_type: str = "query"
    query_id: str = ""
    sql: str = ""
    dialect: str = ""
    status: str = ""  # "started", "validated", "executed", "scored", "failed"
    duration_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.query_id:
            self.query_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationEvent:
    """Structured event for evaluation results."""
    event_type: str = "evaluation"
    request_id: str = ""
    agent_id: str = ""
    task_id: str = ""
    status: str = ""  # "success", "failed", "error"
    scores: Dict[str, float] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationEvent:
    """Structured event for validation results."""
    event_type: str = "validation"
    query_id: str = ""
    is_valid: bool = False
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    hallucinations: Dict[str, list] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceEvent:
    """Structured event for performance metrics."""
    event_type: str = "performance"
    operation: str = ""
    duration_ms: float = 0.0
    rows_processed: int = 0
    memory_mb: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventLogger:
    """
    High-level event logger for common operations.

    Usage:
        event_logger = EventLogger()

        # Log query processing
        event_logger.log_query_start(sql, dialect)
        # ... process query ...
        event_logger.log_query_complete(query_id, duration_ms, status)

        # Log evaluation
        event_logger.log_evaluation(request_id, agent_id, task_id, scores)
    """

    def __init__(self, logger_name: str = "agentx.events"):
        self.logger = get_logger(logger_name)

    def log_query_start(self, sql: str, dialect: str) -> str:
        """Log query processing start. Returns query_id."""
        event = QueryEvent(
            sql=sql[:200] + "..." if len(sql) > 200 else sql,
            dialect=dialect,
            status="started",
        )
        self.logger.info(
            "Query processing started",
            event=event.to_dict(),
        )
        return event.query_id

    def log_query_validated(self, query_id: str, is_valid: bool, errors: list = None, duration_ms: float = 0):
        """Log query validation result."""
        event = ValidationEvent(
            query_id=query_id,
            is_valid=is_valid,
            errors=errors or [],
            duration_ms=duration_ms,
        )
        self.logger.info(
            "Query validated",
            event=event.to_dict(),
        )

    def log_query_complete(self, query_id: str, duration_ms: float, status: str, rows: int = 0, error: str = None):
        """Log query processing completion."""
        event = QueryEvent(
            query_id=query_id,
            status=status,
            duration_ms=duration_ms,
            error=error,
            metadata={"rows_returned": rows},
        )
        level = logging.INFO if status == "success" else logging.WARNING
        self.logger.log(
            level,
            f"Query processing {status}",
            event=event.to_dict(),
        )

    def log_evaluation(
        self,
        request_id: str,
        agent_id: str,
        task_id: str,
        status: str,
        scores: Dict[str, float] = None,
        duration_ms: float = 0,
    ):
        """Log evaluation result."""
        event = EvaluationEvent(
            request_id=request_id,
            agent_id=agent_id,
            task_id=task_id,
            status=status,
            scores=scores or {},
            duration_ms=duration_ms,
        )
        self.logger.info(
            f"Evaluation {status}",
            event=event.to_dict(),
        )

    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics."""
        event = PerformanceEvent(
            operation=operation,
            duration_ms=duration_ms,
            metadata=kwargs,
        )
        self.logger.debug(
            f"Performance: {operation}",
            event=event.to_dict(),
        )


# Default event logger instance
event_logger = EventLogger()
