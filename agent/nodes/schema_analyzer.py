"""
Schema Analyzer — LangGraph node for database schema introspection.

Reads the database schema via the eval infrastructure's SQLExecutor,
formats it into a compact text representation for downstream LLM nodes,
and caches the result using a TTL + content-hash invalidation strategy.

No LLM call is made here — this is pure data transformation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from agentx import SQLExecutor, ExecutorConfig, SchemaSnapshot

from agent.state import AgentState
from agent import config as agent_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level schema cache
# ---------------------------------------------------------------------------
_schema_cache: dict[str, Any] = {
    "hash": "",          # SHA-256 hex digest of the schema content
    "timestamp": 0.0,    # time.monotonic() when the cache was populated
    "formatted": "",     # The formatted schema string
}


def _compute_schema_hash(snapshot: SchemaSnapshot) -> str:
    """Compute a deterministic SHA-256 hash of the schema content.

    The ``captured_at`` field is deliberately excluded so that a cache
    hit is based purely on structural content, not on when the snapshot
    was taken.
    """
    schema_dict = snapshot.to_dict()
    schema_dict.pop("captured_at", None)

    # json.dumps with sort_keys guarantees deterministic serialisation
    canonical = json.dumps(schema_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_schema(snapshot: SchemaSnapshot) -> str:
    """Format a SchemaSnapshot into compact, LLM-friendly text.

    Output looks like::

        Table: customers
          id (INTEGER, PK)
          name (TEXT)
          email (TEXT, nullable)
          city_id (INTEGER, FK -> cities.id)

        Table: orders
          ...
    """
    parts: list[str] = []

    for table_name in sorted(snapshot.tables):
        table = snapshot.tables[table_name]
        parts.append(f"Table: {table.name}")

        for col in table.columns:
            tokens: list[str] = [col.dtype]

            if col.primary_key:
                tokens.append("PK")
            if col.foreign_key:
                tokens.append(f"FK -> {col.foreign_key}")
            if col.nullable and not col.primary_key:
                tokens.append("nullable")

            annotation = ", ".join(tokens)
            parts.append(f"  {col.name} ({annotation})")

        parts.append("")  # blank line between tables

    return "\n".join(parts).rstrip("\n")


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------

def schema_analyzer(state: AgentState) -> dict:
    """Introspect the database schema and return formatted context.

    On a cache hit (same content hash and TTL not expired) the previously
    formatted string is returned immediately, avoiding redundant work.

    Returns
    -------
    dict
        ``{"schema_context": <formatted schema string>}``
    """
    global _schema_cache

    executor = SQLExecutor(
        ExecutorConfig(
            dialect=state["dialect"],
            db_path=state["db_path"],
        )
    )

    try:
        snapshot: SchemaSnapshot = executor.schema
        current_hash = _compute_schema_hash(snapshot)
        now = time.monotonic()

        cache_age = now - _schema_cache["timestamp"]
        ttl = agent_config.SCHEMA_CACHE_TTL_SECONDS
        cache_valid = (
            _schema_cache["hash"] == current_hash
            and cache_age < ttl
            and _schema_cache["formatted"]
        )

        if cache_valid:
            logger.debug(
                "Schema cache hit (age=%.1fs, ttl=%ds)", cache_age, ttl
            )
            return {"schema_context": _schema_cache["formatted"]}

        # Cache miss — format and store
        logger.debug("Schema cache miss — formatting %d tables", len(snapshot.tables))
        formatted = _format_schema(snapshot)

        _schema_cache = {
            "hash": current_hash,
            "timestamp": now,
            "formatted": formatted,
        }

        return {"schema_context": formatted}

    finally:
        executor.close()
