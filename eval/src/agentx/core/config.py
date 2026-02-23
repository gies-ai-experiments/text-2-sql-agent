"""Framework configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AgentX framework configuration.

    Settings are loaded from environment variables with the AGENTX_ prefix.
    For example, AGENTX_DATABASE_URL sets the database_url field.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENTX_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database settings
    database_url: str = Field(
        default="postgresql://agentx:agentx@localhost:5432/agentx",
        description="PostgreSQL connection URL",
    )
    db_pool_min_size: int = Field(
        default=2,
        description="Minimum number of connections in the pool",
    )
    db_pool_max_size: int = Field(
        default=10,
        description="Maximum number of connections in the pool",
    )
    db_pool_timeout: float = Field(
        default=30.0,
        description="Timeout in seconds for acquiring a connection from the pool",
    )

    # Schema settings
    default_schema: str = Field(
        default="public",
        description="Default PostgreSQL schema to use",
    )

    # Fixture settings
    fixtures_path: str = Field(
        default="tasks/fixtures",
        description="Path to fixture data files",
    )

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    trace_output_path: str = Field(
        default="logs/traces",
        description="Path for structured trace logs",
    )

    # Execution settings
    query_timeout: float = Field(
        default=30.0,
        description="Timeout in seconds for SQL query execution",
    )
    max_sample_rows: int = Field(
        default=100,
        description="Maximum rows to return from sample queries",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses LRU cache to ensure settings are only loaded once.
    """
    return Settings()
