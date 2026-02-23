"""LangGraph node: generate SQL for a single QueryTask using GPT-5."""

from __future__ import annotations

import logging
from pathlib import Path

import openai

from agent.config import MODEL, OPENAI_API_KEY
from agent.state import AgentState, QueryTask

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template — loaded once at import time
# ---------------------------------------------------------------------------
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "query_generator.txt"
_PROMPT_TEMPLATE: str = _PROMPT_PATH.read_text()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_sql(raw: str) -> str:
    """Strip markdown code fences, trailing semicolons, and whitespace."""
    text = raw.strip()
    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```sql or ```) and last line (```)
        lines = [l for l in lines[1:] if not l.strip() == "```"]
        text = "\n".join(lines)
    # Remove trailing semicolon
    text = text.rstrip().rstrip(";").rstrip()
    return text


def _format_rows_as_table(data: list[dict], max_rows: int = 20) -> str:
    """Format a list of row-dicts as a simple text table (up to *max_rows*)."""
    if not data:
        return "(no rows)"

    rows = data[:max_rows]
    columns = list(rows[0].keys())

    # Compute column widths (header vs. data)
    widths = {col: len(str(col)) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))

    # Header
    header = " | ".join(str(col).ljust(widths[col]) for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)
    body_lines = [
        " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        for row in rows
    ]

    table = "\n".join([header, separator, *body_lines])
    if len(data) > max_rows:
        table += f"\n... ({len(data) - max_rows} more rows omitted)"
    return table


def _build_predecessor_context(
    current_task: QueryTask,
    query_results: list[dict],
) -> str:
    """Build a text block with predecessor query results for sequential plans."""
    depends_on: list[str] = current_task.get("depends_on", [])
    if not depends_on:
        return ""

    results_by_id: dict[str, dict] = {
        r["task_id"]: r for r in query_results
    }

    sections: list[str] = []
    for dep_id in depends_on:
        result = results_by_id.get(dep_id)
        if result is None:
            sections.append(f"[Task {dep_id}]: (result not available)")
            continue
        table_text = _format_rows_as_table(result.get("data", []))
        sections.append(f"[Task {dep_id}]:\n{table_text}")

    return "\n== PREDECESSOR RESULTS ==\n" + "\n\n".join(sections)


def _build_retry_context(state: AgentState) -> str:
    """Build a text block with retry feedback, if applicable."""
    retry_feedback = state.get("retry_feedback")
    retry_count = state.get("retry_count", 0)

    if not retry_feedback or retry_count <= 0:
        return ""

    return (
        f"\n== RETRY FEEDBACK (attempt {retry_count}) ==\n"
        f"{retry_feedback}"
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def query_generator(state: AgentState) -> dict:
    """Generate SQL for the current QueryTask via GPT-5.

    Reads the current task from *state*, builds predecessor and retry context,
    calls the OpenAI chat completion API, cleans the response, and returns the
    updated task.

    Returns
    -------
    dict
        ``{"current_task": updated_task, "queries": [updated_task]}``
    """
    current_task: QueryTask = state["current_task"]

    predecessor_context = _build_predecessor_context(
        current_task,
        state.get("query_results", []),
    )
    retry_context = _build_retry_context(state)

    prompt = _PROMPT_TEMPLATE.format(
        dialect=state.get("dialect", "sqlite"),
        schema_context=state.get("schema_context", ""),
        task_description=current_task["description"],
        predecessor_context=predecessor_context,
        retry_context=retry_context,
    )

    logger.debug(
        "query_generator prompt for task %s (%d chars)",
        current_task["id"],
        len(prompt),
    )

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_sql = response.choices[0].message.content or ""
    clean = _clean_sql(raw_sql)

    logger.info(
        "Generated SQL for task %s: %s",
        current_task["id"],
        clean[:120],
    )

    updated_task: QueryTask = {**current_task, "sql": clean}
    return {"current_task": updated_task, "queries": [updated_task]}
