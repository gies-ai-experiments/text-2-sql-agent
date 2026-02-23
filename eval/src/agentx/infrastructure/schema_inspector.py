"""Schema introspection using PostgreSQL catalog queries.

Provides schema introspection via pg_catalog and information_schema,
extracting tables, columns, primary keys, and foreign key relationships.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from psycopg import Connection
from psycopg.rows import dict_row

from agentx.core.models import ColumnInfo, ForeignKey, SchemaSnapshot, TableInfo

logger = logging.getLogger(__name__)


class SchemaInspector:
    """Inspects PostgreSQL schema using catalog queries.

    This class provides methods to introspect database schema using
    PostgreSQL's pg_catalog and information_schema, extracting:
    - Table names and metadata
    - Column names, types, nullability
    - Primary key constraints
    - Foreign key relationships

    Example:
        with db.connection() as conn:
            inspector = SchemaInspector(conn, schema="public")
            tables = inspector.get_tables()
            snapshot = inspector.get_schema_snapshot()
    """

    def __init__(self, conn: Connection, schema: str = "public"):
        """Initialize the schema inspector.

        Args:
            conn: Active psycopg Connection
            schema: PostgreSQL schema to inspect (default: "public")
        """
        self._conn = conn
        self._schema = schema

    @property
    def schema(self) -> str:
        """Get the schema being inspected."""
        return self._schema

    def get_tables(self) -> list[str]:
        """Get all table names in the schema.

        Returns:
            List of table names

        Example:
            tables = inspector.get_tables()
            # ['users', 'orders', 'products']
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (self._schema,))
            rows = cur.fetchall()
            return [row["table_name"] for row in rows]

    def get_columns(self, table: str) -> list[ColumnInfo]:
        """Get column information for a table.

        Args:
            table: Table name

        Returns:
            List of ColumnInfo objects with column metadata

        Example:
            columns = inspector.get_columns("users")
            for col in columns:
                print(f"{col.name}: {col.dtype}, nullable={col.nullable}")
        """
        # Get column info from information_schema
        column_query = """
            SELECT
                c.column_name,
                c.data_type,
                c.udt_name,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale
            FROM information_schema.columns c
            WHERE c.table_schema = %s
              AND c.table_name = %s
            ORDER BY c.ordinal_position
        """

        # Get primary key columns
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        """

        # Get foreign key columns
        fk_query = """
            SELECT
                kcu.column_name,
                ccu.table_name AS references_table,
                ccu.column_name AS references_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        """

        with self._conn.cursor(row_factory=dict_row) as cur:
            # Get columns
            cur.execute(column_query, (self._schema, table))
            column_rows = cur.fetchall()

            # Get primary keys
            cur.execute(pk_query, (self._schema, table))
            pk_columns = {row["column_name"] for row in cur.fetchall()}

            # Get foreign keys
            cur.execute(fk_query, (self._schema, table))
            fk_rows = cur.fetchall()
            fk_map = {
                row["column_name"]: f"{row['references_table']}.{row['references_column']}"
                for row in fk_rows
            }

        columns = []
        for row in column_rows:
            # Build full type string
            dtype = row["data_type"]
            if row["character_maximum_length"]:
                dtype = f"{dtype}({row['character_maximum_length']})"
            elif row["numeric_precision"] and row["data_type"] == "numeric":
                if row["numeric_scale"]:
                    dtype = f"{dtype}({row['numeric_precision']},{row['numeric_scale']})"
                else:
                    dtype = f"{dtype}({row['numeric_precision']})"

            col = ColumnInfo(
                name=row["column_name"],
                dtype=dtype,
                nullable=row["is_nullable"] == "YES",
                primary_key=row["column_name"] in pk_columns,
                foreign_key=fk_map.get(row["column_name"]),
            )
            columns.append(col)

        return columns

    def get_foreign_keys(self, table: str) -> list[ForeignKey]:
        """Get foreign key relationships for a table.

        Args:
            table: Table name

        Returns:
            List of ForeignKey objects describing the relationships

        Example:
            fks = inspector.get_foreign_keys("orders")
            for fk in fks:
                print(f"{fk.column} -> {fk.references_table}.{fk.references_column}")
        """
        query = """
            SELECT
                kcu.column_name,
                ccu.table_name AS references_table,
                ccu.column_name AS references_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.column_name
        """

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (self._schema, table))
            rows = cur.fetchall()

        return [
            ForeignKey(
                column=row["column_name"],
                references_table=row["references_table"],
                references_column=row["references_column"],
                constraint_name=row["constraint_name"],
            )
            for row in rows
        ]

    def get_primary_keys(self, table: str) -> list[str]:
        """Get primary key columns for a table.

        Args:
            table: Table name

        Returns:
            List of column names that form the primary key

        Example:
            pk_cols = inspector.get_primary_keys("order_items")
            # ['order_id', 'product_id']
        """
        query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (self._schema, table))
            rows = cur.fetchall()

        return [row["column_name"] for row in rows]

    def get_table_row_count(self, table: str) -> int:
        """Get the approximate row count for a table.

        Uses pg_class statistics for fast approximate count.

        Args:
            table: Table name

        Returns:
            Approximate row count (may not be exact)
        """
        query = """
            SELECT reltuples::bigint AS estimate
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname = %s
        """

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (self._schema, table))
            row = cur.fetchone()
            if row and row["estimate"] >= 0:
                return int(row["estimate"])
            # Fallback to COUNT(*) for empty tables or if stats not available
            cur.execute(
                f"SELECT COUNT(*) as cnt FROM {self._schema}.{table}"  # noqa: S608
            )
            count_row = cur.fetchone()
            return int(count_row["cnt"]) if count_row else 0

    def get_table_info(self, table: str) -> TableInfo:
        """Get complete information for a single table.

        Args:
            table: Table name

        Returns:
            TableInfo object with columns and row count
        """
        columns = self.get_columns(table)
        row_count = self.get_table_row_count(table)

        return TableInfo(
            name=table,
            columns=columns,
            row_count=row_count,
            schema=self._schema,
        )

    def get_schema_snapshot(self, database: str = "agentx") -> SchemaSnapshot:
        """Capture a complete schema snapshot.

        Creates a snapshot of the entire schema including all tables,
        columns, and foreign key relationships. This is used for
        SQL validation and hallucination detection.

        Args:
            database: Database name for the snapshot metadata

        Returns:
            SchemaSnapshot object containing all schema information

        Example:
            snapshot = inspector.get_schema_snapshot()
            if snapshot.has_table("users"):
                if snapshot.has_column("users", "email"):
                    print("Schema is valid")
        """
        logger.info(f"Capturing schema snapshot for {self._schema}")

        tables_dict: dict[str, TableInfo] = {}
        foreign_keys_dict: dict[str, list[ForeignKey]] = {}

        table_names = self.get_tables()

        for table_name in table_names:
            table_info = self.get_table_info(table_name)
            tables_dict[table_name] = table_info

            fks = self.get_foreign_keys(table_name)
            if fks:
                foreign_keys_dict[table_name] = fks

        snapshot = SchemaSnapshot(
            dialect="postgresql",
            database=database,
            tables=tables_dict,
            foreign_keys=foreign_keys_dict,
            captured_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Schema snapshot captured: {len(tables_dict)} tables, "
            f"{sum(len(fks) for fks in foreign_keys_dict.values())} foreign keys"
        )

        return snapshot

    def get_indexes(self, table: str) -> list[dict]:
        """Get index information for a table.

        Args:
            table: Table name

        Returns:
            List of dicts with index metadata
        """
        query = """
            SELECT
                i.relname AS index_name,
                am.amname AS index_type,
                idx.indisunique AS is_unique,
                idx.indisprimary AS is_primary,
                array_agg(a.attname ORDER BY k.ordinality) AS columns
            FROM pg_index idx
            JOIN pg_class i ON i.oid = idx.indexrelid
            JOIN pg_class t ON t.oid = idx.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_am am ON am.oid = i.relam
            CROSS JOIN LATERAL unnest(idx.indkey) WITH ORDINALITY AS k(attnum, ordinality)
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
            WHERE n.nspname = %s
              AND t.relname = %s
            GROUP BY i.relname, am.amname, idx.indisunique, idx.indisprimary
            ORDER BY i.relname
        """

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (self._schema, table))
            return list(cur.fetchall())
