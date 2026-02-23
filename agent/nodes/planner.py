"""Planner node — decides the query execution strategy using GPT-5.

Reads the natural language question and schema context from state, then
produces a structured QueryPlan (single or multi-sequential)
via OpenAI's JSON Schema structured output mode.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import openai

from agent.config import MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)
from agent.state import AgentState, QueryPlan

# ---------------------------------------------------------------------------
# Prompt template (loaded once at import time)
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()

# ---------------------------------------------------------------------------
# JSON Schema for OpenAI structured output
# ---------------------------------------------------------------------------

PLAN_JSON_SCHEMA = {
    "name": "query_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "plan_type": {
                "type": "string",
                "enum": ["single", "multi-sequential"],
            },
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "sql": {"type": "string"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "description", "sql", "depends_on"],
                    "additionalProperties": False,
                },
            },
            "confidence": {"type": "number"},
        },
        "required": ["plan_type", "tasks", "confidence"],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def planner(state: AgentState) -> dict:
    """LangGraph node that produces a QueryPlan from the question + schema.

    Returns
    -------
    dict
        ``{"plan": QueryPlan}`` to be merged into AgentState.
    """
    prompt = _PROMPT_TEMPLATE.format(
        schema_context=state["schema_context"],
        question=state["question"],
    )

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": PLAN_JSON_SCHEMA,
            },
        )

        raw: str = response.choices[0].message.content or ""
        data: dict = json.loads(raw)

        plan: QueryPlan = {
            "plan_type": data["plan_type"],
            "tasks": data["tasks"],
            "confidence": data["confidence"],
        }

    except Exception as exc:
        logger.exception("Planner LLM call failed: %s", exc)
        # Fall back to a single-task plan so the graph can continue
        plan = {
            "plan_type": "single",
            "tasks": [{"id": "t1", "description": state["question"], "sql": "", "depends_on": []}],
            "confidence": 0.0,
        }

    if plan["confidence"] < 0.5:
        print(f"\u26a0 Low planner confidence: {plan['confidence']:.2f}")

    return {"plan": plan}
