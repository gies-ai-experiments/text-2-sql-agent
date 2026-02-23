"""
Dialect configurations for multi-database SQL support.
"""

from .registry import (
    Dialect,
    DialectConfig,
    DIALECT_CONFIGS,
    get_dialect_config,
    get_supported_dialects,
)

__all__ = [
    "Dialect",
    "DialectConfig",
    "DIALECT_CONFIGS",
    "get_dialect_config",
    "get_supported_dialects",
]
