"""CLI entrypoint for the text-to-SQL agent.

Usage:
    python -m agent.main "How many customers are in each city?"
    python -m agent.main --dialect postgresql --db-path mydb.sqlite "Top 5 orders"
    python -m agent.main --verbose "Show total revenue by month"
"""

from __future__ import annotations

import argparse
import time

from agent.config import (
    MODEL,
    SCORE_THRESHOLD,
    MAX_RETRIES,
    DEFAULT_DIALECT,
    DEFAULT_DB_PATH,
)
from agent.graph import build_graph


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

def _format_table(rows: list[dict], max_rows: int = 50) -> str:
    """Format rows as a bordered SQL-style table.

    Example output::

        +----------+----------------+
        | region   | customer_count |
        +----------+----------------+
        | East     |             13 |
        | North    |             12 |
        +----------+----------------+
        2 rows
    """
    if not rows:
        return "(empty result set)"

    display = rows[:max_rows]
    columns = list(display[0].keys())

    # Compute column widths (min width = header length)
    widths: dict[str, int] = {col: len(str(col)) for col in columns}
    for row in display:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))

    # Build separator and format strings
    sep = "+-" + "-+-".join("-" * widths[col] for col in columns) + "-+"
    header = "| " + " | ".join(str(col).ljust(widths[col]) for col in columns) + " |"

    lines = [sep, header, sep]
    for row in display:
        cells = []
        for col in columns:
            val = row.get(col, "")
            s = str(val)
            # Right-align numbers
            if isinstance(val, (int, float)):
                cells.append(s.rjust(widths[col]))
            else:
                cells.append(s.ljust(widths[col]))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append(sep)

    total = len(rows)
    if total > max_rows:
        lines.append(f"{max_rows} of {total} rows (truncated)")
    else:
        lines.append(f"{total} row{'s' if total != 1 else ''}")

    return "\n".join(lines)


def _print_query_results(results: list[dict], queries: list[dict]) -> None:
    """Print each query result as a SQL-style table."""
    desc_by_id = {q["id"]: q.get("description", q["id"]) for q in queries}

    for result in results:
        task_id = result.get("task_id", "?")
        score = result.get("score", 0.0)
        status = result.get("status", "unknown")
        sql = ""

        # Find the SQL from the queries list
        for q in queries:
            if q["id"] == task_id:
                sql = q.get("sql", "")
                break

        print(f"\n  Task: {task_id} — {desc_by_id.get(task_id, task_id)}")
        if sql:
            print(f"  SQL:  {sql}")
        print(f"  Score: {score:.2f}  Status: {status}")

        error = result.get("error", "")
        if error:
            print(f"  Error: {error}")

        data = result.get("data", [])
        if data:
            print()
            for line in _format_table(data).split("\n"):
                print(f"  {line}")
        else:
            print("  (no rows returned)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Text-to-SQL agent powered by LangGraph + GPT-5",
    )
    parser.add_argument("question", help="Natural language question to answer")
    parser.add_argument(
        "--dialect",
        default=DEFAULT_DIALECT,
        help=f"SQL dialect (default: {DEFAULT_DIALECT})",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress and state dumps",
    )

    args = parser.parse_args()

    # -- Header --
    print(f"Model:     {MODEL}")
    print(f"Dialect:   {args.dialect}")
    print(f"DB path:   {args.db_path}")
    print(f"Threshold: {SCORE_THRESHOLD}")
    print(f"Retries:   {MAX_RETRIES}")
    print(f"Question:  {args.question}")
    print("-" * 60)

    initial_state = {
        "question": args.question,
        "dialect": args.dialect,
        "db_path": args.db_path,
        "schema_context": "",
        "plan": {"plan_type": "single", "tasks": [], "confidence": 0.0},
        "current_task": {"id": "", "description": "", "sql": "", "depends_on": []},
        "queries": [],
        "query_results": [],
        "retry_count": 0,
        "retry_feedback": "",
        "final_answer": "",
        "answer_relevance_score": 0.0,
    }

    graph = build_graph()
    start = time.perf_counter()
    event = {}

    # Accumulate results across all events for final display
    all_query_results: list[dict] = []
    all_queries: list[dict] = []
    final_answer = "(no answer produced)"
    relevance_score = None

    for event in graph.stream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            if update:
                # Collect query results and queries as they stream in
                if "query_results" in update:
                    all_query_results.extend(update["query_results"])
                if "queries" in update:
                    all_queries.extend(update["queries"])
                if "final_answer" in update:
                    final_answer = update["final_answer"]
                if "answer_relevance_score" in update:
                    relevance_score = update["answer_relevance_score"]

            if args.verbose:
                print(f"\n[{node_name}] ->")
                if update:
                    for key, value in update.items():
                        preview = str(value)
                        if len(preview) > 200:
                            preview = preview[:200] + "..."
                        print(f"  {key}: {preview}")
                else:
                    print("  (no state changes)")
            else:
                print(f"  [{node_name}] done")

    elapsed = time.perf_counter() - start
    print("-" * 60)

    # -- Query Results as Tables --
    if all_query_results:
        print("\nQuery Results:")
        _print_query_results(all_query_results, all_queries)

    # -- Final Answer --
    print("\n" + "=" * 60)
    print(f"\nAnswer:\n{final_answer}")
    if relevance_score is not None:
        print(f"\nAnswer Relevance Score: {relevance_score:.2f}")
    print(f"\nElapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
