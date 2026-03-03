"""Per-query relevance checker — judges whether a sub-query is on-path.

Called from executor_eval after the SQL is executed and scored.  Asks the
LLM whether this sub-query's output actually contributes to answering the
original user question.  Returns a 0-1 relevance score that gets blended
into the overall eval score and surfaced to the retry handler.
"""

from __future__ import annotations

import logging
from pathlib import Path

import openai

from agent.config import MODEL, OPENAI_API_KEY
from agent.nodes.answer_judge import parse_judge_response  # reuse parser

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "query_relevance.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()

_MAX_PREVIEW_ROWS = 20


def _format_preview(data: list[dict]) -> str:
    """Format result rows into a compact text table for the prompt."""
    if not data:
        return "(empty result set)"

    display = data[:_MAX_PREVIEW_ROWS]
    cols = list(display[0].keys())
    lines = [" | ".join(cols)]
    for row in display:
        lines.append(" | ".join(str(row.get(c, "")) for c in cols))
    if len(data) > _MAX_PREVIEW_ROWS:
        lines.append(f"... ({len(data) - _MAX_PREVIEW_ROWS} more rows)")
    return "\n".join(lines)


def check_query_relevance(
    question: str,
    task_description: str,
    sql: str,
    data: list[dict],
) -> tuple[float, str]:
    """Check whether a sub-query result is on-path to the user's question.

    Parameters
    ----------
    question
        The original user question.
    task_description
        What this sub-query was supposed to accomplish.
    sql
        The SQL that was executed.
    data
        The result rows from execution.

    Returns
    -------
    tuple[float, str]
        (relevance_score 0-1, reasoning)
    """
    preview = _format_preview(data)

    prompt = _PROMPT_TEMPLATE.format(
        question=question,
        task_description=task_description,
        sql=sql,
        result_data=preview,
        max_rows=_MAX_PREVIEW_ROWS,
    )

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content or ""
    score, reasoning = parse_judge_response(raw)

    logger.info("Query relevance: %.2f — %s", score, reasoning)
    return score, reasoning
