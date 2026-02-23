#!/usr/bin/env python3
"""
AgentX Evaluation Framework - Demo Script

This script demonstrates the key features of the AgentX SQL evaluation framework.
Run each section to showcase different capabilities.

Usage:
    python demo.py              # Run full demo
    python demo.py --section 1  # Run specific section
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def print_header(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_subheader(title):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---\n")


def pause(message="Press Enter to continue..."):
    """Pause for user input."""
    input(f"\n{message}")


def demo_section_1():
    """Section 1: Multi-Dialect SQL Execution"""
    print_header("SECTION 1: Multi-Dialect SQL Execution")

    print("AgentX supports multiple SQL dialects with zero-config setup.\n")

    from agentx import SQLExecutor, ExecutorConfig

    # SQLite Demo
    print_subheader("SQLite (Default, In-Memory)")

    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

    # Create sample data
    executor.adapter.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            price REAL
        )
    """)
    executor.adapter.execute("INSERT INTO products VALUES (1, 'Laptop', 'Electronics', 999.99)")
    executor.adapter.execute("INSERT INTO products VALUES (2, 'Mouse', 'Electronics', 29.99)")
    executor.adapter.execute("INSERT INTO products VALUES (3, 'Desk', 'Furniture', 199.99)")
    executor.refresh_schema()

    # Execute query
    result = executor.process_query("""
        SELECT category, COUNT(*) as count, ROUND(AVG(price), 2) as avg_price
        FROM products
        GROUP BY category
    """)

    print(f"Query Status: {result.overall_status}")
    print(f"Results: {result.data}")
    print(f"Execution Time: {result.execution.get('execution_time_ms', 0):.2f}ms")

    executor.close()

    # DuckDB Demo
    print_subheader("DuckDB (Analytics)")

    executor = SQLExecutor(ExecutorConfig(dialect="duckdb"))
    executor.adapter.execute("CREATE TABLE sales (product TEXT, amount REAL, date DATE)")
    executor.adapter.execute("INSERT INTO sales VALUES ('Widget', 100.0, '2024-01-15')")
    executor.adapter.execute("INSERT INTO sales VALUES ('Gadget', 150.0, '2024-01-16')")
    executor.refresh_schema()

    result = executor.process_query("SELECT product, SUM(amount) as total FROM sales GROUP BY product")
    print(f"DuckDB Result: {result.data}")

    executor.close()

    print("\n[Supported: SQLite, DuckDB, PostgreSQL, BigQuery, Snowflake]")


def demo_section_2():
    """Section 2: Hallucination Detection"""
    print_header("SECTION 2: Hallucination Detection")

    print("AgentX detects phantom tables, columns, and functions BEFORE execution.\n")

    from agentx import SQLExecutor, ExecutorConfig

    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

    # Setup real schema
    executor.adapter.execute("CREATE TABLE users (id INTEGER, name TEXT, email TEXT)")
    executor.adapter.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@test.com')")
    executor.refresh_schema()

    print("Actual Schema: users(id, name, email)\n")

    # Test 1: Phantom Table
    print_subheader("Test 1: Phantom Table Detection")
    result = executor.process_query("SELECT * FROM customers")  # 'customers' doesn't exist
    print(f"Query: SELECT * FROM customers")
    print(f"Status: {result.overall_status}")
    print(f"Errors: {result.validation.get('errors', [])}")

    # Test 2: Phantom Column
    print_subheader("Test 2: Phantom Column Detection")
    result = executor.process_query("SELECT id, name, phone FROM users")  # 'phone' doesn't exist
    print(f"Query: SELECT id, name, phone FROM users")
    print(f"Status: {result.overall_status}")
    print(f"Errors: {result.validation.get('errors', [])}")

    # Test 3: Valid Query
    print_subheader("Test 3: Valid Query (No Hallucinations)")
    result = executor.process_query("SELECT id, name FROM users WHERE id = 1")
    print(f"Query: SELECT id, name FROM users WHERE id = 1")
    print(f"Status: {result.overall_status}")
    print(f"Data: {result.data}")

    executor.close()


