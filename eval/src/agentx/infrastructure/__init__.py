"""
Infrastructure layer for database connections and schema introspection.
"""

from .models import ColumnInfo, TableInfo, SchemaSnapshot
from .database import DatabaseAdapter, create_adapter

__all__ = [
    "ColumnInfo",
    "TableInfo",
    "SchemaSnapshot",
    "DatabaseAdapter",
    "create_adapter",
]
