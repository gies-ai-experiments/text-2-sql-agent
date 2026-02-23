#!/usr/bin/env python3
"""
AgentBeats-compatible entrypoint for Sample Purple Agent (SQL Generator).

Starts a Purple Agent server that generates SQL using LLMs.

Features:
- Async-native with Quart (Flask-compatible)
- Health/readiness probes for Kubernetes

Usage:
    python entrypoint_purple.py --host 0.0.0.0 --port 8080 --llm gemini
    python entrypoint_purple.py --port 8081 --llm openai --model gpt-4o
"""

import argparse
import asyncio
import os
import sys

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from quart import Quart, request, jsonify
from quart_cors import cors

from agentx_a2a.purple_agent import SampleSQLAgent
from agentx_a2a.health import HealthChecker


def create_app(
    llm_provider: str = "gemini",
    model: str = None,
    api_key: str = None,
    card_url: str = None,
    agent_name: str = "Sample SQL Agent",
) -> Quart:
    """Create Quart app for Purple Agent."""
    app = Quart(__name__)
    cors(app)

    # Initialize SQL Agent
    agent = SampleSQLAgent(
        llm_provider=llm_provider,
        model=model,
        api_key=api_key,
    )

    # Initialize health checker
    health_checker = HealthChecker(agent=agent, version="1.0.0")

    @app.route("/", methods=["GET"])
    async def index():
        """Agent info endpoint."""
        return jsonify({
            "name": agent_name,
            "type": "purple_agent",
            "version": "1.0.0",
            "description": "Purple Agent that generates SQL using LLMs",
            "endpoints": {
                "info": "GET /",
                "health": "GET /health",
                "ready": "GET /ready",
                "generate": "POST /generate",
                "agent_card": "GET /.well-known/agent.json",
            },
            "capabilities": {
                "llm_provider": llm_provider,
                "model": model or "default",
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
        status = await health_checker.check_readiness()
        code = 200 if status.ready else 503
        return jsonify(status.to_dict()), code

    @app.route("/.well-known/agent.json", methods=["GET"])
    async def agent_card():
        """A2A Agent Card endpoint."""
        return jsonify({
            "name": agent_name,
            "description": f"Purple Agent that generates SQL queries using {llm_provider}",
            "version": "1.0.0",
            "url": card_url or request.host_url.rstrip("/"),
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "skills": [
                {
                    "id": "sql_generation",
                    "name": "SQL Generation",
                    "description": "Generates SQL queries from natural language questions",
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

    @app.route("/generate", methods=["POST"])
    async def generate():
        """
        Generate SQL from a task.

        Expected request body:
        {
            "task_id": "sqlite_simple_select",
            "question": "Get all customers from New York",
            "schema": {...},
            "dialect": "sqlite"
        }

        Returns:
        {
            "sql": "SELECT * FROM customers WHERE city = 'New York'",
            "reasoning": "...",
            "task_id": "sqlite_simple_select"
        }
        """
        data = await request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        if not data.get("question"):
            return jsonify({"error": "Question required"}), 400

        try:
            # Use async version if available, otherwise sync
            if hasattr(agent, 'handle_task'):
                result = await agent.handle_task(data)
            else:
                result = agent.handle_task_sync(data)
            return jsonify(result)

        except Exception as e:
            return jsonify({
                "sql": "",
                "error": str(e),
                "task_id": data.get("task_id"),
            }), 500

    # Also support A2A-style message endpoint
    @app.route("/a2a/message", methods=["POST"])
    async def a2a_message():
        """
        Handle A2A message format.

        The Green Agent may send messages in A2A format.
        """
        data = await request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        # Extract task from A2A message parts
        parts = data.get("parts", [])
        task_data = {}

        for part in parts:
            if part.get("type") == "data":
                task_data = part.get("data", {})
                break
            elif part.get("type") == "text":
                # Try to parse as task
                task_data = {"question": part.get("text", "")}

        if not task_data:
            task_data = data  # Fallback to whole body

        try:
            if hasattr(agent, 'handle_task'):
                result = await agent.handle_task(task_data)
            else:
                result = agent.handle_task_sync(task_data)
            return jsonify({
                "parts": [
                    {
                        "type": "data",
                        "data": result,
                    }
                ]
            })

        except Exception as e:
            return jsonify({
                "parts": [
                    {
                        "type": "data",
                        "data": {
                            "sql": "",
                            "error": str(e),
                        }
                    }
                ]
            }), 500

    @app.before_serving
    async def startup():
        """Initialize resources on startup."""
        print("Purple Agent starting up...")

    @app.after_serving
    async def shutdown():
        """Clean up resources on shutdown."""
        print("Purple Agent shutting down...")

    return app


def main():
    parser = argparse.ArgumentParser(
        description="Sample Purple Agent (SQL Generator)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind (default: 8080)"
    )
    parser.add_argument(
        "--card-url",
        help="URL for agent card advertisement"
    )
    parser.add_argument(
        "--llm",
        default="gemini",
        choices=["gemini", "openai"],
        help="LLM provider (default: gemini)"
    )
    parser.add_argument(
        "--model",
        help="Model name (optional, uses provider default)"
    )
    parser.add_argument(
        "--api-key",
        help="API key (optional, uses env variable)"
    )
    parser.add_argument(
        "--name",
        default="Sample SQL Agent",
        help="Agent name for identification"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    args = parser.parse_args()

    card_url = args.card_url or f"http://{args.host}:{args.port}"

    print(f"Starting Purple Agent '{args.name}' on {args.host}:{args.port}")
    print(f"LLM: {args.llm}, Model: {args.model or 'default'}")
    print(f"Agent card URL: {card_url}")

    app = create_app(
        llm_provider=args.llm,
        model=args.model,
        api_key=args.api_key,
        card_url=card_url,
        agent_name=args.name,
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