def demo_section_3():
    """Section 3: 7-Dimensional Scoring"""
    print_header("SECTION 3: 7-Dimensional Scoring System")

    print("AgentX scores SQL queries across 7 dimensions:\n")
    print("  1. Correctness (35%)     - Results match expected output")
    print("  2. Safety (20%)          - No hallucinations or dangerous patterns")
    print("  3. Efficiency (15%)      - Query execution performance")
    print("  4. Completeness (10%)    - Result quality (nulls, truncation)")
    print("  5. Semantic Accuracy (10%) - Value-level comparison")
    print("  6. Best Practices (5%)   - SQL code quality")
    print("  7. Plan Quality (5%)     - Execution plan analysis\n")

    from agentx import SQLExecutor, ExecutorConfig
    from evaluation.enhanced_scorer import EnhancedScorer
    from evaluation.result_comparator import DefaultResultComparator
    from evaluation.data_structures import ExecutionResult, ComparisonResult

    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))
    executor.adapter.execute("CREATE TABLE orders (id INTEGER, customer TEXT, total REAL)")
    executor.adapter.execute("INSERT INTO orders VALUES (1, 'Alice', 150.0)")
    executor.adapter.execute("INSERT INTO orders VALUES (2, 'Bob', 200.0)")
    executor.adapter.execute("INSERT INTO orders VALUES (3, 'Alice', 75.0)")
    executor.refresh_schema()

    scorer = EnhancedScorer()
    comparator = DefaultResultComparator()

    # Good Query
    print_subheader("Scoring a Well-Written Query")

    sql = "SELECT customer, SUM(total) as total_spent FROM orders GROUP BY customer"
    expected = [{"customer": "Alice", "total_spent": 225.0}, {"customer": "Bob", "total_spent": 200.0}]

    result = executor.process_query(sql)
    comparison = comparator.compare(result.data, expected)

    exec_result = ExecutionResult(
        success=True,
        data=result.data,
        rows_returned=len(result.data),
        execution_time_ms=result.execution.get('execution_time_ms', 0),
        is_valid=True,
        validation_errors=[],
    )

    score = scorer.score(
        comparison=comparison,
        execution_result=exec_result,
        sql=sql,
        dialect="sqlite",
        expected_results=expected,
    )

    print(f"SQL: {sql}\n")
    print(f"Overall Score:      {score.overall:.1%}")
    print(f"  Correctness:      {score.correctness:.1%}")
    print(f"  Safety:           {score.safety:.1%}")
    print(f"  Efficiency:       {score.efficiency:.1%}")
    print(f"  Best Practices:   {score.best_practices_score:.1%}")

    # Bad Query (SELECT *)
    print_subheader("Scoring a Query with Bad Practices")

    sql_bad = "SELECT * FROM orders"
    result_bad = executor.process_query(sql_bad)

    exec_result_bad = ExecutionResult(
        success=True,
        data=result_bad.data,
        rows_returned=len(result_bad.data),
        execution_time_ms=0.1,
        is_valid=True,
        validation_errors=[],
    )

    score_bad = scorer.score(
        comparison=ComparisonResult(is_match=True, match_score=1.0, row_count_match=True, column_count_match=True),
        execution_result=exec_result_bad,
        sql=sql_bad,
        dialect="sqlite",
    )

    print(f"SQL: {sql_bad}\n")
    print(f"Overall Score:      {score_bad.overall:.1%}")
    print(f"  Best Practices:   {score_bad.best_practices_score:.1%}")
    if score_bad.best_practices_report:
        print(f"  Violations:       {score_bad.best_practices_report.get('violations', [])}")

    executor.close()


