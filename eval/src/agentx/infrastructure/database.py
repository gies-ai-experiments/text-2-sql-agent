"""
Database abstraction layer with adapters for different SQL dialects.

This module provides a unified interface for:
- Database connections
- Schema introspection
- Query execution

Supported dialects:
- SQLite (built-in, zero dependencies)
- DuckDB (pip install duckdb)
- PostgreSQL (pip install psycopg2-binary)
- BigQuery (pip install google-cloud-bigquery)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import time

from .models import ColumnInfo, TableInfo, SchemaSnapshot


@dataclass
class ExecutionResult:
    """Result of SQL query execution."""
    success: bool
    data: List[Dict[str, Any]]
    columns: List[str]
    rows_returned: int
    execution_time_ms: float
    error: Optional[str] = None
    dialect: str = ""


class DatabaseAdapter(ABC):
    """
    Abstract base class for database-specific operations.

    Each dialect implements this interface to provide:
    - Connection management
    - Schema introspection
    - Query execution
    """

    @abstractmethod
    def connect(self) -> Any:
        """Create and return a database connection."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    def get_dialect(self) -> str:
        """Return the sqlglot dialect name."""
        pass

    @abstractmethod
    def get_schema_snapshot(self) -> SchemaSnapshot:
        """Get complete schema information."""
        pass

    @abstractmethod
    def execute(self, sql: str) -> ExecutionResult:
        """Execute SQL and return results."""
        pass

    def execute_many(self, statements: List[str]) -> List[ExecutionResult]:
        """Execute multiple SQL statements."""
        results = []
        for sql in statements:
            results.append(self.execute(sql))
        return results


# =============================================================================
# SQLITE ADAPTER
# =============================================================================

