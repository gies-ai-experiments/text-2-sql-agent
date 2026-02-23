#!/usr/bin/env python3
"""
AgentX Benchmark Runner

Run comprehensive benchmarks against an LLM SQL agent and generate detailed reports.

Usage:
    # Run against local A2A server
    python run_benchmark.py --output results/

    # Run against external agent
    python run_benchmark.py --agent-url http://localhost:8000 --output results/

    # Filter by difficulty
    python run_benchmark.py --difficulty easy,medium --output results/

    # Export specific formats
    python run_benchmark.py --format json,csv,html --output results/
"""

import argparse
import json
import csv
import os
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

# Add paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run."""
    agent_url: Optional[str] = None
    tasks_path: Optional[str] = None
    output_dir: str = "results"
    difficulties: List[str] = field(default_factory=lambda: ["easy", "medium", "hard", "enterprise"])
    tags: Optional[List[str]] = None
    formats: List[str] = field(default_factory=lambda: ["json", "csv", "summary"])
    dialect: str = "sqlite"
    timeout: float = 30.0
    verbose: bool = False
    schema: str = "basic"  # "basic" or "enterprise"


@dataclass
class TaskResult:
    """Result for a single task."""
    task_id: str
    question: str
    difficulty: str
    tags: List[str]
    gold_sql: str
    agent_sql: Optional[str] = None
    status: str = "pending"  # pending, success, failed, error, skipped

    # Scores
    overall_score: float = 0.0
    correctness: float = 0.0
    efficiency: float = 0.0
    safety: float = 0.0
    completeness: float = 0.0
    semantic_accuracy: float = 0.0
    best_practices: float = 0.0
    plan_quality: float = 0.0

    # Execution details
    execution_time_ms: float = 0.0
    rows_returned: int = 0

    # Validation
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    phantom_tables: List[str] = field(default_factory=list)
    phantom_columns: List[str] = field(default_factory=list)

    # Comparison with expected
    matches_expected: Optional[bool] = None
    match_score: float = 0.0

    error_message: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    benchmark_id: str
    started_at: str
    completed_at: str
    duration_seconds: float

    config: Dict[str, Any]

    # Summary stats
    total_tasks: int = 0
    successful: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0

    # Aggregate scores
    average_score: float = 0.0
    median_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0

    # Scores by dimension
    scores_by_dimension: Dict[str, float] = field(default_factory=dict)

    # Scores by difficulty
    scores_by_difficulty: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Scores by tag
    scores_by_tag: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Individual results
    results: List[TaskResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["results"] = [r.to_dict() for r in self.results]
        return data


class BenchmarkRunner:
    """
    Runs benchmarks against SQL agents.

    Can run against:
    1. External agent via A2A API
    2. Local evaluation using gold SQL
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.tasks: List[Dict] = []
        self.results: List[TaskResult] = []

        # Load tasks
        self._load_tasks()

    def _load_tasks(self):
        """Load benchmark tasks from JSON."""
        tasks_path = self.config.tasks_path
        if not tasks_path:
            if self.config.schema == "enterprise":
                tasks_path = os.path.join(
                    os.path.dirname(__file__),
                    "tasks", "gold_queries", "sqlite", "enterprise_queries.json"
                )
            else:
                tasks_path = os.path.join(
                    os.path.dirname(__file__),
                    "tasks", "gold_queries", "sqlite", "basic_queries.json"
                )

        with open(tasks_path, 'r') as f:
            all_tasks = json.load(f)

        # Filter by difficulty
        self.tasks = [
            t for t in all_tasks
            if t.get("difficulty", "medium") in self.config.difficulties
        ]

        # Filter by tags if specified
        if self.config.tags:
            self.tasks = [
                t for t in self.tasks
                if any(tag in t.get("tags", []) for tag in self.config.tags)
            ]

        if self.config.verbose:
            print(f"Loaded {len(self.tasks)} tasks from {tasks_path}")

    def run(self, sql_generator: Optional[Callable[[Dict], str]] = None) -> BenchmarkReport:
        """
        Run the benchmark.

        Args:
            sql_generator: Optional function that takes a task dict and returns SQL.
                          If not provided, uses gold_sql for evaluation.

        Returns:
            BenchmarkReport with all results
        """
        import uuid

        benchmark_id = str(uuid.uuid4())[:8]
        started_at = datetime.now(timezone.utc)

        print(f"\n{'='*60}")
        print(f"AGENTX BENCHMARK RUN: {benchmark_id}")
        print(f"{'='*60}")
        print(f"Schema: {self.config.schema.upper()}")
        print(f"Tasks: {len(self.tasks)}")
        print(f"Difficulties: {self.config.difficulties}")
        print(f"Dialect: {self.config.dialect}")
        print(f"{'='*60}\n")

        # Initialize executor and scorer
        from agentx import SQLExecutor, ExecutorConfig
        from evaluation.enhanced_scorer import EnhancedScorer
        from evaluation.result_comparator import DefaultResultComparator
        from evaluation.data_structures import ComparisonResult, ExecutionResult

        executor = SQLExecutor(ExecutorConfig(dialect=self.config.dialect))
        scorer = EnhancedScorer()
        comparator = DefaultResultComparator()

        # Setup sample data
        self._setup_sample_data(executor)

        self.results = []

        for i, task in enumerate(self.tasks, 1):
            task_id = task["id"]
            difficulty = task.get("difficulty", "medium")

            print(f"[{i}/{len(self.tasks)}] {task_id} ({difficulty})...", end=" ", flush=True)

            result = TaskResult(
                task_id=task_id,
                question=task["question"],
                difficulty=difficulty,
                tags=task.get("tags", []),
                gold_sql=task["gold_sql"],
            )

            try:
                # Get SQL to evaluate
                if sql_generator:
                    sql = sql_generator(task)
                    result.agent_sql = sql
                else:
                    sql = task["gold_sql"]
                    result.agent_sql = sql

                # Execute and evaluate
                exec_result = executor.process_query(sql, verbose=False)

                result.is_valid = exec_result.is_valid
                result.validation_errors = exec_result.validation.get("errors", [])

                hall_report = exec_result.validation.get("hallucination_report", {})
                if hall_report:
                    result.phantom_tables = hall_report.get("phantom_tables", [])
                    result.phantom_columns = hall_report.get("phantom_columns", [])

                if exec_result.success:
                    result.status = "success"
                    result.rows_returned = len(exec_result.data) if exec_result.data else 0
                    result.execution_time_ms = exec_result.execution.get("execution_time_ms", 0)

                    # Compare with expected results if available
                    expected = task.get("expected_results")
                    if expected:
                        comparison = comparator.compare(exec_result.data, expected)
                        result.matches_expected = comparison.is_match
                        result.match_score = comparison.match_score
                    else:
                        comparison = ComparisonResult(
                            is_match=True, match_score=1.0,
                            row_count_match=True, column_count_match=True
                        )

                    # Create execution result for scorer
                    eval_exec_result = ExecutionResult(
                        success=True,
                        data=exec_result.data,
                        rows_returned=result.rows_returned,
                        execution_time_ms=result.execution_time_ms,
                        is_valid=result.is_valid,
                        validation_errors=result.validation_errors,
                        query_type=exec_result.validation.get("query_type", "SELECT"),
                        tables_accessed=exec_result.validation.get("tables_accessed", []),
                        columns_accessed=exec_result.validation.get("columns_accessed", []),
                    )

                    # Score
                    score = scorer.score(
                        comparison=comparison,
                        execution_result=eval_exec_result,
                        sql=sql,
                        dialect=self.config.dialect,
                        expected_results=expected,
                    )

                    result.overall_score = score.overall
                    result.correctness = score.correctness
                    result.efficiency = score.efficiency
                    result.safety = score.safety
                    result.completeness = score.result_completeness
                    result.semantic_accuracy = score.semantic_accuracy_score
                    result.best_practices = score.best_practices_score
                    result.plan_quality = score.plan_quality_score

                    if score.best_practices_report:
                        result.suggestions = score.best_practices_report.get("suggestions", [])

                    print(f"✓ {result.overall_score:.1%}")
                else:
                    result.status = "failed"
                    result.error_message = exec_result.error
                    print(f"✗ FAILED")

            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                print(f"✗ ERROR: {e}")

            self.results.append(result)

        executor.close()

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        # Build report
        report = self._build_report(
            benchmark_id=benchmark_id,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_seconds=duration,
        )

        return report

    def _setup_sample_data(self, executor):
        """Setup sample data for evaluation."""
        if self.config.schema == "enterprise":
            self._setup_enterprise_data(executor)
        else:
            self._setup_basic_data(executor)

    def _setup_basic_data(self, executor):
        """Setup basic sample data for evaluation."""
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
            except:
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
            except:
                pass

        executor.refresh_schema()

    def _setup_enterprise_data(self, executor):
        """Setup enterprise schema with star schema and comprehensive data."""
        from tasks.enterprise_schema import setup_enterprise_schema
        setup_enterprise_schema(executor)

    def _build_report(
        self,
        benchmark_id: str,
        started_at: str,
        completed_at: str,
        duration_seconds: float,
    ) -> BenchmarkReport:
        """Build comprehensive benchmark report."""

        successful = [r for r in self.results if r.status == "success"]
        failed = [r for r in self.results if r.status == "failed"]
        errors = [r for r in self.results if r.status == "error"]
        skipped = [r for r in self.results if r.status == "skipped"]

        # Calculate aggregate scores
        scores = [r.overall_score for r in successful]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        sorted_scores = sorted(scores)
        median_score = sorted_scores[len(sorted_scores) // 2] if sorted_scores else 0.0
        min_score = min(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0

        # Scores by dimension
        dimensions = ["correctness", "efficiency", "safety", "completeness",
                      "semantic_accuracy", "best_practices", "plan_quality"]
        scores_by_dimension = {}
        for dim in dimensions:
            dim_scores = [getattr(r, dim) for r in successful]
            scores_by_dimension[dim] = sum(dim_scores) / len(dim_scores) if dim_scores else 0.0

        # Scores by difficulty
        scores_by_difficulty = {}
        for diff in ["easy", "medium", "hard", "enterprise"]:
            diff_results = [r for r in successful if r.difficulty == diff]
            if diff_results:
                diff_scores = [r.overall_score for r in diff_results]
                scores_by_difficulty[diff] = {
                    "count": len(diff_results),
                    "average": sum(diff_scores) / len(diff_scores),
                    "min": min(diff_scores),
                    "max": max(diff_scores),
                }

        # Scores by tag
        scores_by_tag = {}
        all_tags = set()
        for r in self.results:
            all_tags.update(r.tags)

        for tag in all_tags:
            tag_results = [r for r in successful if tag in r.tags]
            if tag_results:
                tag_scores = [r.overall_score for r in tag_results]
                scores_by_tag[tag] = {
                    "count": len(tag_results),
                    "average": sum(tag_scores) / len(tag_scores),
                }

        return BenchmarkReport(
            benchmark_id=benchmark_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            config=asdict(self.config),
            total_tasks=len(self.results),
            successful=len(successful),
            failed=len(failed),
            errors=len(errors),
            skipped=len(skipped),
            average_score=avg_score,
            median_score=median_score,
            min_score=min_score,
            max_score=max_score,
            scores_by_dimension=scores_by_dimension,
            scores_by_difficulty=scores_by_difficulty,
            scores_by_tag=scores_by_tag,
            results=self.results,
        )


class MetricsExporter:
    """Export benchmark results in various formats."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, report: BenchmarkReport, formats: List[str]) -> Dict[str, str]:
        """
        Export report in specified formats.

        Returns dict mapping format to output file path.
        """
        outputs = {}

        for fmt in formats:
            if fmt == "json":
                outputs["json"] = self.export_json(report)
            elif fmt == "csv":
                outputs["csv"] = self.export_csv(report)
            elif fmt == "summary":
                outputs["summary"] = self.export_summary(report)
            elif fmt == "html":
                outputs["html"] = self.export_html(report)

        return outputs

    def export_json(self, report: BenchmarkReport) -> str:
        """Export full report as JSON."""
        path = self.output_dir / f"benchmark_{report.benchmark_id}.json"

        with open(path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2, default=str)

        return str(path)

    def export_csv(self, report: BenchmarkReport) -> str:
        """Export results as CSV."""
        path = self.output_dir / f"benchmark_{report.benchmark_id}.csv"

        fieldnames = [
            "task_id", "difficulty", "status", "overall_score",
            "correctness", "efficiency", "safety", "completeness",
            "semantic_accuracy", "best_practices", "plan_quality",
            "execution_time_ms", "rows_returned", "is_valid",
            "matches_expected", "error_message"
        ]

        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in report.results:
                row = {k: getattr(result, k) for k in fieldnames}
                writer.writerow(row)

        return str(path)

    def export_summary(self, report: BenchmarkReport) -> str:
        """Export human-readable summary."""
        path = self.output_dir / f"benchmark_{report.benchmark_id}_summary.txt"

        lines = [
            "=" * 60,
            "AGENTX BENCHMARK REPORT",
            "=" * 60,
            "",
            f"Benchmark ID: {report.benchmark_id}",
            f"Started: {report.started_at}",
            f"Duration: {report.duration_seconds:.2f} seconds",
            "",
            "RESULTS SUMMARY",
            "-" * 40,
            f"Total Tasks:  {report.total_tasks}",
            f"Successful:   {report.successful}",
            f"Failed:       {report.failed}",
            f"Errors:       {report.errors}",
            "",
            "SCORES",
            "-" * 40,
            f"Average:  {report.average_score:.2%}",
            f"Median:   {report.median_score:.2%}",
            f"Min:      {report.min_score:.2%}",
            f"Max:      {report.max_score:.2%}",
            "",
            "SCORES BY DIMENSION",
            "-" * 40,
        ]

        for dim, score in report.scores_by_dimension.items():
            lines.append(f"  {dim:20s}: {score:.2%}")

        lines.extend([
            "",
            "SCORES BY DIFFICULTY",
            "-" * 40,
        ])

        for diff, stats in report.scores_by_difficulty.items():
            lines.append(f"  {diff:12s}: {stats['average']:.2%} (n={stats['count']})")

        if report.scores_by_tag:
            lines.extend([
                "",
                "TOP TAGS BY SCORE",
                "-" * 40,
            ])

            sorted_tags = sorted(
                report.scores_by_tag.items(),
                key=lambda x: x[1]["average"],
                reverse=True
            )[:10]

            for tag, stats in sorted_tags:
                lines.append(f"  {tag:20s}: {stats['average']:.2%} (n={stats['count']})")

        # Failed tasks
        failed = [r for r in report.results if r.status != "success"]
        if failed:
            lines.extend([
                "",
                "FAILED/ERROR TASKS",
                "-" * 40,
            ])
            for r in failed[:10]:
                lines.append(f"  {r.task_id}: {r.status} - {r.error_message or 'validation failed'}")

        lines.extend([
            "",
            "=" * 60,
        ])

        content = "\n".join(lines)

        with open(path, 'w') as f:
            f.write(content)

        # Also print to console
        print("\n" + content)

        return str(path)

    def export_html(self, report: BenchmarkReport) -> str:
        """Export as HTML report."""
        path = self.output_dir / f"benchmark_{report.benchmark_id}.html"

        # Generate score color
        def score_color(score: float) -> str:
            if score >= 0.9:
                return "#28a745"  # green
            elif score >= 0.7:
                return "#ffc107"  # yellow
            else:
                return "#dc3545"  # red

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>AgentX Benchmark Report - {report.benchmark_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .score-bar {{ height: 20px; background: #e9ecef; border-radius: 4px; overflow: hidden; }}
        .score-fill {{ height: 100%; transition: width 0.3s; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        .status-success {{ color: #28a745; }}
        .status-failed {{ color: #dc3545; }}
        .status-error {{ color: #ffc107; }}
        .tag {{ display: inline-block; background: #e9ecef; padding: 2px 8px; border-radius: 4px; margin: 2px; font-size: 0.85em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AgentX Benchmark Report</h1>
        <p>Benchmark ID: <strong>{report.benchmark_id}</strong> | Duration: {report.duration_seconds:.2f}s | {report.started_at}</p>

        <div class="summary">
            <div class="stat-card">
                <div class="stat-value">{report.total_tasks}</div>
                <div class="stat-label">Total Tasks</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #28a745">{report.successful}</div>
                <div class="stat-label">Successful</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #dc3545">{report.failed + report.errors}</div>
                <div class="stat-label">Failed/Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: {score_color(report.average_score)}">{report.average_score:.1%}</div>
                <div class="stat-label">Average Score</div>
            </div>
        </div>

        <h2>Scores by Dimension</h2>
        <table>
            <tr><th>Dimension</th><th>Score</th><th></th></tr>
"""

        for dim, score in report.scores_by_dimension.items():
            html += f"""
            <tr>
                <td>{dim.replace('_', ' ').title()}</td>
                <td>{score:.1%}</td>
                <td><div class="score-bar"><div class="score-fill" style="width: {score*100}%; background: {score_color(score)}"></div></div></td>
            </tr>
"""

        html += """
        </table>

        <h2>Scores by Difficulty</h2>
        <table>
            <tr><th>Difficulty</th><th>Count</th><th>Average</th><th>Min</th><th>Max</th></tr>
"""

        for diff, stats in report.scores_by_difficulty.items():
            html += f"""
            <tr>
                <td>{diff.title()}</td>
                <td>{stats['count']}</td>
                <td>{stats['average']:.1%}</td>
                <td>{stats['min']:.1%}</td>
                <td>{stats['max']:.1%}</td>
            </tr>
"""

        html += """
        </table>

        <h2>Individual Results</h2>
        <table>
            <tr><th>Task</th><th>Difficulty</th><th>Status</th><th>Score</th><th>Tags</th></tr>
"""

        for r in report.results:
            status_class = f"status-{r.status}"
            tags_html = " ".join(f'<span class="tag">{t}</span>' for t in r.tags[:3])
            html += f"""
            <tr>
                <td>{r.task_id}</td>
                <td>{r.difficulty}</td>
                <td class="{status_class}">{r.status.upper()}</td>
                <td>{r.overall_score:.1%}</td>
                <td>{tags_html}</td>
            </tr>
"""

        html += """
        </table>
    </div>
</body>
</html>
"""

        with open(path, 'w') as f:
            f.write(html)

        return str(path)


def main():
    parser = argparse.ArgumentParser(
        description="Run AgentX SQL Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all benchmarks
  python run_benchmark.py --output results/

  # Run only easy and medium tasks
  python run_benchmark.py --difficulty easy,medium --output results/

  # Export as HTML report
  python run_benchmark.py --format json,csv,html,summary --output results/

  # Filter by tags
  python run_benchmark.py --tags join,aggregation --output results/

  # Run enterprise benchmark (star schema, complex queries)
  python run_benchmark.py --schema enterprise --output results/

  # Run enterprise with specific tags
  python run_benchmark.py --schema enterprise --tags star_schema,window --output results/
"""
    )

    parser.add_argument("--agent-url", help="URL of agent A2A API (optional)")
    parser.add_argument("--tasks", help="Path to tasks JSON file")
    parser.add_argument("--output", "-o", default="results", help="Output directory")
    parser.add_argument("--difficulty", "-d", default="easy,medium,hard,enterprise",
                        help="Comma-separated difficulties to include")
    parser.add_argument("--tags", "-t", help="Comma-separated tags to filter")
    parser.add_argument("--format", "-f", default="json,csv,summary",
                        help="Comma-separated output formats (json,csv,summary,html)")
    parser.add_argument("--dialect", default="sqlite", help="SQL dialect")
    parser.add_argument("--schema", "-s", default="basic", choices=["basic", "enterprise"],
                        help="Schema type: basic (simple tables) or enterprise (star schema)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    config = BenchmarkConfig(
        agent_url=args.agent_url,
        tasks_path=args.tasks,
        output_dir=args.output,
        difficulties=args.difficulty.split(","),
        tags=args.tags.split(",") if args.tags else None,
        formats=args.format.split(","),
        dialect=args.dialect,
        verbose=args.verbose,
        schema=args.schema,
    )

    # Run benchmark
    runner = BenchmarkRunner(config)
    report = runner.run()

    # Export results
    exporter = MetricsExporter(config.output_dir)
    outputs = exporter.export(report, config.formats)

    print(f"\nExported results:")
    for fmt, path in outputs.items():
        print(f"  {fmt}: {path}")


if __name__ == "__main__":
    main()
