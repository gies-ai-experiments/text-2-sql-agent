#!/usr/bin/env python3
"""
Test script for A2A Protocol interface.

Tests:
1. Server initialization
2. Agent registration
3. Task retrieval
4. SQL evaluation
5. Batch evaluation
6. Leaderboard

Run with: python test_a2a.py
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# Add paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from a2a.models import (
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
)
from a2a.server import A2AServer, create_app


class TestA2AModels(unittest.TestCase):
    """Test A2A data models."""

    def test_agent_info(self):
        """Test AgentInfo model."""
        agent = AgentInfo(
            agent_id="test-123",
            agent_name="TestAgent",
            agent_version="1.0.0",
            capabilities=["sql_generation"],
        )

        self.assertEqual(agent.agent_id, "test-123")
        self.assertEqual(agent.agent_name, "TestAgent")
        self.assertIn("sql_generation", agent.capabilities)

        # Test serialization
        data = agent.to_dict()
        self.assertIn("agent_id", data)
        self.assertIn("registered_at", data)

    def test_benchmark_info(self):
        """Test BenchmarkInfo model."""
        info = BenchmarkInfo()

        self.assertEqual(info.name, "AgentX SQL Benchmark")
        self.assertIn("sqlite", info.supported_dialects)
        self.assertIn("correctness", info.scoring_dimensions)

    def test_task_definition(self):
        """Test TaskDefinition model."""
        task = TaskDefinition(
            task_id="test_task",
            question="Get all users",
            dialect="sqlite",
            difficulty="easy",
            schema_info={"tables": ["users"]},
            tags=["select", "basic"],
        )

        self.assertEqual(task.task_id, "test_task")
        self.assertEqual(task.dialect, "sqlite")
        self.assertIn("select", task.tags)

    def test_evaluation_request(self):
        """Test EvaluationRequest model."""
        req = EvaluationRequest(
            agent_id="agent-123",
            task_id="task-456",
            sql="SELECT * FROM users",
        )

        self.assertEqual(req.agent_id, "agent-123")
        self.assertEqual(req.task_id, "task-456")
        self.assertIsNotNone(req.submitted_at)

    def test_score_breakdown(self):
        """Test ScoreBreakdown model."""
        scores = ScoreBreakdown(
            overall=0.85,
            correctness=0.9,
            efficiency=0.8,
            safety=0.95,
            completeness=0.8,
            semantic_accuracy=0.85,
            best_practices=0.7,
            plan_quality=0.9,
        )

        self.assertEqual(scores.overall, 0.85)
        data = scores.to_dict()
        self.assertIn("correctness", data)


class TestA2AServer(unittest.TestCase):
    """Test A2A server functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        # Create server with test tasks
        cls.server = A2AServer(dialect="sqlite")

    def test_benchmark_info(self):
        """Test getting benchmark info."""
        info = self.server.get_benchmark_info()

        self.assertIsInstance(info, BenchmarkInfo)
        self.assertEqual(info.name, "AgentX SQL Benchmark")

    def test_register_agent(self):
        """Test agent registration."""
        agent_info = AgentInfo(
            agent_id="",
            agent_name="TestBot",
            agent_version="2.0.0",
            capabilities=["test"],
        )

        registered = self.server.register_agent(agent_info)

        self.assertIsNotNone(registered.agent_id)
        self.assertEqual(registered.agent_name, "TestBot")
        self.assertIn(registered.agent_id, self.server.agents)

    def test_get_tasks(self):
        """Test retrieving tasks."""
        request = TaskRequest(
            agent_id="test-agent",
            limit=5,
        )

        response = self.server.get_tasks(request)

        self.assertIsInstance(response, TaskResponse)
        self.assertGreaterEqual(len(response.tasks), 0)
        self.assertIsNotNone(response.session_id)

    def test_get_tasks_with_filter(self):
        """Test task filtering."""
        request = TaskRequest(
            agent_id="test-agent",
            difficulty="easy",
            limit=10,
        )

        response = self.server.get_tasks(request)

        for task in response.tasks:
            self.assertEqual(task.difficulty, "easy")

    def test_evaluate_valid_query(self):
        """Test evaluating a valid SQL query."""
        # Register agent first
        agent = self.server.register_agent(AgentInfo(
            agent_id="",
            agent_name="EvalTest",
        ))

        # Get a task
        tasks = self.server.get_tasks(TaskRequest(agent_id=agent.agent_id, limit=1))
        if not tasks.tasks:
            self.skipTest("No tasks available")

        task = tasks.tasks[0]

        # Submit evaluation
        eval_req = EvaluationRequest(
            agent_id=agent.agent_id,
            task_id=task.task_id,
            sql="SELECT * FROM customers LIMIT 5",
        )

        result = self.server.evaluate_submission(eval_req)

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.task_id, task.task_id)

        if result.status == "success":
            self.assertIsNotNone(result.scores)
            self.assertGreaterEqual(result.scores.overall, 0)
            self.assertLessEqual(result.scores.overall, 1)

    def test_evaluate_invalid_query(self):
        """Test evaluating an invalid SQL query (phantom table)."""
        agent = self.server.register_agent(AgentInfo(
            agent_id="",
            agent_name="InvalidTest",
        ))

        eval_req = EvaluationRequest(
            agent_id=agent.agent_id,
            task_id="sqlite_simple_select",
            sql="SELECT * FROM nonexistent_table",
        )

        result = self.server.evaluate_submission(eval_req)

        self.assertEqual(result.status, "failed")
        self.assertFalse(result.is_valid)

    def test_batch_evaluation(self):
        """Test batch evaluation."""
        agent = self.server.register_agent(AgentInfo(
            agent_id="",
            agent_name="BatchTest",
        ))

        batch_req = BatchEvaluationRequest(
            agent_id=agent.agent_id,
            submissions=[
                {"task_id": "sqlite_simple_select", "sql": "SELECT * FROM customers LIMIT 10"},
                {"task_id": "sqlite_count", "sql": "SELECT COUNT(*) FROM customers"},
            ],
        )

        response = self.server.evaluate_batch(batch_req)

        self.assertIsInstance(response, EvaluationResponse)
        self.assertEqual(len(response.results), 2)
        self.assertIn("total_submitted", response.summary)

    def test_leaderboard(self):
        """Test leaderboard generation."""
        # Make some submissions first
        agent = self.server.register_agent(AgentInfo(
            agent_id="",
            agent_name="LeaderboardTest",
        ))

        eval_req = EvaluationRequest(
            agent_id=agent.agent_id,
            task_id="sqlite_simple_select",
            sql="SELECT * FROM customers LIMIT 10",
        )
        self.server.evaluate_submission(eval_req)

        # Get leaderboard
        leaderboard = self.server.get_leaderboard(limit=5)

        self.assertIsInstance(leaderboard, list)
        # Should have at least one entry from our submission
        if leaderboard:
            entry = leaderboard[0]
            self.assertIsNotNone(entry.agent_name)
            self.assertGreaterEqual(entry.average_score, 0)


