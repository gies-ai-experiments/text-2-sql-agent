#!/usr/bin/env python3
"""
A2A-compatible entrypoint for AgentX Green Agent.

Uses the A2A server framework for proper protocol support with AgentBeats.
"""

import argparse
import os
import sys

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from a2a_executor_green import SQLBenchmarkExecutor


def main():
    parser = argparse.ArgumentParser(
        description="AgentX SQL Benchmark Green Agent (A2A)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9009,
        help="Port to bind (default: 9009)"
    )
    parser.add_argument(
        "--card-url",
        help="URL for agent card advertisement"
    )
    parser.add_argument(
        "--dialect",
        default="sqlite",
        choices=["sqlite", "duckdb", "postgresql"],
        help="SQL dialect (default: sqlite)"
    )
    parser.add_argument(
        "--scorer-preset",
        default="default",
        choices=["default", "strict", "performance", "quality"],
        help="Scorer preset (default: default)"
    )

    args = parser.parse_args()

    print(f"Starting AgentX Green Agent on {args.host}:{args.port}")
    print(f"Dialect: {args.dialect}, Scorer: {args.scorer_preset}")

    # Define agent skill
    skill = AgentSkill(
        id="sql_benchmark",
        name="SQL Benchmark Assessment",
        description="Evaluates SQL agents on correctness, efficiency, safety, completeness, semantic accuracy, best practices, and plan quality",
        tags=["benchmark", "sql", "evaluation"],
        examples=[
            '{"participants": {"sql_agent": "http://localhost:9009"}, "config": {"difficulty": ["easy", "medium"], "task_count": 5}}'
        ],
    )

    # Create agent card
    agent_card = AgentCard(
        name="AgentX SQL Benchmark",
        description="Green Agent for evaluating SQL-generating AI agents with 7-dimensional scoring",
        url=args.card_url or f"http://{args.host}:{args.port}/",
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    # Create executor
    executor = SQLBenchmarkExecutor(
        dialect=args.dialect,
        scorer_preset=args.scorer_preset,
    )

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    # Create A2A server
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # Run server
    uvicorn.run(server.build(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