class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite database adapter.

    Zero external dependencies - uses Python's built-in sqlite3 module.
    Supports in-memory databases for fast testing.
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize SQLite adapter.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory
        """
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Create SQLite connection."""
        import sqlite3
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self) -> None:
        """Close SQLite connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_dialect(self) -> str:
        return "sqlite"

    def get_schema_snapshot(self) -> SchemaSnapshot:
        """Get schema from SQLite database."""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        tables = {}

        # Get all tables (excluding SQLite internal tables)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        for (table_name,) in cursor.fetchall():
            # Get columns using PRAGMA
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = []

            for row in cursor.fetchall():
                # PRAGMA table_info returns:
                # cid, name, type, notnull, dflt_value, pk
                columns.append(ColumnInfo(
                    name=row[1],
                    dtype=row[2] or "TEXT",
                    nullable=not bool(row[3]),
                    primary_key=bool(row[5]),
                    default=row[4],
                ))

            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
            for fk_row in cursor.fetchall():
                # id, seq, table, from, to, on_update, on_delete, match
                from_col = fk_row[3]
                to_table = fk_row[2]
                to_col = fk_row[4]

                # Update column with FK info
                for col in columns:
                    if col.name == from_col:
                        col.foreign_key = f"{to_table}.{to_col}"
                        break

            # Get row count
            try:
                cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
                row_count = cursor.fetchone()[0]
            except Exception:
                row_count = None

            tables[table_name] = TableInfo(
                name=table_name,
                columns=columns,
                row_count=row_count,
            )

        return SchemaSnapshot(
            dialect="sqlite",
            database=self.db_path,
            tables=tables,
        )

    def execute(self, sql: str) -> ExecutionResult:
        """Execute SQL query."""
        if not self.conn:
            self.connect()

        start_time = time.time()

        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)

            # Check if query returns data
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                data = [dict(zip(columns, row)) for row in rows]

                elapsed = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=True,
                    data=data,
                    columns=columns,
                    rows_returned=len(data),
                    execution_time_ms=elapsed,
                    dialect="sqlite",
                )
            else:
                # Non-SELECT query
                self.conn.commit()
                elapsed = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=True,
                    data=[],
                    columns=[],
                    rows_returned=cursor.rowcount,
                    execution_time_ms=elapsed,
                    dialect="sqlite",
                )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                data=[],
                columns=[],
                rows_returned=0,
                execution_time_ms=elapsed,
                error=str(e),
                dialect="sqlite",
            )


# =============================================================================
# DUCKDB ADAPTER
# =============================================================================

class DuckDBAdapter(DatabaseAdapter):
    """
    DuckDB database adapter.

    DuckDB is an embedded analytical database, great for:
    - Fast analytics on CSV/Parquet files
    - In-memory processing
    - Compatible with pandas DataFrames
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize DuckDB adapter.

        Args:
            db_path: Path to DuckDB database file, or ":memory:" for in-memory
        """
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Create DuckDB connection."""
        try:
            import duckdb
            self.conn = duckdb.connect(self.db_path)
            return self.conn
        except ImportError:
            raise ImportError(
                "DuckDB is not installed. Install with: pip install duckdb"
            )

    def close(self) -> None:
        """Close DuckDB connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_dialect(self) -> str:
        return "duckdb"

    def get_schema_snapshot(self) -> SchemaSnapshot:
        """Get schema from DuckDB database."""
        if not self.conn:
            self.connect()

        tables = {}

        # Get all tables
        result = self.conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """).fetchall()

        for (table_name,) in result:
            # Get columns
            cols = self.conn.execute(f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                AND table_schema = 'main'
                ORDER BY ordinal_position
            """).fetchall()

            columns = [
                ColumnInfo(
                    name=col[0],
                    dtype=col[1],
                    nullable=(col[2] == 'YES'),
                    default=col[3],
                )
                for col in cols
            ]

            # Get row count
            try:
                row_count = self.conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
            except Exception:
                row_count = None

            tables[table_name] = TableInfo(
                name=table_name,
                columns=columns,
                schema="main",
                row_count=row_count,
            )

        return SchemaSnapshot(
            dialect="duckdb",
            database=self.db_path,
            tables=tables,
        )

    def execute(self, sql: str) -> ExecutionResult:
        """Execute SQL query."""
        if not self.conn:
            self.connect()

        start_time = time.time()

        try:
            result = self.conn.execute(sql)

            if result.description:
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                data = [dict(zip(columns, row)) for row in rows]

                elapsed = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=True,
                    data=data,
                    columns=columns,
                    rows_returned=len(data),
                    execution_time_ms=elapsed,
                    dialect="duckdb",
                )
            else:
                elapsed = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=True,
                    data=[],
                    columns=[],
                    rows_returned=0,
                    execution_time_ms=elapsed,
                    dialect="duckdb",
                )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                data=[],
                columns=[],
                rows_returned=0,
                execution_time_ms=elapsed,
                error=str(e),
                dialect="duckdb",
            )


# =============================================================================
# POSTGRESQL ADAPTER (using SQLAlchemy for compatibility)
# =============================================================================

class PostgreSQLAdapter(DatabaseAdapter):
    """
    PostgreSQL database adapter using SQLAlchemy.
    """

    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL adapter.

        Args:
            connection_string: PostgreSQL connection string
                e.g., "postgresql://user:pass@localhost:5432/dbname"
        """
        self.connection_string = connection_string
        self.engine = None
        self.conn = None

    def connect(self):
        """Create PostgreSQL connection."""
        try:
            from sqlalchemy import create_engine
            self.engine = create_engine(self.connection_string)
            self.conn = self.engine.connect()
            return self.conn
        except ImportError:
            raise ImportError(
                "SQLAlchemy is not installed. Install with: pip install sqlalchemy psycopg2-binary"
            )

    def close(self) -> None:
        """Close PostgreSQL connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.engine:
            self.engine.dispose()
            self.engine = None

    def get_dialect(self) -> str:
        return "postgres"

    def get_schema_snapshot(self) -> SchemaSnapshot:
        """Get schema from PostgreSQL database."""
        if not self.engine:
            self.connect()

        from sqlalchemy import inspect

        inspector = inspect(self.engine)
        tables = {}

        for table_name in inspector.get_table_names(schema="public"):
            columns = []

            # Get columns
            for col in inspector.get_columns(table_name, schema="public"):
                columns.append(ColumnInfo(
                    name=col["name"],
                    dtype=str(col["type"]),
                    nullable=col.get("nullable", True),
                    default=str(col.get("default")) if col.get("default") else None,
                ))

            # Get primary keys
            pk_constraint = inspector.get_pk_constraint(table_name, schema="public")
            pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []
            for col in columns:
                if col.name in pk_columns:
                    col.primary_key = True

            # Get foreign keys
            for fk in inspector.get_foreign_keys(table_name, schema="public"):
                constrained_cols = fk.get("constrained_columns", [])
                referred_table = fk.get("referred_table", "")
                referred_cols = fk.get("referred_columns", [])

                for i, col_name in enumerate(constrained_cols):
                    for col in columns:
                        if col.name == col_name and i < len(referred_cols):
                            col.foreign_key = f"{referred_table}.{referred_cols[i]}"

            tables[table_name] = TableInfo(
                name=table_name,
                columns=columns,
                schema="public",
            )

        return SchemaSnapshot(
            dialect="postgresql",
            database=self.connection_string.split("/")[-1].split("?")[0],
            tables=tables,
        )

    def execute(self, sql: str) -> ExecutionResult:
        """Execute SQL query."""
        if not self.conn:
            self.connect()

        from sqlalchemy import text

        start_time = time.time()

        try:
            result = self.conn.execute(text(sql))

            if result.returns_rows:
                columns = list(result.keys())
                data = [dict(row._mapping) for row in result.fetchall()]

                elapsed = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=True,
                    data=data,
                    columns=columns,
                    rows_returned=len(data),
                    execution_time_ms=elapsed,
                    dialect="postgresql",
                )
            else:
                elapsed = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=True,
                    data=[],
                    columns=[],
                    rows_returned=result.rowcount,
                    execution_time_ms=elapsed,
                    dialect="postgresql",
                )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                data=[],
                columns=[],
                rows_returned=0,
                execution_time_ms=elapsed,
                error=str(e),
                dialect="postgresql",
            )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_adapter(
    dialect: str,
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    **kwargs
) -> DatabaseAdapter:
    """
    Create appropriate database adapter for the given dialect.

    Args:
        dialect: Database dialect ("sqlite", "duckdb", "postgresql", etc.)
        connection_string: Connection string for server-based databases
        db_path: Path for file-based databases (SQLite, DuckDB)
        **kwargs: Additional dialect-specific options

    Returns:
        DatabaseAdapter instance

    Examples:
        # SQLite in-memory
        adapter = create_adapter("sqlite")

        # SQLite file
        adapter = create_adapter("sqlite", db_path="data.db")

        # DuckDB
        adapter = create_adapter("duckdb", db_path="analytics.duckdb")

        # PostgreSQL
        adapter = create_adapter(
            "postgresql",
            connection_string="postgresql://user:pass@localhost/db"
        )
    """
    dialect = dialect.lower()

    if dialect == "sqlite":
        return SQLiteAdapter(db_path=db_path or ":memory:")

    elif dialect == "duckdb":
        return DuckDBAdapter(db_path=db_path or ":memory:")

    elif dialect in ("postgresql", "postgres"):
        if not connection_string:
            raise ValueError("PostgreSQL requires a connection_string")
        return PostgreSQLAdapter(connection_string=connection_string)

    elif dialect == "bigquery":
        # TODO: Implement BigQuery adapter
        raise NotImplementedError("BigQuery adapter not yet implemented")

    elif dialect == "snowflake":
        # TODO: Implement Snowflake adapter
        raise NotImplementedError("Snowflake adapter not yet implemented")

    else:
        supported = ["sqlite", "duckdb", "postgresql"]
        raise ValueError(f"Unsupported dialect: {dialect}. Supported: {supported}")
