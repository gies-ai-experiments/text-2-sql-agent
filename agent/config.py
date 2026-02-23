"""Central configuration for the text2sql agent."""

import os
from pathlib import Path

# Load .env file if present (for local dev — keeps secrets out of shell history)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

MODEL = os.environ.get("TEXT2SQL_MODEL", "gpt-5")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SCORE_THRESHOLD = float(os.environ.get("TEXT2SQL_SCORE_THRESHOLD", "0.70"))
MAX_RETRIES = int(os.environ.get("TEXT2SQL_MAX_RETRIES", "3"))
SCHEMA_CACHE_TTL_SECONDS = int(os.environ.get("TEXT2SQL_SCHEMA_CACHE_TTL", "300"))
DEFAULT_DIALECT = os.environ.get("TEXT2SQL_DIALECT", "sqlite")
DEFAULT_DB_PATH = os.environ.get("TEXT2SQL_DB_PATH", ":memory:")
