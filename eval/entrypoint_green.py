#!/usr/bin/env python3
"""
AgentBeats-compatible entrypoint for AgentX Green Agent.

Starts the SQL Benchmark Green Agent server that evaluates Purple Agents.

Features:
- Async-native with Quart (Flask-compatible)
- Resilient HTTP communication with retry and circuit breaker
- Health/readiness probes for Kubernetes

Usage:
    python entrypoint_green.py --host 0.0.0.0 --port 8001
    python entrypoint_green.py --port 8001 --dialect sqlite --scorer-preset strict
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from quart import Quart, request, jsonify, Response
from quart_cors import cors

from agentx_a2a.green_agent import SQLBenchmarkGreenAgent, AssessmentConfig
from agentx_a2a.health import HealthChecker
from agentx_a2a.resilience import ResilientHTTPClient, TimeoutConfig


def create_app(
    dialect: str = "sqlite",
    scorer_preset: str = "default",
    card_url: str = None,
) -> Quart:
    """Create Quart app for Green Agent."""
    app = Quart(__name__)
    cors(app)

    # Initialize Green Agent
    agent = SQLBenchmarkGreenAgent(
        dialect=dialect,
        scorer_preset=scorer_preset,
    )

    # Initialize resilient HTTP client
    http_client = ResilientHTTPClient(TimeoutConfig())

    # Initialize health checker
    health_checker = HealthChecker(agent=agent, version="1.0.0")

    @app.route("/", methods=["GET"])
    async def index():
        """Agent info endpoint."""
        return jsonify({
            "name": "AgentX SQL Benchmark",
            "type": "green_agent",
            "version": "1.0.0",
            "description": "Green Agent for evaluating SQL-generating AI agents",
            "endpoints": {
                "info": "GET /",
                "health": "GET /health",
                "ready": "GET /ready",
                "schema": "GET /schema",
                "assess": "POST /assess",
                "assess_stream": "POST /assess/stream",
                "agent_card": "GET /.well-known/agent.json",
            },
            "capabilities": {
                "scoring_dimensions": 7,
                "supported_dialects": ["sqlite", "duckdb", "postgresql"],
                "multi_agent": True,
                "streaming": True,
                "resilience": {
                    "retry": True,
                    "circuit_breaker": True,
                    "adaptive_timeouts": True,
                }
            }
        })

    @app.route("/health", methods=["GET"])
    async def health():
        """
        Liveness probe endpoint.

        Quick check to verify process is alive.
        Used by Kubernetes liveness probes.
        """
        status = await health_checker.check_liveness()
        return jsonify(status.to_dict())

    @app.route("/ready", methods=["GET"])
    async def ready():
        """
        Readiness probe endpoint.

        Full check to verify service can handle requests.
        Used by Kubernetes readiness probes.
        """
        # Add executor to health checker for database check
        if agent._executor:
            health_checker.executor = agent._executor

        status = await health_checker.check_readiness()
        code = 200 if status.ready else 503
        return jsonify(status.to_dict()), code

    @app.route("/schema", methods=["GET"])
    async def schema():
        """Get database schema for Purple Agents."""
        schema_info = agent.get_schema_info()
        return jsonify(schema_info)

    @app.route("/.well-known/agent.json", methods=["GET"])
    async def agent_card():
        """A2A Agent Card endpoint."""
        return jsonify({
            "name": "AgentX SQL Benchmark",
            "description": "Green Agent for evaluating SQL-generating AI agents with 7-dimensional scoring",
            "version": "1.0.0",
            "url": card_url or request.host_url.rstrip("/"),
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
            },
            "skills": [
                {
                    "id": "sql_benchmark",
                    "name": "SQL Benchmark Assessment",
                    "description": "Evaluates SQL agents on correctness, efficiency, safety, completeness, semantic accuracy, best practices, and plan quality",
                    "inputModes": ["application/json"],
                    "outputModes": ["application/json"],
                    "tags": [],
                }
            ],
            "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["application/json"],
        })

    @app.route("/.well-known/agent-card.json", methods=["GET"])
    async def agent_card_json():
        """A2A Agent Card endpoint (AgentBeats alias)."""
        return await agent_card()

    @app.route("/assess", methods=["POST"])
    async def assess():
        """
        Start an assessment.

        Expected request body:
        {
            "participants": {
                "agent_1": "http://purple-agent-1:8080",
                "agent_2": "http://purple-agent-2:8081"
            },
            "config": {
                "difficulty": ["easy", "medium"],
                "task_count": 10,
                "scorer_preset": "default"
            }
        }
        """
        data = await request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        participants = data.get("participants", {})
        config = data.get("config", {})

        if not participants:
            return jsonify({"error": "No participants specified"}), 400

        try:
            # Run assessment asynchronously (native async)
            updates = []
            async for update in agent.handle_assessment(participants, config):
                updates.append(update.to_dict())

            # Find the final artifact
            final_update = updates[-1] if updates else {}
            artifact = final_update.get("artifact")

            return jsonify({
                "status": "completed",
                "updates": updates,
                "artifact": artifact,
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "error": str(e),
            }), 500

    @app.route("/assess/stream", methods=["POST"])
    async def assess_stream():
        """
        Start an assessment with streaming updates.

        Returns Server-Sent Events (SSE) stream.
        """
        data = await request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        participants = data.get("participants", {})
        config = data.get("config", {})

        if not participants:
            return jsonify({"error": "No participants specified"}), 400

        async def generate():
            """Async generator for SSE stream."""
            try:
                async for update in agent.handle_assessment(participants, config):
                    yield f"data: {json.dumps(update.to_dict())}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    @app.before_serving
    async def startup():
        """Initialize resources on startup."""
        print("Green Agent starting up...")

    @app.after_serving
    async def shutdown():
        """Clean up resources on shutdown."""
        print("Green Agent shutting down...")
        await http_client.close()
        agent.close()

    return app


def main():
    parser = argparse.ArgumentParser(
        description="AgentX SQL Benchmark Green Agent"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to bind (default: 8001)"
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    args = parser.parse_args()

    card_url = args.card_url or f"http://{args.host}:{args.port}"

    print(f"Starting AgentX Green Agent on {args.host}:{args.port}")
    print(f"Dialect: {args.dialect}, Scorer: {args.scorer_preset}")
    print(f"Agent card URL: {card_url}")

    app = create_app(
        dialect=args.dialect,
        scorer_preset=args.scorer_preset,
        card_url=card_url,
    )

    # Use hypercorn for production-ready async server
    try:
        from hypercorn.config import Config
        from hypercorn.asyncio import serve

        config = Config()
        config.bind = [f"{args.host}:{args.port}"]
        config.accesslog = "-"  # Log to stdout

        asyncio.run(serve(app, config))
    except ImportError:
        # Fallback to Quart's built-in server (development only)
        print("Warning: hypercorn not installed, using development server")
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
        )


if __name__ == "__main__":
    main()
