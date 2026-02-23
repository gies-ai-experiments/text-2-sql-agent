"""
A2A Protocol Client.

Example client for interacting with the AgentX SQL Benchmark.
Use this as a reference implementation for building agent integrations.

Usage:
    from a2a import A2AClient

    client = A2AClient("http://localhost:5000")

    # Register agent
    agent = client.register("MyAgent", "1.0.0")

    # Get tasks
    tasks = client.get_tasks(difficulty="easy")

    # Submit and evaluate
    result = client.evaluate(tasks[0].task_id, "SELECT * FROM customers")
"""

import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .models import (
    AgentInfo,
    BenchmarkInfo,
    TaskDefinition,
    TaskResponse,
    EvaluationResult,
    EvaluationResponse,
    LeaderboardEntry,
)


class A2AClientError(Exception):
    """Error from A2A client operations."""
    pass


class A2AClient:
    """
    Client for interacting with AgentX A2A Server.

    Provides a simple interface for:
    - Agent registration
    - Task discovery
    - SQL evaluation
    - Result retrieval
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5000",
        timeout: float = 30.0,
    ):
        """
        Initialize the A2A client.

        Args:
            base_url: URL of the A2A server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.agent_id: Optional[str] = None
        self.session_id: Optional[str] = None

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to the server."""
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=self.timeout)
            else:
                raise A2AClientError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            raise A2AClientError(f"Cannot connect to server at {self.base_url}")
        except requests.exceptions.Timeout:
            raise A2AClientError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            error_msg = e.response.json().get("error", str(e)) if e.response else str(e)
            raise A2AClientError(f"HTTP error: {error_msg}")

    def health_check(self) -> bool:
        """Check if the server is healthy."""
        try:
            result = self._request("GET", "/health")
            return result.get("status") == "healthy"
        except A2AClientError:
            return False

    def get_info(self) -> BenchmarkInfo:
        """Get benchmark information."""
        data = self._request("GET", "/info")
        return BenchmarkInfo(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            supported_dialects=data.get("supported_dialects", []),
            scoring_dimensions=data.get("scoring_dimensions", []),
            api_version=data.get("api_version", ""),
        )

    def register(
        self,
        agent_name: str,
        agent_version: str = "1.0.0",
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentInfo:
        """
        Register an agent with the benchmark server.

        Args:
            agent_name: Name of the agent
            agent_version: Version string
            capabilities: List of agent capabilities
            metadata: Additional metadata

        Returns:
            AgentInfo with assigned agent_id
        """
        data = {
            "agent_name": agent_name,
            "agent_version": agent_version,
            "capabilities": capabilities or [],
            "metadata": metadata or {},
        }

        result = self._request("POST", "/agents/register", data=data)

        agent = AgentInfo(
            agent_id=result["agent_id"],
            agent_name=result["agent_name"],
            agent_version=result.get("agent_version", "1.0.0"),
            capabilities=result.get("capabilities", []),
            metadata=result.get("metadata", {}),
            registered_at=result.get("registered_at", ""),
        )

        self.agent_id = agent.agent_id
        return agent

    def get_tasks(
        self,
        dialect: Optional[str] = None,
        difficulty: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[TaskDefinition]:
        """
        Get available evaluation tasks.

        Args:
            dialect: Filter by SQL dialect
            difficulty: Filter by difficulty (easy, medium, hard)
            tags: Filter by tags
            limit: Maximum number of tasks

        Returns:
            List of TaskDefinition objects
        """
        data = {
            "agent_id": self.agent_id or "anonymous",
            "limit": limit,
        }
        if dialect:
            data["dialect"] = dialect
        if difficulty:
            data["difficulty"] = difficulty
        if tags:
            data["tags"] = tags

        result = self._request("POST", "/tasks", data=data)

        self.session_id = result.get("session_id")

        tasks = []
        for t in result.get("tasks", []):
            tasks.append(TaskDefinition(
                task_id=t["task_id"],
                question=t["question"],
                dialect=t["dialect"],
                difficulty=t["difficulty"],
                schema_info=t.get("schema_info", {}),
                tags=t.get("tags", []),
                hints=t.get("hints", []),
            ))

        return tasks

    def get_schema(self) -> Dict[str, Any]:
        """Get the database schema."""
        return self._request("GET", "/schema")

    def evaluate(
        self,
        task_id: str,
        sql: str,
        execution_trace: Optional[List[Dict]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """
        Submit a SQL query for evaluation.

        Args:
            task_id: ID of the task being answered
            sql: Generated SQL query
            execution_trace: Optional reasoning trace
            metadata: Additional metadata

        Returns:
            EvaluationResult with scores and feedback
        """
        if not self.agent_id:
            raise A2AClientError("Agent not registered. Call register() first.")

        data = {
            "agent_id": self.agent_id,
            "task_id": task_id,
            "sql": sql,
            "session_id": self.session_id,
        }
        if execution_trace:
            data["execution_trace"] = execution_trace
        if metadata:
            data["metadata"] = metadata

        result = self._request("POST", "/evaluate", data=data)

        return self._parse_evaluation_result(result)

    def evaluate_batch(
        self,
        submissions: List[Dict[str, str]],
    ) -> EvaluationResponse:
        """
        Submit multiple SQL queries for evaluation.

        Args:
            submissions: List of {task_id, sql} dicts

        Returns:
            EvaluationResponse with all results
        """
        if not self.agent_id:
            raise A2AClientError("Agent not registered. Call register() first.")

        data = {
            "agent_id": self.agent_id,
            "submissions": submissions,
            "session_id": self.session_id,
        }

        result = self._request("POST", "/evaluate/batch", data=data)

        results = [
            self._parse_evaluation_result(r)
            for r in result.get("results", [])
        ]

        return EvaluationResponse(
            request_id=result.get("request_id", ""),
            agent_id=result.get("agent_id", ""),
            results=results,
            summary=result.get("summary", {}),
            evaluated_at=result.get("evaluated_at", ""),
        )

    def get_leaderboard(self, limit: int = 10) -> List[LeaderboardEntry]:
        """Get the benchmark leaderboard."""
        result = self._request("GET", "/leaderboard", params={"limit": limit})

        entries = []
        for e in result.get("leaderboard", []):
            entries.append(LeaderboardEntry(
                agent_id=e["agent_id"],
                agent_name=e["agent_name"],
                total_tasks=e["total_tasks"],
                completed_tasks=e["completed_tasks"],
                average_score=e["average_score"],
                scores_by_dimension=e.get("scores_by_dimension", {}),
                scores_by_difficulty=e.get("scores_by_difficulty", {}),
                last_submission=e.get("last_submission", ""),
            ))

        return entries

    def get_my_results(self) -> List[EvaluationResult]:
        """Get all results for the current agent."""
        if not self.agent_id:
            raise A2AClientError("Agent not registered. Call register() first.")

        result = self._request("GET", f"/agents/{self.agent_id}/results")

        return [
            self._parse_evaluation_result(r)
            for r in result.get("results", [])
        ]

    def _parse_evaluation_result(self, data: Dict) -> EvaluationResult:
        """Parse evaluation result from API response."""
        from .models import ScoreBreakdown

        scores = None
        if data.get("scores"):
            s = data["scores"]
            scores = ScoreBreakdown(
                overall=s.get("overall", 0),
                correctness=s.get("correctness", 0),
                efficiency=s.get("efficiency", 0),
                safety=s.get("safety", 0),
                completeness=s.get("completeness", 0),
                semantic_accuracy=s.get("semantic_accuracy", 0),
                best_practices=s.get("best_practices", 0),
                plan_quality=s.get("plan_quality", 0),
                validation_score=s.get("validation_score", 1.0),
                hallucination_score=s.get("hallucination_score", 1.0),
                performance_score=s.get("performance_score", 1.0),
            )

        return EvaluationResult(
            task_id=data.get("task_id", ""),
            status=data.get("status", "unknown"),
            scores=scores,
            execution_success=data.get("execution_success", False),
            rows_returned=data.get("rows_returned", 0),
            execution_time_ms=data.get("execution_time_ms", 0),
            is_valid=data.get("is_valid", False),
            validation_errors=data.get("validation_errors", []),
            validation_warnings=data.get("validation_warnings", []),
            phantom_tables=data.get("phantom_tables", []),
            phantom_columns=data.get("phantom_columns", []),
            matches_gold=data.get("matches_gold"),
            match_score=data.get("match_score", 0),
            insights=data.get("insights", []),
            suggestions=data.get("suggestions", []),
            error_message=data.get("error_message"),
        )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_usage():
    """
    Example of how an LLM agent would use this client.

    This demonstrates the typical workflow:
    1. Connect and register
    2. Get available tasks
    3. Generate SQL (agent's job)
    4. Submit for evaluation
    5. Process feedback
    """
    print("=" * 60)
    print("AgentX A2A Client Example")
    print("=" * 60)

    # Create client
    client = A2AClient("http://localhost:5000")

    # Check server health
    if not client.health_check():
        print("Server is not available!")
        return

    # Get benchmark info
    info = client.get_info()
    print(f"\nBenchmark: {info.name} v{info.version}")
    print(f"Supported dialects: {info.supported_dialects}")
    print(f"Scoring dimensions: {info.scoring_dimensions}")

    # Register agent
    agent = client.register(
        agent_name="ExampleAgent",
        agent_version="1.0.0",
        capabilities=["sql_generation", "schema_understanding"],
    )
    print(f"\nRegistered as: {agent.agent_name} ({agent.agent_id})")

    # Get schema
    schema = client.get_schema()
    print(f"\nAvailable tables: {list(schema.get('tables', {}).keys())}")

    # Get tasks
    tasks = client.get_tasks(difficulty="easy", limit=3)
    print(f"\nGot {len(tasks)} tasks:")
    for t in tasks:
        print(f"  - {t.task_id}: {t.question}")

    # Evaluate a submission
    if tasks:
        task = tasks[0]
        sql = "SELECT * FROM customers LIMIT 10"  # Agent would generate this

        print(f"\nEvaluating SQL for task: {task.task_id}")
        print(f"SQL: {sql}")

        result = client.evaluate(task.task_id, sql)

        print(f"\nResult:")
        print(f"  Status: {result.status}")
        if result.scores:
            print(f"  Overall Score: {result.scores.overall:.2%}")
            print(f"  Correctness: {result.scores.correctness:.2%}")
            print(f"  Efficiency: {result.scores.efficiency:.2%}")
            print(f"  Safety: {result.scores.safety:.2%}")

        if result.suggestions:
            print(f"  Suggestions:")
            for s in result.suggestions:
                print(f"    - {s}")

    # Check leaderboard
    leaderboard = client.get_leaderboard(limit=5)
    if leaderboard:
        print(f"\nLeaderboard:")
        for i, entry in enumerate(leaderboard, 1):
            print(f"  {i}. {entry.agent_name}: {entry.average_score:.2%}")

    print("\n" + "=" * 60)
    print("Example complete!")


if __name__ == "__main__":
    example_usage()
