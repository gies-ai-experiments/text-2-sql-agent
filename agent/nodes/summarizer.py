"""Summarizer node — produces a natural language answer from query results.

Reads all query results from state, formats them into a human-readable
context block, then calls the LLM to synthesise a concise answer to the
original question.
"""

from __future__ import annotations

import logging
from pathlib import Path

import openai

from agent.config import MODEL, OPENAI_API_KEY
from agent.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template (loaded once at import time)
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "summarizer.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PREVIEW_ROWS = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_data_preview(rows: list[dict]) -> str:
    """Format a list of row dicts into an aligned text table.

    Displays up to ``_MAX_PREVIEW_ROWS`` rows.  Column widths are computed
    from the header names and the string representations of the cell values
    so that everything lines up nicely.
    """
    if not rows:
        return "(no data)"

    display_rows = rows[:_MAX_PREVIEW_ROWS]
    columns = list(display_rows[0].keys())

    # Compute column widths — max of header length and all cell values
    widths: dict[str, int] = {}
    for col in columns:
        widths[col] = len(str(col))
        for row in display_rows:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))

    # Header
    header = " | ".join(str(col).ljust(widths[col]) for col in columns)
    # Data rows
    lines = [f"  {header}"]
    for row in display_rows:
        line = " | ".join(
            str(row.get(col, "")).ljust(widths[col]) for col in columns
        )
        lines.append(f"  {line}")

    if len(rows) > _MAX_PREVIEW_ROWS:
        lines.append(f"  ... ({len(rows) - _MAX_PREVIEW_ROWS} more rows)")

    return "\n".join(lines)


def _build_results_context(state: AgentState) -> str:
    """Build a readable text block summarising all query results.

    For each result, the block includes:
    - Task description (looked up from the ``queries`` list by task_id)
    - Score
    - Status (with a degraded marker when relevant)
    - Data preview (aligned text table)
    - Error details, if any
    """
    results: list[dict] = state.get("query_results", [])
    queries: list[dict] = state.get("queries", [])

    # Build a lookup from task_id -> description for quick access
    description_by_id: dict[str, str] = {
        q["id"]: q.get("description", q["id"]) for q in queries
    }

    if not results:
        return "(no query results available)"

    sections: list[str] = []
    for result in results:
        task_id = result.get("task_id", "unknown")
        score = result.get("score", 0.0)
        status = result.get("status", "unknown")
        data = result.get("data", [])
        error = result.get("error", "")

        description = description_by_id.get(task_id, task_id)
        status_display = status if status == "success" else f"\u26a0 DEGRADED ({status})"

        parts = [
            f"--- Query: {task_id} (score: {score:.2f}) ---",
            f"Description: {description}",
            f"Status: {status_display}",
        ]

        if data:
            parts.append(f"Data ({len(data)} rows):")
            parts.append(_format_data_preview(data))
        else:
            parts.append("Data: (empty result set)")

        if error:
            parts.append(f"Error: {error}")

        sections.append("\n".join(parts))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------


def summarizer(state: AgentState) -> dict:
    """LangGraph node that produces a natural language answer.

    Formats all query results into a readable context block, injects them
    into the summarizer prompt, and calls the LLM for a final answer.

    Returns
    -------
    dict
        ``{"final_answer": <natural language answer string>}``
    """
    results_context = _build_results_context(state)

    prompt = _PROMPT_TEMPLATE.format(
        question=state.get("question", ""),
        results_context=results_context,
    )

    logger.debug("Summarizer prompt length: %d chars", len(prompt))

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    final_answer: str = response.choices[0].message.content or ""
    logger.info("Summarizer produced answer (%d chars)", len(final_answer))

    return {"final_answer": final_answer}
