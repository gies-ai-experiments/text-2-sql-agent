"""
SQLBenchmarkGreenAgent - AgentBeats Green Agent for SQL Benchmark Evaluation.

Orchestrates SQL benchmark assessments for Purple Agents (SQL-generating AI agents)
using the A2A protocol. Supports multi-agent tournaments with ranking.
"""

import os
import sys
import json
import uuid
import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from .config import (
    AssessmentConfig,
    TaskUpdate,
    ScoreSummary,
    TaskResult,
    ParticipantSummary,
    RankedParticipant,
    AssessmentArtifact,
)
from .artifact_builder import ArtifactBuilder


class SQLBenchmarkGreenAgent:
    """
    AgentBeats Green Agent for SQL Benchmark Evaluation.

    Receives assessment_request with Purple Agent endpoints,
    orchestrates SQL task distribution, evaluates responses,
    and produces scored artifacts with rankings.
    """

    def __init__(
        self,
        tasks_path: Optional[str] = None,
        dialect: str = "sqlite",
        scorer_preset: str = "default",
    ):
        """
        Initialize the Green Agent.

        Args:
            tasks_path: Path to gold queries JSON file
            dialect: SQL dialect (sqlite, duckdb, postgresql)
            scorer_preset: Scorer preset (default, strict, performance, quality)
        """
        self.dialect = dialect
        self.scorer_preset = scorer_preset
        self.tasks_path = tasks_path or self._default_tasks_path()

        # Lazy-loaded components
        self._executor = None
        self._scorer = None
        self._comparator = None
        self._all_tasks: List[Dict[str, Any]] = []

        # Load tasks on init
        self._load_tasks()

    def _default_tasks_path(self) -> str:
        """Get default tasks path."""
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        return os.path.join(base, "tasks", "gold_queries", "sqlite", "basic_queries.json")

    def _load_tasks(self):
        """Load evaluation tasks from JSON file."""
        if not os.path.exists(self.tasks_path):
            print(f"Warning: Tasks file not found: {self.tasks_path}")
            return

        with open(self.tasks_path, 'r') as f:
            self._all_tasks = json.load(f)

        print(f"Loaded {len(self._all_tasks)} tasks from {self.tasks_path}")

    def _get_executor(self):
        """Lazy-load the SQL executor."""
        if self._executor is None:
            from agentx import SQLExecutor, ExecutorConfig
            self._executor = SQLExecutor(ExecutorConfig(dialect=self.dialect))
            self._setup_sample_data()
        return self._executor

    def _get_scorer(self):
        """Lazy-load the enhanced scorer."""
        if self._scorer is None:
            from evaluation.enhanced_scorer import create_enhanced_scorer
            self._scorer = create_enhanced_scorer(self.scorer_preset)
        return self._scorer

    def _get_comparator(self):
        """Lazy-load the result comparator."""
        if self._comparator is None:
            from evaluation.result_comparator import DefaultResultComparator
            self._comparator = DefaultResultComparator(
                numeric_tolerance=1e-6,
                ignore_row_order=True,
                case_sensitive=False,
            )
        return self._comparator

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
                    f"INSERT OR IGNORE INTO customers (id, name, email, city, phone) "
                    f"VALUES ({c[0]}, '{c[1]}', '{c[2]}', '{c[3]}', {repr(c[4])})"
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
                    f"INSERT OR IGNORE INTO orders (id, customer_id, order_date, total, status) "
                    f"VALUES ({o[0]}, {o[1]}, '{o[2]}', {o[3]}, '{o[4]}')"
                )
            except Exception:
                pass

        executor.refresh_schema()
        print("Sample data setup complete")

    def _filter_tasks(self, config: AssessmentConfig) -> List[Dict[str, Any]]:
        """Filter tasks based on assessment configuration."""
        filtered = []

        for task in self._all_tasks:
            # Filter by difficulty
            task_difficulty = task.get("difficulty", "medium")
            if task_difficulty not in config.difficulty:
                continue

            # Filter by tags if specified
            if config.tags:
                task_tags = task.get("tags", [])
                if not any(tag in task_tags for tag in config.tags):
                    continue

            filtered.append(task)

            # Limit task count
            if len(filtered) >= config.task_count:
                break

        return filtered

    def _evaluate_sql(
        self,
        sql: str,
        task: Dict[str, Any],
    ) -> TaskResult:
        """
        Evaluate a SQL submission against a task.

        Args:
            sql: SQL query submitted by Purple Agent
            task: Task definition with expected results

        Returns:
            TaskResult with scores and details
        """
        executor = self._get_executor()
        scorer = self._get_scorer()
        comparator = self._get_comparator()

        # Process the query
        result = executor.process_query(sql, verbose=False)

        # Extract hallucination info
        hall_report = result.validation.get("hallucination_report", {})
        phantom_tables = hall_report.get("phantom_tables", []) if hall_report else []
        phantom_columns = hall_report.get("phantom_columns", []) if hall_report else []

        # Build base task result
        task_result = TaskResult(
            task_id=task["id"],
            question=task["question"],
            sql_submitted=sql,
            gold_sql=task.get("gold_sql"),
            scores=ScoreSummary(
                overall=0.0,
                correctness=0.0,
                efficiency=0.0,
                safety=0.0,
                completeness=0.0,
                semantic_accuracy=0.0,
                best_practices=0.0,
                plan_quality=0.0,
            ),
            execution_success=result.success,
            execution_time_ms=result.execution.get("execution_time_ms", 0),
            rows_returned=len(result.data) if result.data else 0,
            validation_errors=result.validation.get("errors", []),
            phantom_tables=phantom_tables,
            phantom_columns=phantom_columns,
        )

        if not result.success:
            task_result.error_message = result.error
            # Score failed execution
            task_result.scores = ScoreSummary(
                overall=0.0,
                correctness=0.0,
                efficiency=0.0,
                safety=0.36 if phantom_tables or phantom_columns else 0.5,
                completeness=0.0,
                semantic_accuracy=0.0,
                best_practices=0.0,
                plan_quality=0.0,
                hallucination_score=0.0 if phantom_tables else 0.5,
            )
            return task_result

        # Score successful execution
        from evaluation.data_structures import ComparisonResult, ExecutionResult as EvalExecutionResult

        # Compare with expected results if available
        expected_results = task.get("expected_results")
        if expected_results:
            comparison = comparator.compare(result.data, expected_results)
        else:
            # Self-comparison if no expected results
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
            expected_results=expected_results,
        )

        task_result.scores = ScoreSummary(
            overall=score.overall,
            correctness=score.correctness,
            efficiency=score.efficiency,
            safety=score.safety,
            completeness=score.result_completeness,
            semantic_accuracy=score.semantic_accuracy_score,
            best_practices=score.best_practices_score,
            plan_quality=score.plan_quality_score,
            hallucination_score=score.hallucination_score,
            validation_score=score.validation_score,
            performance_score=score.performance_score,
        )

        return task_result

    def get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information for Purple Agents."""
        executor = self._get_executor()
        return executor.get_schema_info()

    async def handle_assessment(
        self,
        participants: Dict[str, str],
        config: Dict[str, Any],
        send_task_func: Optional[Callable] = None,
    ) -> AsyncGenerator[TaskUpdate, None]:
        """
        Handle an assessment request (main entry point).

        Args:
            participants: Mapping of participant_id to endpoint URL
            config: Assessment configuration
            send_task_func: Async function to send tasks to Purple Agents
                           Signature: async def send_task(endpoint, task_payload) -> Dict

        Yields:
            TaskUpdate objects with progress and final artifact
        """
        assessment_id = str(uuid.uuid4())[:8]
        assessment_config = AssessmentConfig.from_dict(config)

        yield TaskUpdate(
            status="submitted",
            message=f"Assessment {assessment_id} started with {len(participants)} participants",
            progress=0.0,
            data={
                "assessment_id": assessment_id,
                "participants": list(participants.keys()),
                "config": config,
            }
        )

        # Filter tasks based on config
        tasks = self._filter_tasks(assessment_config)
        if not tasks:
            yield TaskUpdate(
                status="failed",
                message="No tasks match the specified criteria",
                progress=1.0,
            )
            return

        total_evaluations = len(tasks) * len(participants)
        evaluations_done = 0

        # Initialize results storage
        all_results: Dict[str, List[TaskResult]] = {
            pid: [] for pid in participants
        }

        yield TaskUpdate(
            status="working",
            message=f"Evaluating {len(tasks)} tasks across {len(participants)} participants",
            progress=0.05,
        )

        # Get schema info for task payloads
        schema_info = self.get_schema_info()

        # Process each task
        for task_idx, task in enumerate(tasks):
            task_payload = {
                "task_id": task["id"],
                "question": task["question"],
                "schema": schema_info,
                "dialect": self.dialect,
            }

            # Send to all participants
            if assessment_config.parallel_evaluation:
                # Parallel evaluation
                responses = {}
                if send_task_func:
                    # Real A2A communication
                    coros = {
                        pid: send_task_func(endpoint, task_payload)
                        for pid, endpoint in participants.items()
                    }
                    results = await asyncio.gather(
                        *[coro for coro in coros.values()],
                        return_exceptions=True
                    )
                    for pid, result in zip(coros.keys(), results):
                        if isinstance(result, Exception):
                            responses[pid] = {"sql": "", "error": str(result)}
                        else:
                            responses[pid] = result
                else:
                    # Mock responses for testing (use gold SQL)
                    for pid in participants:
                        responses[pid] = {"sql": task.get("gold_sql", "SELECT 1")}
            else:
                # Sequential evaluation
                responses = {}
                for pid, endpoint in participants.items():
                    if send_task_func:
                        try:
                            responses[pid] = await send_task_func(endpoint, task_payload)
                        except Exception as e:
                            responses[pid] = {"sql": "", "error": str(e)}
                    else:
                        responses[pid] = {"sql": task.get("gold_sql", "SELECT 1")}

            # Evaluate each response
            for pid, response in responses.items():
                sql = response.get("sql", "")
                if not sql:
                    # Handle error response
                    task_result = TaskResult(
                        task_id=task["id"],
                        question=task["question"],
                        sql_submitted="",
                        gold_sql=task.get("gold_sql"),
                        scores=ScoreSummary(
                            overall=0.0,
                            correctness=0.0,
                            efficiency=0.0,
                            safety=0.0,
                            completeness=0.0,
                            semantic_accuracy=0.0,
                            best_practices=0.0,
                            plan_quality=0.0,
                        ),
                        execution_success=False,
                        execution_time_ms=0,
                        rows_returned=0,
                        error_message=response.get("error", "No SQL returned"),
                    )
                else:
                    task_result = self._evaluate_sql(sql, task)

                all_results[pid].append(task_result)
                evaluations_done += 1

                yield TaskUpdate(
                    status="working",
                    progress=0.1 + (0.85 * evaluations_done / total_evaluations),
                    message=f"{pid}: {task['id']} scored {task_result.scores.overall:.2%}",
                    data={
                        "participant": pid,
                        "task_id": task["id"],
                        "score": task_result.scores.overall,
                        "execution_success": task_result.execution_success,
                    }
                )

        # Build final artifact
        yield TaskUpdate(
            status="working",
            progress=0.95,
            message="Building assessment artifact with rankings...",
        )

        artifact = ArtifactBuilder.build(
            assessment_id=assessment_id,
            config=assessment_config,
            participants=participants,
            results=all_results,
        )

        yield TaskUpdate(
            status="completed",
            progress=1.0,
            message=f"Assessment complete. Winner: {artifact.rankings[0].participant_id} "
                    f"({artifact.rankings[0].overall_score:.2%})",
            artifact=artifact,
        )

    def close(self):
        """Clean up resources."""
        if self._executor:
            self._executor.close()
            self._executor = None
