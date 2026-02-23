"""
A2A Protocol REST API Server.

Provides standardized endpoints for external agents to:
- Discover benchmark info and available tasks
- Register agents
- Submit SQL queries for evaluation
- Get detailed scoring feedback
- View leaderboard

Run with: python -m a2a.server
"""

import os
import sys
import json
import uuid
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from functools import wraps

from flask import Flask, request, jsonify, Response, g
from flask_cors import CORS

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from .models import (
    AgentInfo,
    BenchmarkInfo,
    TaskDefinition,
    TaskRequest,
    TaskResponse,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationResult,
    ScoreBreakdown,
    BatchEvaluationRequest,
    LeaderboardEntry,
    SessionState,
)

# Import structured logging
try:
    from agentx.logging import (
        get_logger,
        configure_logging,
        LogContext,
        event_logger,
    )
    # Configure JSON logging
    configure_logging(json_output=os.environ.get("LOG_FORMAT", "json") == "json")
    logger = get_logger("a2a.server")
except ImportError:
    # Fallback to basic logging if agentx.logging not available
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("a2a.server")
    event_logger = None
    LogContext = None


class A2AServer:
    """
    A2A Protocol Server for SQL Benchmark.

    Manages:
    - Agent registration
    - Task distribution
    - Evaluation processing
    - Leaderboard tracking
    """

    def __init__(
        self,
        tasks_path: Optional[str] = None,
        dialect: str = "sqlite",
    ):
        """
        Initialize the A2A server.

        Args:
            tasks_path: Path to gold queries JSON file
            dialect: Default SQL dialect
        """
        self.dialect = dialect
        self.tasks_path = tasks_path or self._default_tasks_path()

        # In-memory state (use Redis/DB for production)
        self.agents: Dict[str, AgentInfo] = {}
        self.sessions: Dict[str, SessionState] = {}
        self.results: Dict[str, List[EvaluationResult]] = {}  # agent_id -> results
        self.tasks: Dict[str, TaskDefinition] = {}

        # Load tasks
        self._load_tasks()

        # Initialize executor lazily
        self._executor = None
        self._scorer = None

    def _default_tasks_path(self) -> str:
        """Get default tasks path."""
        base = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(base, "tasks", "gold_queries", "sqlite", "basic_queries.json")

    def _load_tasks(self):
        """Load evaluation tasks from JSON file."""
        if not os.path.exists(self.tasks_path):
            logger.warning(f"Tasks file not found: {self.tasks_path}")
            return

        with open(self.tasks_path, 'r') as f:
            raw_tasks = json.load(f)

        for task in raw_tasks:
            task_def = TaskDefinition(
                task_id=task["id"],
                question=task["question"],
                dialect=task.get("dialect", self.dialect),
                difficulty=task.get("difficulty", "medium"),
                schema_info={},  # Will be populated on request
                tags=task.get("tags", []),
            )
            self.tasks[task_def.task_id] = task_def

        logger.info(f"Loaded {len(self.tasks)} tasks from {self.tasks_path}")

    def _get_executor(self):
        """Lazy-load the SQL executor."""
        if self._executor is None:
            from agentx import SQLExecutor, ExecutorConfig

            self._executor = SQLExecutor(ExecutorConfig(dialect=self.dialect))

            # Create sample tables for evaluation
            self._setup_sample_data()

        return self._executor

    def _get_scorer(self):
        """Lazy-load the enhanced scorer."""
        if self._scorer is None:
            from evaluation.enhanced_scorer import EnhancedScorer
            self._scorer = EnhancedScorer()
        return self._scorer

    def _setup_sample_data(self):
        """Setup sample data for evaluation."""
        executor = self._executor

        # Create customers table
        executor.adapter.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                city TEXT,
                phone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create orders table
        executor.adapter.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date TEXT,
                total REAL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)

        # Insert sample data
        sample_customers = [
            (1, 'Alice Johnson', 'alice@example.com', 'New York', '555-0101'),
            (2, 'Bob Smith', 'bob@example.com', 'Los Angeles', '555-0102'),
            (3, 'Charlie Brown', 'charlie@example.com', 'Chicago', '555-0103'),
            (4, 'Diana Ross', 'diana@example.com', 'New York', '555-0104'),
            (5, 'Edward Kim', 'edward@example.com', 'San Francisco', None),
        ]

        for c in sample_customers:
            try:
                executor.adapter.execute(
                    f"INSERT OR IGNORE INTO customers (id, name, email, city, phone) VALUES ({c[0]}, '{c[1]}', '{c[2]}', '{c[3]}', {repr(c[4])})"
                )
            except Exception:
                pass

        sample_orders = [
            (1, 1, '2024-01-15', 150.00, 'completed'),
            (2, 1, '2024-02-20', 75.50, 'completed'),
            (3, 2, '2024-01-25', 200.00, 'completed'),
            (4, 3, '2024-03-01', 50.00, 'pending'),
            (5, 4, '2024-03-10', 1200.00, 'completed'),
        ]

        for o in sample_orders:
            try:
                executor.adapter.execute(
                    f"INSERT OR IGNORE INTO orders (id, customer_id, order_date, total, status) VALUES ({o[0]}, {o[1]}, '{o[2]}', {o[3]}, '{o[4]}')"
                )
            except Exception:
                pass

        executor.refresh_schema()
        logger.info("Sample data setup complete")

    def get_benchmark_info(self) -> BenchmarkInfo:
        """Get benchmark information."""
        return BenchmarkInfo()

    def register_agent(self, agent_info: AgentInfo) -> AgentInfo:
        """Register a new agent."""
        if not agent_info.agent_id:
            agent_info.agent_id = str(uuid.uuid4())

        agent_info.registered_at = datetime.utcnow().isoformat()
        self.agents[agent_info.agent_id] = agent_info
        self.results[agent_info.agent_id] = []

        logger.info(f"Registered agent: {agent_info.agent_name} ({agent_info.agent_id})")
        return agent_info

    def get_tasks(self, task_request: TaskRequest) -> TaskResponse:
        """Get available tasks based on filter criteria."""
        filtered_tasks = []

        for task in self.tasks.values():
            # Apply filters
            if task_request.dialect and task.dialect != task_request.dialect:
                continue
            if task_request.difficulty and task.difficulty != task_request.difficulty:
                continue
            if task_request.tags:
                if not any(tag in task.tags for tag in task_request.tags):
                    continue

            # Add schema info
            executor = self._get_executor()
            task.schema_info = executor.get_schema_info()

            filtered_tasks.append(task)

            if len(filtered_tasks) >= task_request.limit:
                break

        return TaskResponse(
            tasks=filtered_tasks,
            total_available=len(self.tasks),
        )

    def evaluate_submission(self, eval_request: EvaluationRequest) -> EvaluationResult:
        """Evaluate a single SQL submission."""
        task_id = eval_request.task_id
        sql = eval_request.sql

        # Validate task exists
        if task_id not in self.tasks:
            return EvaluationResult(
                task_id=task_id,
                status="error",
                error_message=f"Unknown task: {task_id}",
            )

        task = self.tasks[task_id]
        executor = self._get_executor()
        scorer = self._get_scorer()

        # Process the query
        result = executor.process_query(sql, verbose=False)

        # Build evaluation result
        eval_result = EvaluationResult(
            task_id=task_id,
            status="success" if result.success else "failed",
            execution_success=result.success,
            rows_returned=len(result.data) if result.data else 0,
            execution_time_ms=result.execution.get("execution_time_ms", 0),
            is_valid=result.is_valid,
            validation_errors=result.validation.get("errors", []),
            validation_warnings=result.validation.get("warnings", []),
            insights=result.analysis.get("insights", []),
        )

        # Extract hallucination info
        hall_report = result.validation.get("hallucination_report", {})
        if hall_report:
            eval_result.phantom_tables = hall_report.get("phantom_tables", [])
            eval_result.phantom_columns = hall_report.get("phantom_columns", [])

        # Score the result
        if result.success:
            from evaluation.data_structures import ComparisonResult, ExecutionResult as EvalExecutionResult

            # Create comparison (self-comparison for now)
            comparison = ComparisonResult(
                is_match=True,
                match_score=1.0,
                row_count_match=True,
                column_count_match=True,
            )

            # Create execution result for scorer
            exec_result = EvalExecutionResult(
                success=result.success,
                data=result.data,
                rows_returned=len(result.data) if result.data else 0,
                execution_time_ms=result.execution.get("execution_time_ms", 0),
                is_valid=result.is_valid,
                validation_errors=result.validation.get("errors", []),
                validation_warnings=result.validation.get("warnings", []),
                query_type=result.validation.get("query_type", "SELECT"),
                tables_accessed=result.validation.get("tables_accessed", []),
                columns_accessed=result.validation.get("columns_accessed", []),
                insights=result.analysis.get("insights", []),
                summary=result.analysis.get("summary", ""),
            )

            # Score
            score = scorer.score(
                comparison=comparison,
                execution_result=exec_result,
                sql=sql,
                dialect=self.dialect,
            )

            eval_result.scores = ScoreBreakdown(
                overall=score.overall,
                correctness=score.correctness,
                efficiency=score.efficiency,
                safety=score.safety,
                completeness=score.result_completeness,
                semantic_accuracy=score.semantic_accuracy_score,
                best_practices=score.best_practices_score,
                plan_quality=score.plan_quality_score,
                validation_score=score.validation_score,
                hallucination_score=score.hallucination_score,
                performance_score=score.performance_score,
            )

            # Add suggestions from best practices
            if score.best_practices_report:
                eval_result.suggestions = score.best_practices_report.get("suggestions", [])

        # Store result
        if eval_request.agent_id in self.results:
            self.results[eval_request.agent_id].append(eval_result)

        return eval_result

    def evaluate_batch(self, batch_request: BatchEvaluationRequest) -> EvaluationResponse:
        """Evaluate multiple SQL submissions."""
        results = []

        for submission in batch_request.submissions:
            eval_req = EvaluationRequest(
                agent_id=batch_request.agent_id,
                task_id=submission["task_id"],
                sql=submission["sql"],
                session_id=batch_request.session_id,
            )
            result = self.evaluate_submission(eval_req)
            results.append(result)

        # Calculate summary
        total = len(results)
        successful = sum(1 for r in results if r.status == "success")
        avg_score = 0.0
        if successful > 0:
            scores = [r.scores.overall for r in results if r.scores]
            avg_score = sum(scores) / len(scores) if scores else 0.0

        return EvaluationResponse(
            request_id=str(uuid.uuid4()),
            agent_id=batch_request.agent_id,
            results=results,
            summary={
                "total_submitted": total,
                "successful": successful,
                "failed": total - successful,
                "average_score": round(avg_score, 4),
            },
        )

    def get_leaderboard(self, limit: int = 10) -> List[LeaderboardEntry]:
        """Get the benchmark leaderboard."""
        entries = []

        for agent_id, agent in self.agents.items():
            results = self.results.get(agent_id, [])
            if not results:
                continue

            # Calculate stats
            successful = [r for r in results if r.scores]
            if not successful:
                continue

            avg_score = sum(r.scores.overall for r in successful) / len(successful)

            # Scores by dimension
            dim_scores = {
                "correctness": sum(r.scores.correctness for r in successful) / len(successful),
                "efficiency": sum(r.scores.efficiency for r in successful) / len(successful),
                "safety": sum(r.scores.safety for r in successful) / len(successful),
            }

            # Scores by difficulty (would need task lookup)
            diff_scores = {"easy": avg_score, "medium": avg_score, "hard": avg_score}

            entries.append(LeaderboardEntry(
                agent_id=agent_id,
                agent_name=agent.agent_name,
                total_tasks=len(results),
                completed_tasks=len(successful),
                average_score=round(avg_score, 4),
                scores_by_dimension=dim_scores,
                scores_by_difficulty=diff_scores,
                last_submission=results[-1].task_id if results else "",
            ))

        # Sort by average score
        entries.sort(key=lambda e: e.average_score, reverse=True)
        return entries[:limit]

    def get_agent_results(self, agent_id: str) -> List[EvaluationResult]:
        """Get all results for an agent."""
        return self.results.get(agent_id, [])


