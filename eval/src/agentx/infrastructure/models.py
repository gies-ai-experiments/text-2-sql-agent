"""
Data models for database schema representation.

These models are dialect-agnostic and used across all database adapters.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class ColumnInfo:
    """Metadata for a database column."""
    name: str
    dtype: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: Optional[str] = None  # Format: "table.column"
    default: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.dtype,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
            "foreign_key": self.foreign_key,
            "default": self.default,
        }


@dataclass
class TableInfo:
    """Metadata for a database table."""
    name: str
    columns: List[ColumnInfo]
    schema: Optional[str] = None
    row_count: Optional[int] = None

    def get_column(self, name: str) -> Optional[ColumnInfo]:
        """Get column by name (case-insensitive)."""
        name_lower = name.lower()
        for col in self.columns:
            if col.name.lower() == name_lower:
                return col
        return None

    def has_column(self, name: str) -> bool:
        """Check if column exists (case-insensitive)."""
        return self.get_column(name) is not None

    @property
    def column_names(self) -> List[str]:
        """Get list of column names."""
        return [col.name for col in self.columns]

    @property
    def primary_keys(self) -> List[str]:
        """Get list of primary key column names."""
        return [col.name for col in self.columns if col.primary_key]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema": self.schema,
            "columns": [col.to_dict() for col in self.columns],
            "row_count": self.row_count,
        }


@dataclass
class SchemaSnapshot:
    """
    Complete snapshot of a database schema.

    Contains all tables and their columns for validation purposes.
    """
    dialect: str
    database: str
    tables: Dict[str, TableInfo] = field(default_factory=dict)
    captured_at: datetime = field(default_factory=datetime.utcnow)

    def has_table(self, name: str) -> bool:
        """Check if table exists (case-insensitive)."""
        name_lower = name.lower()
        return any(t.lower() == name_lower for t in self.tables.keys())

    def get_table(self, name: str) -> Optional[TableInfo]:
        """Get table by name (case-insensitive)."""
        name_lower = name.lower()
        for table_name, table_info in self.tables.items():
            if table_name.lower() == name_lower:
                return table_info
        return None

    def has_column(self, table: str, column: str) -> bool:
        """Check if column exists in table (case-insensitive)."""
        table_info = self.get_table(table)
        if not table_info:
            return False
        return table_info.has_column(column)

    def get_all_columns(self) -> Dict[str, List[str]]:
        """Get all columns organized by table."""
        return {
            table_name: table_info.column_names
            for table_name, table_info in self.tables.items()
        }

    def get_column_anywhere(self, column: str) -> List[str]:
        """
        Find which tables contain a column.

        Returns list of table names that have this column.
        """
        tables_with_column = []
        column_lower = column.lower()
        for table_name, table_info in self.tables.items():
            if any(c.name.lower() == column_lower for c in table_info.columns):
                tables_with_column.append(table_name)
        return tables_with_column

    @property
    def table_names(self) -> List[str]:
        """Get list of all table names."""
        return list(self.tables.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dialect": self.dialect,
            "database": self.database,
            "tables": {name: info.to_dict() for name, info in self.tables.items()},
            "captured_at": self.captured_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchemaSnapshot":
        """Create SchemaSnapshot from dictionary."""
        tables = {}
        for table_name, table_data in data.get("tables", {}).items():
            columns = [
                ColumnInfo(
                    name=col["name"],
                    dtype=col["type"],
                    nullable=col.get("nullable", True),
                    primary_key=col.get("primary_key", False),
                    foreign_key=col.get("foreign_key"),
                )
                for col in table_data.get("columns", [])
            ]
            tables[table_name] = TableInfo(
                name=table_name,
                columns=columns,
                schema=table_data.get("schema"),
                row_count=table_data.get("row_count"),
            )

        return cls(
            dialect=data.get("dialect", ""),
            database=data.get("database", ""),
            tables=tables,
        )
