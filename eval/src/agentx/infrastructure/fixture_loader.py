"""Bulk data loading using PostgreSQL COPY protocol.

Provides efficient fixture loading for test data setup using
PostgreSQL's COPY command for high-performance bulk inserts.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any

from psycopg import Connection

from agentx.infrastructure.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class FixtureLoader:
    """Loads fixture data using PostgreSQL COPY protocol.

    This class provides methods for efficiently loading test data:
    - Bulk insert from Python dicts via COPY
    - Load from CSV or JSON files
    - Transactional cleanup via TRUNCATE

    Example:
        loader = FixtureLoader(db_manager)
        rows_loaded = loader.load("users", [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ])
        print(f"Loaded {rows_loaded} rows")

        # Cleanup
        loader.teardown(["users", "orders"])
    """

    def __init__(self, db_manager: DatabaseManager, schema: str = "public"):
        """Initialize the fixture loader.

        Args:
            db_manager: DatabaseManager instance for connections
            schema: PostgreSQL schema for tables (default: "public")
        """
        self._db_manager = db_manager
        self._schema = schema

    @property
    def schema(self) -> str:
        """Get the schema for fixture loading."""
        return self._schema

    def load(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        columns: list[str] | None = None,
    ) -> int:
        """Load rows into a table using COPY protocol.

        Uses PostgreSQL's COPY command for efficient bulk loading.
        All rows must have the same columns.

        Args:
            table: Target table name
            rows: List of dictionaries representing rows
            columns: Optional list of columns (inferred from first row if not provided)

        Returns:
            Number of rows loaded

        Raises:
            ValueError: If rows is empty or columns are inconsistent
            RuntimeError: If database connection is not available

        Example:
            loader.load("users", [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ])
        """
        if not rows:
            logger.warning(f"No rows to load for table {table}")
            return 0

        # Determine columns from first row if not specified
        if columns is None:
            columns = list(rows[0].keys())

        logger.info(f"Loading {len(rows)} rows into {self._schema}.{table}")

        # Build CSV data in memory
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=columns,
            extrasaction="ignore",
        )

        for row in rows:
            # Convert non-string values for CSV
            csv_row = {}
            for col in columns:
                value = row.get(col)
                if value is None:
                    csv_row[col] = ""
                elif isinstance(value, (dict, list)):
                    csv_row[col] = json.dumps(value)
                elif isinstance(value, bool):
                    csv_row[col] = "t" if value else "f"
                else:
                    csv_row[col] = str(value)
            writer.writerow(csv_row)

        csv_data = csv_buffer.getvalue()
        csv_buffer.close()

        # Prepare column list for COPY command
        col_list = ", ".join(f'"{c}"' for c in columns)
        qualified_table = f"{self._schema}.{table}"

        with self._db_manager.connection() as conn:
            with conn.cursor() as cur:
                # Use COPY FROM STDIN with CSV format
                copy_sql = f"COPY {qualified_table} ({col_list}) FROM STDIN WITH (FORMAT CSV, NULL '')"

                with cur.copy(copy_sql) as copy:
                    copy.write(csv_data.encode("utf-8"))

                conn.commit()

        logger.info(f"Loaded {len(rows)} rows into {qualified_table}")
        return len(rows)

    def load_from_csv(
        self,
        table: str,
        filepath: str | Path,
        *,
        delimiter: str = ",",
        has_header: bool = True,
    ) -> int:
        """Load data from a CSV file using COPY protocol.

        Args:
            table: Target table name
            filepath: Path to CSV file
            delimiter: CSV delimiter (default: ",")
            has_header: Whether CSV has a header row (default: True)

        Returns:
            Number of rows loaded
        """
        filepath = Path(filepath)
        logger.info(f"Loading CSV {filepath} into {self._schema}.{table}")

        qualified_table = f"{self._schema}.{table}"

        with open(filepath, encoding="utf-8") as f:
            csv_data = f.read()

        # Parse to count rows (excluding header if present)
        lines = csv_data.strip().split("\n")
        row_count = len(lines) - 1 if has_header else len(lines)

        with self._db_manager.connection() as conn:
            with conn.cursor() as cur:
                copy_sql = f"""
                    COPY {qualified_table}
                    FROM STDIN WITH (
                        FORMAT CSV,
                        DELIMITER '{delimiter}',
                        HEADER {has_header}
                    )
                """
                with cur.copy(copy_sql) as copy:
                    copy.write(csv_data.encode("utf-8"))

                conn.commit()

        logger.info(f"Loaded {row_count} rows from CSV into {qualified_table}")
        return row_count

    def load_from_json(
        self,
        table: str,
        filepath: str | Path,
        *,
        columns: list[str] | None = None,
    ) -> int:
        """Load data from a JSON file.

        The JSON file should contain an array of objects.

        Args:
            table: Target table name
            filepath: Path to JSON file
            columns: Optional list of columns to load

        Returns:
            Number of rows loaded
        """
        filepath = Path(filepath)
        logger.info(f"Loading JSON {filepath} into {self._schema}.{table}")

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON file must contain an array of objects")

        return self.load(table, data, columns=columns)

    def teardown(
        self,
        tables: list[str],
        *,
        cascade: bool = False,
    ) -> None:
        """Truncate tables for cleanup.

        Truncates the specified tables, optionally with CASCADE.
        Tables are truncated in the order provided.

        Args:
            tables: List of table names to truncate
            cascade: If True, use TRUNCATE CASCADE (default: False)

        Example:
            loader.teardown(["order_items", "orders", "users"])
        """
        if not tables:
            return

        logger.info(f"Truncating tables: {tables}")

        cascade_sql = " CASCADE" if cascade else ""

        with self._db_manager.connection() as conn:
            with conn.cursor() as cur:
                for table in tables:
                    qualified_table = f"{self._schema}.{table}"
                    cur.execute(f"TRUNCATE TABLE {qualified_table}{cascade_sql}")
                conn.commit()

        logger.info(f"Truncated {len(tables)} tables")

    def create_savepoint(self, conn: Connection, name: str) -> None:
        """Create a savepoint for transactional rollback.

        Args:
            conn: Active connection
            name: Savepoint name
        """
        with conn.cursor() as cur:
            cur.execute(f"SAVEPOINT {name}")
        logger.debug(f"Created savepoint: {name}")

    def rollback_to_savepoint(self, conn: Connection, name: str) -> None:
        """Rollback to a savepoint.

        Args:
            conn: Active connection
            name: Savepoint name to rollback to
        """
        with conn.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
        logger.debug(f"Rolled back to savepoint: {name}")

    def release_savepoint(self, conn: Connection, name: str) -> None:
        """Release a savepoint.

        Args:
            conn: Active connection
            name: Savepoint name to release
        """
        with conn.cursor() as cur:
            cur.execute(f"RELEASE SAVEPOINT {name}")
        logger.debug(f"Released savepoint: {name}")

    def setup_test_fixtures(
        self,
        fixtures: dict[str, list[dict[str, Any]]],
    ) -> dict[str, int]:
        """Load multiple tables with fixture data.

        Convenience method for loading fixtures for multiple tables.

        Args:
            fixtures: Dictionary mapping table names to row lists

        Returns:
            Dictionary mapping table names to rows loaded

        Example:
            loaded = loader.setup_test_fixtures({
                "users": [{"id": 1, "name": "Alice"}],
                "orders": [{"id": 1, "user_id": 1, "amount": 100}],
            })
        """
        results = {}
        for table, rows in fixtures.items():
            results[table] = self.load(table, rows)
        return results
