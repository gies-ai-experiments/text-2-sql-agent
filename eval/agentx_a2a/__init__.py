"""
A2A (Agent-to-Agent) Protocol Interface for AgentX SQL Benchmark.

This module provides a standardized interface for external agents to:
1. Discover available evaluation tasks
2. Submit SQL queries for evaluation
3. Receive detailed scoring feedback

Compliant with common agent communication patterns.
"""

__all__ = []

# Import server components (only available in Green Agent)
try:
    from .server import A2AServer, create_app
    from .models import (
        TaskRequest,
        TaskResponse,
        EvaluationRequest,
        EvaluationResponse,
        AgentInfo,
        BenchmarkInfo,
    )
    from .client import A2AClient

    __all__.extend([
        "A2AServer",
        "create_app",
        "TaskRequest",
        "TaskResponse",
        "EvaluationRequest",
        "EvaluationResponse",
        "AgentInfo",
        "BenchmarkInfo",
        "A2AClient",
    ])
except ImportError:
    pass

# Import Green Agent components
try:
    from .green_agent import (
        SQLBenchmarkGreenAgent,
        AssessmentConfig,
        TaskUpdate,
        AssessmentArtifact,
        ArtifactBuilder,
    )

    __all__.extend([
        "SQLBenchmarkGreenAgent",
        "AssessmentConfig",
        "TaskUpdate",
        "AssessmentArtifact",
        "ArtifactBuilder",
    ])
except ImportError:
    pass

# Import Purple Agent components
try:
    from .purple_agent import SampleSQLAgent, LLMClient

    __all__.extend([
        "SampleSQLAgent",
        "LLMClient",
    ])
except ImportError:
    pass
