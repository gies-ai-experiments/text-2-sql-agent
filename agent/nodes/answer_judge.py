"""Answer Judge node — LLM-as-judge for end-to-end answer relevance.

After the summarizer produces a final answer, this node asks the LLM to
score how well that answer addresses the original user question.  This
catches problems that per-query scoring misses: bad decomposition, lost
context between sub-queries, and summarizer hallucination.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import openai

from agent.config import MODEL, OPENAI_API_KEY
from agent.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template (loaded once at import time)
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "answer_judge.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_PREVIEW_ROWS = 30


def _build_results_context(state: AgentState) -> str:
    """Build a compact text summary of query results for the judge."""
    results: list[dict] = state.get("query_results", [])
    queries: list[dict] = state.get("queries", [])

    description_by_id: dict[str, str] = {
        q["id"]: q.get("description", q["id"]) for q in queries
    }

    if not results:
        return "(no query results)"

    sections: list[str] = []
    for result in results:
        task_id = result.get("task_id", "unknown")
        data = result.get("data", [])
        status = result.get("status", "unknown")
        description = description_by_id.get(task_id, task_id)

        parts = [f"[{task_id}] {description} — {status}"]
        if data:
            cols = list(data[0].keys())
            parts.append("  " + " | ".join(cols))
            for row in data[:_MAX_PREVIEW_ROWS]:
                parts.append("  " + " | ".join(str(row.get(c, "")) for c in cols))
            if len(data) > _MAX_PREVIEW_ROWS:
                parts.append(f"  ... ({len(data) - _MAX_PREVIEW_ROWS} more rows)")
        else:
            parts.append("  (empty result set)")

        sections.append("\n".join(parts))

    return "\n\n".join(sections)


def parse_judge_response(text: str) -> tuple[float, str]:
    """Extract score and reasoning from the LLM judge response.

    Tries JSON parsing first, then falls back to regex extraction.
    Returns (score, reasoning).  On failure returns (0.5, <error msg>).
    """
    text = text.strip()

    # Try JSON parse
    try:
        obj = json.loads(text)
        score = float(obj["score"])
        reasoning = obj.get("reasoning", "")
        return (max(0.0, min(1.0, score)), reasoning)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # Fallback: extract JSON object from surrounding text
    json_match = re.search(r"\{[^}]+\}", text)
    if json_match:
        try:
            obj = json.loads(json_match.group())
            score = float(obj["score"])
            reasoning = obj.get("reasoning", "")
            return (max(0.0, min(1.0, score)), reasoning)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    # Last resort: look for a bare number
    num_match = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", text)
    if num_match:
        return (float(num_match.group(1)), "score extracted from unstructured response")

    return (0.5, "could not parse judge response — defaulting to 0.5")


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------


def answer_judge(state: AgentState) -> dict:
    """LangGraph node that scores end-to-end answer relevance.

    Returns
    -------
    dict
        ``{"answer_relevance_score": <float 0-1>}``
    """
    question = state.get("question", "")
    final_answer = state.get("final_answer", "")
    results_context = _build_results_context(state)

    if not final_answer:
        logger.warning("No final_answer to judge — returning 0.0")
        return {"answer_relevance_score": 0.0}

    prompt = _PROMPT_TEMPLATE.format(
        question=question,
        results_context=results_context,
        final_answer=final_answer,
    )

    logger.debug("Answer judge prompt length: %d chars", len(prompt))

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content or ""
    score, reasoning = parse_judge_response(raw)

    logger.info("Answer relevance score: %.2f — %s", score, reasoning)

    return {"answer_relevance_score": score}