def demo_section_4():
    """Section 4: Enterprise Schema & Complex Queries"""
    print_header("SECTION 4: Enterprise Data Warehouse Benchmark")

    print("AgentX includes an enterprise benchmark with:")
    print("  - 19 tables (fact tables, dimensions, SCD Type 2)")
    print("  - 30 complex query patterns")
    print("  - 2000+ rows of realistic sample data\n")

    from agentx import SQLExecutor, ExecutorConfig
    from tasks.enterprise_schema import setup_enterprise_schema

    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

    print("Setting up enterprise schema...")
    setup_enterprise_schema(executor)

    # Show schema
    schema = executor.adapter.get_schema_snapshot()
    tables = [t.name if hasattr(t, 'name') else str(t) for t in schema.tables]
    print(f"\nTables created: {len(tables)}")
    print(f"  Fact tables: sales_fact, orders_fact, user_events")
    print(f"  Dimensions: dim_customer, dim_product, dim_store, dim_date")
    print(f"  Special: dim_customer_scd (Type 2), employees (hierarchy)")

    # Run enterprise queries
    print_subheader("Enterprise Query 1: Star Schema Join")

    sql = """
        SELECT dp.category, ds.region,
               SUM(sf.quantity * sf.unit_price) as total_sales
        FROM sales_fact sf
        JOIN dim_product dp ON sf.product_id = dp.product_id
        JOIN dim_store ds ON sf.store_id = ds.store_id
        GROUP BY dp.category, ds.region
        ORDER BY 3 DESC
        LIMIT 5
    """
    result = executor.process_query(sql)
    print(f"Status: {result.overall_status}")
    print(f"Results (top 5):")
    for row in result.data[:5]:
        print(f"  {row}")

    print_subheader("Enterprise Query 2: SCD Type 2 (Point-in-Time)")

    sql = """
        SELECT customer_id, customer_name, segment, valid_from, valid_to
        FROM dim_customer_scd
        WHERE is_current = 1
        ORDER BY customer_id
        LIMIT 5
    """
    result = executor.process_query(sql)
    print(f"Current customer records:")
    for row in result.data[:5]:
        print(f"  {row}")

    print_subheader("Enterprise Query 3: Window Function (Running Total)")

    sql = """
        SELECT dd.full_date,
               SUM(sf.quantity * sf.unit_price) as daily_total
        FROM sales_fact sf
        JOIN dim_date dd ON sf.date_id = dd.date_id
        GROUP BY dd.full_date
        ORDER BY dd.full_date
        LIMIT 10
    """
    result = executor.process_query(sql)
    print(f"Daily sales totals:")
    for row in result.data[:5]:
        print(f"  {row}")

    executor.close()


def demo_section_5():
    """Section 5: A2A Protocol Interface"""
    print_header("SECTION 5: A2A Protocol (Agent-to-Agent Interface)")

    print("AgentX provides a REST API for external LLM agents to connect.\n")

    print("Endpoints:")
    print("  GET  /info         - Benchmark information")
    print("  GET  /health       - Health check")
    print("  GET  /schema       - Database schema")
    print("  POST /agents/register - Register an agent")
    print("  POST /tasks        - Get evaluation tasks")
    print("  POST /evaluate     - Submit SQL for evaluation")
    print("  GET  /leaderboard  - View rankings\n")

    print_subheader("Simulating Agent Workflow")

    from a2a.server import A2AServer
    from a2a.models import AgentInfo, TaskRequest, EvaluationRequest

    server = A2AServer(dialect="sqlite")

    # Register agent
    agent_info = AgentInfo(
        agent_id="",  # Server will generate
        agent_name="DemoAgent",
        agent_version="1.0.0",
        capabilities=["sql_generation"]
    )
    registered = server.register_agent(agent_info)
    print(f"1. Registered agent: {registered.agent_name} (ID: {registered.agent_id[:8]}...)")

    # Get tasks
    task_request = TaskRequest(agent_id=registered.agent_id, difficulty="easy", limit=3)
    task_response = server.get_tasks(task_request)
    print(f"\n2. Retrieved {len(task_response.tasks)} tasks:")
    for t in task_response.tasks:
        print(f"   - {t.task_id}: {t.question[:50]}...")

    # Evaluate SQL
    print(f"\n3. Submitting SQL for evaluation...")
    if task_response.tasks:
        eval_request = EvaluationRequest(
            agent_id=registered.agent_id,
            task_id=task_response.tasks[0].task_id,
            sql="SELECT * FROM customers LIMIT 10"
        )
        eval_result = server.evaluate_submission(eval_request)

        print(f"   Status: {eval_result.status}")
        if eval_result.scores:
            print(f"   Overall Score: {eval_result.scores.overall:.1%}")
            print(f"   Correctness: {eval_result.scores.correctness:.1%}")
            print(f"   Safety: {eval_result.scores.safety:.1%}")
        else:
            print(f"   (No scores - validation issues)")

    # Leaderboard
    print(f"\n4. Leaderboard:")
    leaderboard = server.get_leaderboard()
    if leaderboard:
        for i, entry in enumerate(leaderboard[:3], 1):
            print(f"   {i}. {entry.agent_name}: {entry.average_score:.1%}")
    else:
        print("   (No entries yet)")