def create_app(
    tasks_path: Optional[str] = None,
    dialect: str = "sqlite",
) -> Flask:
    """
    Create the Flask application with A2A endpoints.

    Args:
        tasks_path: Path to gold queries JSON
        dialect: Default SQL dialect

    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    CORS(app)

    # Initialize server
    server = A2AServer(tasks_path=tasks_path, dialect=dialect)

    # Store server on app for access in routes
    app.a2a_server = server

    # =========================================================================
    # REQUEST LOGGING MIDDLEWARE
    # =========================================================================

    @app.before_request
    def log_request_start():
        """Log incoming request and set timing."""
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()

        # Log request (skip health checks to reduce noise)
        if request.path != "/health":
            logger.info(
                "Request started",
                request_id=g.request_id,
                method=request.method,
                path=request.path,
                remote_addr=request.remote_addr,
            )

    @app.after_request
    def log_request_complete(response):
        """Log request completion with timing."""
        if hasattr(g, "start_time") and request.path != "/health":
            duration_ms = (time.time() - g.start_time) * 1000
            logger.info(
                "Request completed",
                request_id=getattr(g, "request_id", "unknown"),
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
        return response

    # =========================================================================
    # API ENDPOINTS
    # =========================================================================

    @app.route("/", methods=["GET"])
    def root():
        """Root endpoint with API info."""
        return jsonify({
            "name": "AgentX SQL Benchmark A2A API",
            "version": "1.0.0",
            "endpoints": {
                "GET /info": "Get benchmark information",
                "POST /agents/register": "Register an agent",
                "POST /tasks": "Get available tasks",
                "POST /evaluate": "Evaluate a SQL submission",
                "POST /evaluate/batch": "Evaluate multiple submissions",
                "GET /leaderboard": "Get benchmark leaderboard",
                "GET /agents/<agent_id>/results": "Get agent results",
                "GET /health": "Health check",
            },
        })

    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

    @app.route("/info", methods=["GET"])
    def get_info():
        """Get benchmark information."""
        info = server.get_benchmark_info()
        return jsonify(info.to_dict())

    @app.route("/agents/register", methods=["POST"])
    def register_agent():
        """
        Register a new agent.

        Request body:
        {
            "agent_name": "MyAgent",
            "agent_version": "1.0.0",
            "capabilities": ["sql_generation", "schema_understanding"]
        }
        """
        data = request.get_json()
        if not data or "agent_name" not in data:
            return jsonify({"error": "agent_name is required"}), 400

        agent_info = AgentInfo(
            agent_id=data.get("agent_id", ""),
            agent_name=data["agent_name"],
            agent_version=data.get("agent_version", "1.0.0"),
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {}),
        )

        registered = server.register_agent(agent_info)
        return jsonify(registered.to_dict()), 201

    @app.route("/tasks", methods=["POST"])
    def get_tasks():
        """
        Get available evaluation tasks.

        Request body:
        {
            "agent_id": "...",
            "dialect": "sqlite",
            "difficulty": "medium",
            "tags": ["join"],
            "limit": 10
        }
        """
        data = request.get_json() or {}

        task_request = TaskRequest(
            agent_id=data.get("agent_id", "anonymous"),
            dialect=data.get("dialect"),
            difficulty=data.get("difficulty"),
            tags=data.get("tags"),
            limit=data.get("limit", 10),
        )

        response = server.get_tasks(task_request)
        return jsonify(response.to_dict())

    @app.route("/evaluate", methods=["POST"])
    def evaluate():
        """
        Evaluate a SQL submission.

        Request body:
        {
            "agent_id": "...",
            "task_id": "sqlite_simple_select",
            "sql": "SELECT * FROM customers LIMIT 10"
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        required = ["agent_id", "task_id", "sql"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing required fields: {missing}"}), 400

        eval_request = EvaluationRequest(
            agent_id=data["agent_id"],
            task_id=data["task_id"],
            sql=data["sql"],
            session_id=data.get("session_id"),
            execution_trace=data.get("execution_trace"),
            metadata=data.get("metadata", {}),
        )

        result = server.evaluate_submission(eval_request)
        return jsonify(result.to_dict())

    @app.route("/evaluate/batch", methods=["POST"])
    def evaluate_batch():
        """
        Evaluate multiple SQL submissions.

        Request body:
        {
            "agent_id": "...",
            "submissions": [
                {"task_id": "task1", "sql": "SELECT ..."},
                {"task_id": "task2", "sql": "SELECT ..."}
            ]
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        if "agent_id" not in data or "submissions" not in data:
            return jsonify({"error": "agent_id and submissions required"}), 400

        batch_request = BatchEvaluationRequest(
            agent_id=data["agent_id"],
            submissions=data["submissions"],
            session_id=data.get("session_id"),
        )

        response = server.evaluate_batch(batch_request)
        return jsonify(response.to_dict())

    @app.route("/leaderboard", methods=["GET"])
    def get_leaderboard():
        """Get the benchmark leaderboard."""
        limit = request.args.get("limit", 10, type=int)
        entries = server.get_leaderboard(limit=limit)
        return jsonify({
            "leaderboard": [e.to_dict() for e in entries],
            "updated_at": datetime.utcnow().isoformat(),
        })

    @app.route("/agents/<agent_id>/results", methods=["GET"])
    def get_agent_results(agent_id: str):
        """Get all results for a specific agent."""
        results = server.get_agent_results(agent_id)
        return jsonify({
            "agent_id": agent_id,
            "total_results": len(results),
            "results": [r.to_dict() for r in results],
        })

    @app.route("/schema", methods=["GET"])
    def get_schema():
        """Get the database schema."""
        executor = server._get_executor()
        return jsonify(executor.get_schema_info())

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    return app


def main():
    """Run the A2A server."""
    import argparse

    parser = argparse.ArgumentParser(description="AgentX A2A Protocol Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--dialect", default="sqlite", help="SQL dialect")
    parser.add_argument("--tasks", help="Path to tasks JSON file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    app = create_app(tasks_path=args.tasks, dialect=args.dialect)

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║              AgentX SQL Benchmark - A2A Server                   ║
╠══════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                       ║
║    GET  /info          - Benchmark information                   ║
║    POST /agents/register - Register your agent                   ║
║    POST /tasks         - Get evaluation tasks                    ║
║    POST /evaluate      - Submit SQL for evaluation               ║
║    POST /evaluate/batch - Batch evaluation                       ║
║    GET  /leaderboard   - View leaderboard                        ║
║    GET  /schema        - View database schema                    ║
╠══════════════════════════════════════════════════════════════════╣
║  Server: http://{args.host}:{args.port}                              ║
║  Dialect: {args.dialect}                                              ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