class TestA2AFlaskApp(unittest.TestCase):
    """Test Flask API endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up Flask test client."""
        cls.app = create_app(dialect="sqlite")
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("endpoints", data)

    def test_health_endpoint(self):
        """Test health check."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["status"], "healthy")

    def test_info_endpoint(self):
        """Test benchmark info endpoint."""
        response = self.client.get("/info")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("name", data)
        self.assertIn("supported_dialects", data)

    def test_register_agent_endpoint(self):
        """Test agent registration endpoint."""
        response = self.client.post("/agents/register", json={
            "agent_name": "FlaskTestAgent",
            "agent_version": "1.0.0",
            "capabilities": ["sql_generation"],
        })
        self.assertEqual(response.status_code, 201)

        data = response.get_json()
        self.assertIn("agent_id", data)
        self.assertEqual(data["agent_name"], "FlaskTestAgent")

    def test_register_agent_missing_name(self):
        """Test registration with missing name."""
        response = self.client.post("/agents/register", json={
            "agent_version": "1.0.0",
        })
        self.assertEqual(response.status_code, 400)

    def test_tasks_endpoint(self):
        """Test tasks endpoint."""
        response = self.client.post("/tasks", json={
            "agent_id": "test-agent",
            "limit": 5,
        })
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("tasks", data)
        self.assertIn("session_id", data)

    def test_evaluate_endpoint(self):
        """Test evaluate endpoint."""
        # Register first
        reg_response = self.client.post("/agents/register", json={
            "agent_name": "EvalEndpointTest",
        })
        agent_id = reg_response.get_json()["agent_id"]

        # Evaluate
        response = self.client.post("/evaluate", json={
            "agent_id": agent_id,
            "task_id": "sqlite_simple_select",
            "sql": "SELECT * FROM customers LIMIT 10",
        })
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("status", data)
        self.assertIn("task_id", data)

    def test_evaluate_missing_fields(self):
        """Test evaluate with missing fields."""
        response = self.client.post("/evaluate", json={
            "agent_id": "test",
        })
        self.assertEqual(response.status_code, 400)

    def test_batch_evaluate_endpoint(self):
        """Test batch evaluate endpoint."""
        # Register first
        reg_response = self.client.post("/agents/register", json={
            "agent_name": "BatchEndpointTest",
        })
        agent_id = reg_response.get_json()["agent_id"]

        # Batch evaluate
        response = self.client.post("/evaluate/batch", json={
            "agent_id": agent_id,
            "submissions": [
                {"task_id": "sqlite_simple_select", "sql": "SELECT * FROM customers"},
                {"task_id": "sqlite_count", "sql": "SELECT COUNT(*) FROM customers"},
            ],
        })
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("results", data)
        self.assertIn("summary", data)

    def test_leaderboard_endpoint(self):
        """Test leaderboard endpoint."""
        response = self.client.get("/leaderboard?limit=5")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("leaderboard", data)

    def test_schema_endpoint(self):
        """Test schema endpoint."""
        response = self.client.get("/schema")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("tables", data)


class TestA2AIntegration(unittest.TestCase):
    """Integration tests for full workflow."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.app = create_app(dialect="sqlite")
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def test_full_evaluation_workflow(self):
        """Test complete evaluation workflow."""
        # 1. Get benchmark info
        info_resp = self.client.get("/info")
        self.assertEqual(info_resp.status_code, 200)

        # 2. Register agent
        reg_resp = self.client.post("/agents/register", json={
            "agent_name": "IntegrationTestAgent",
            "capabilities": ["sql_generation", "schema_understanding"],
        })
        self.assertEqual(reg_resp.status_code, 201)
        agent_id = reg_resp.get_json()["agent_id"]

        # 3. Get schema
        schema_resp = self.client.get("/schema")
        self.assertEqual(schema_resp.status_code, 200)
        schema = schema_resp.get_json()
        print(f"Available tables: {list(schema.get('tables', {}).keys())}")

        # 4. Get tasks
        tasks_resp = self.client.post("/tasks", json={
            "agent_id": agent_id,
            "difficulty": "easy",
            "limit": 3,
        })
        self.assertEqual(tasks_resp.status_code, 200)
        tasks = tasks_resp.get_json()["tasks"]
        print(f"Got {len(tasks)} tasks")

        # 5. Evaluate each task
        for task in tasks:
            # Generate appropriate SQL based on task
            sql = self._generate_sql_for_task(task)

            eval_resp = self.client.post("/evaluate", json={
                "agent_id": agent_id,
                "task_id": task["task_id"],
                "sql": sql,
            })
            self.assertEqual(eval_resp.status_code, 200)

            result = eval_resp.get_json()
            print(f"Task {task['task_id']}: {result['status']}")
            if result.get("scores"):
                print(f"  Score: {result['scores']['overall']:.2%}")

        # 6. Check leaderboard
        lb_resp = self.client.get("/leaderboard")
        self.assertEqual(lb_resp.status_code, 200)

        # 7. Get agent results
        results_resp = self.client.get(f"/agents/{agent_id}/results")
        self.assertEqual(results_resp.status_code, 200)
        results = results_resp.get_json()
        print(f"Total submissions: {results['total_results']}")

    def _generate_sql_for_task(self, task: dict) -> str:
        """Generate SQL for a task (simplified)."""
        task_id = task["task_id"]

        # Simple task-based SQL generation
        sql_map = {
            "sqlite_simple_select": "SELECT * FROM customers LIMIT 10",
            "sqlite_count": "SELECT COUNT(*) as total FROM customers",
            "sqlite_where_filter": "SELECT * FROM customers WHERE city = 'New York'",
            "sqlite_join": "SELECT c.name, o.order_date, o.total FROM customers c JOIN orders o ON c.id = o.customer_id",
            "sqlite_group_by": "SELECT city, COUNT(*) as customer_count FROM customers GROUP BY city ORDER BY customer_count DESC",
        }

        return sql_map.get(task_id, "SELECT 1")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("A2A PROTOCOL INTERFACE TESTS")
    print("=" * 60 + "\n")

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestA2AModels))
    suite.addTests(loader.loadTestsFromTestCase(TestA2AServer))
    suite.addTests(loader.loadTestsFromTestCase(TestA2AFlaskApp))
    suite.addTests(loader.loadTestsFromTestCase(TestA2AIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("ALL A2A TESTS PASSED!")
    else:
        print(f"TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60 + "\n")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