def demo_section_6():
    """Section 6: Benchmark Runner & Reports"""
    print_header("SECTION 6: Benchmark Runner & Metrics Export")

    print("AgentX includes a benchmark runner for batch evaluation.\n")

    from run_benchmark import BenchmarkRunner, BenchmarkConfig, MetricsExporter

    config = BenchmarkConfig(
        output_dir="results",
        difficulties=["easy"],
        formats=["json", "csv"],
        dialect="sqlite",
        verbose=False,
    )

    print("Running benchmark on 'easy' difficulty queries...")
    print("(This evaluates gold SQL against the scoring system)\n")

    runner = BenchmarkRunner(config)
    report = runner.run()

    print_subheader("Benchmark Results")
    print(f"Total Tasks:    {report.total_tasks}")
    print(f"Successful:     {report.successful}")
    print(f"Failed:         {report.failed}")
    print(f"\nAverage Score:  {report.average_score:.1%}")
    print(f"Median Score:   {report.median_score:.1%}")
    print(f"Min Score:      {report.min_score:.1%}")
    print(f"Max Score:      {report.max_score:.1%}")

    print_subheader("Scores by Dimension")
    for dim, score in report.scores_by_dimension.items():
        print(f"  {dim:20s}: {score:.1%}")

    # Export
    exporter = MetricsExporter(config.output_dir)
    outputs = exporter.export(report, ["json", "csv"])

    print_subheader("Exported Reports")
    for fmt, path in outputs.items():
        print(f"  {fmt}: {path}")


def demo_summary():
    """Print demo summary."""
    print_header("DEMO COMPLETE - AgentX Evaluation Framework")

    print("Key Features Demonstrated:\n")
    print("  1. Multi-Dialect Support    - SQLite, DuckDB, PostgreSQL, BigQuery")
    print("  2. Hallucination Detection  - Catches phantom tables/columns/functions")
    print("  3. 7-Dimensional Scoring    - Correctness, safety, efficiency, etc.")
    print("  4. Enterprise Benchmark     - Star schema, SCD, window functions")
    print("  5. A2A Protocol Interface   - REST API for agent integration")
    print("  6. Benchmark Runner         - Batch evaluation with metrics export")

    print("\n" + "="*70)
    print("  Ready for LLM SQL agents to connect and be evaluated!")
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="AgentX Demo Script")
    parser.add_argument("--section", "-s", type=int, choices=[1,2,3,4,5,6],
                        help="Run specific section (1-6)")
    parser.add_argument("--no-pause", action="store_true",
                        help="Run without pausing between sections")
    args = parser.parse_args()

    sections = [
        ("Multi-Dialect SQL Execution", demo_section_1),
        ("Hallucination Detection", demo_section_2),
        ("7-Dimensional Scoring", demo_section_3),
        ("Enterprise Benchmark", demo_section_4),
        ("A2A Protocol Interface", demo_section_5),
        ("Benchmark Runner", demo_section_6),
    ]

    print("\n" + "="*70)
    print("       AGENTX - Multi-Dialect SQL Evaluation Framework")
    print("              Hackathon Demo Presentation")
    print("="*70)

    if args.section:
        # Run specific section
        name, func = sections[args.section - 1]
        func()
    else:
        # Run all sections
        for i, (name, func) in enumerate(sections, 1):
            if not args.no_pause and i > 1:
                pause(f"Press Enter for Section {i}: {name}...")
            func()

    if not args.section:
        demo_summary()


if __name__ == "__main__":
    main()
