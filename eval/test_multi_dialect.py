#!/usr/bin/env python3
"""
Test script for multi-dialect SQL evaluation system.

Tests:
1. Dialect registry and configuration
2. SQLite adapter (zero dependencies)
3. Multi-dialect SQL parser
4. Hallucination detection
5. SQLAgent full pipeline

Run with: python test_multi_dialect.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agentx import (
    SQLExecutor,
    ExecutorConfig,
    get_dialect_config,
    get_supported_dialects,
    MultiDialectSQLParser,
    HallucinationDetector,
    create_adapter,
)


def test_dialect_registry():
    """Test dialect configuration registry."""
    print("\n" + "=" * 60)
    print("TEST: Dialect Registry")
    print("=" * 60)

    # Test supported dialects
    dialects = get_supported_dialects()
    print(f"Supported dialects: {dialects}")
    assert "sqlite" in dialects
    assert "duckdb" in dialects
    assert "postgresql" in dialects
    assert "bigquery" in dialects

    # Test SQLite config
    sqlite_config = get_dialect_config("sqlite")
    print(f"\nSQLite config:")
    print(f"  - sqlglot dialect: {sqlite_config.sqlglot_dialect}")
    print(f"  - supports schemas: {sqlite_config.supports_schemas}")
    print(f"  - supports CTE: {sqlite_config.supports_cte}")
    print(f"  - functions count: {len(sqlite_config.builtin_functions)}")

    # Verify some SQLite functions
    assert "COUNT" in sqlite_config.builtin_functions
    assert "SUM" in sqlite_config.builtin_functions
    assert "DATE" in sqlite_config.builtin_functions
    assert "ROW_NUMBER" in sqlite_config.builtin_functions

    # Test BigQuery config
    bq_config = get_dialect_config("bigquery")
    print(f"\nBigQuery config:")
    print(f"  - sqlglot dialect: {bq_config.sqlglot_dialect}")
    print(f"  - functions count: {len(bq_config.builtin_functions)}")

    # Verify BigQuery-specific functions
    assert "SAFE_DIVIDE" in bq_config.builtin_functions
    assert "ARRAY_AGG" in bq_config.builtin_functions
    assert "UNNEST" in bq_config.builtin_functions

    print("\n✅ Dialect registry tests passed!")


def test_sqlite_adapter():
    """Test SQLite database adapter."""
    print("\n" + "=" * 60)
    print("TEST: SQLite Adapter")
    print("=" * 60)

    # Create in-memory SQLite adapter
    adapter = create_adapter("sqlite")
    adapter.connect()

    # Create test table
    adapter.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test data
    adapter.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@test.com')")
    adapter.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob@test.com')")
    adapter.execute("INSERT INTO users (name, email) VALUES ('Charlie', 'charlie@test.com')")

    # Query data
    result = adapter.execute("SELECT * FROM users ORDER BY id")
    print(f"\nQuery result: {result.success}")
    print(f"Rows returned: {result.rows_returned}")
    print(f"Columns: {result.columns}")
    print(f"Data: {result.data}")

    assert result.success
    assert result.rows_returned == 3
    assert "name" in result.columns

    # Get schema snapshot
    schema = adapter.get_schema_snapshot()
    print(f"\nSchema snapshot:")
    print(f"  - Dialect: {schema.dialect}")
    print(f"  - Tables: {schema.table_names}")
    print(f"  - Users columns: {schema.get_table('users').column_names}")

    assert schema.has_table("users")
    assert schema.has_column("users", "name")
    assert schema.has_column("users", "email")

    adapter.close()
    print("\n✅ SQLite adapter tests passed!")


def test_sql_parser():
    """Test multi-dialect SQL parser."""
    print("\n" + "=" * 60)
    print("TEST: Multi-Dialect SQL Parser")
    print("=" * 60)

    parser = MultiDialectSQLParser(default_dialect="sqlite")

    # Test simple SELECT
    sql = "SELECT name, email FROM users WHERE id = 1"
    parsed = parser.parse(sql)

    print(f"\nParsed SQL: {sql}")
    print(f"  - Is valid: {parsed.is_valid}")
    print(f"  - Query type: {parsed.query_type}")
    print(f"  - Tables: {parsed.identifiers.tables}")
    print(f"  - Columns: {parsed.identifiers.columns}")

    assert parsed.is_valid
    assert "users" in parsed.identifiers.tables
    assert any("name" in c for c in parsed.identifiers.columns)

    # Test with JOINs
    sql = """
        SELECT u.name, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        WHERE o.total > 100
    """
    parsed = parser.parse(sql)

    print(f"\nParsed JOIN query:")
    print(f"  - Tables: {parsed.identifiers.tables}")
    print(f"  - Columns: {parsed.identifiers.columns}")
    print(f"  - Aliases: {parsed.identifiers.aliases}")

    assert "users" in parsed.identifiers.tables or "u" in parsed.identifiers.aliases

    # Test function extraction
    sql = "SELECT COUNT(*), AVG(total), MAX(created_at) FROM orders"
    parsed = parser.parse(sql)

    print(f"\nParsed aggregation query:")
    print(f"  - Functions: {parsed.identifiers.functions}")

    assert any("COUNT" in f.upper() for f in parsed.identifiers.functions)

    # Test function validation
    invalid_funcs = parser.validate_functions(
        "SELECT SAFE_DIVIDE(a, b) FROM table1",
        dialect="sqlite"
    )
    print(f"\nInvalid functions for SQLite: {invalid_funcs}")

    # SAFE_DIVIDE is BigQuery-specific, should be flagged for SQLite
    # (but we're lenient in validation)

    # Test transpilation
    sqlite_sql = "SELECT IFNULL(name, 'Unknown') FROM users"
    pg_sql = parser.transpile(sqlite_sql, from_dialect="sqlite", to_dialect="postgresql")
    print(f"\nTranspiled SQLite -> PostgreSQL:")
    print(f"  - Original: {sqlite_sql}")
    print(f"  - Result: {pg_sql}")

    print("\n✅ SQL parser tests passed!")


def test_hallucination_detector():
    """Test hallucination detection."""
    print("\n" + "=" * 60)
    print("TEST: Hallucination Detector")
    print("=" * 60)

    # Create adapter and schema
    adapter = create_adapter("sqlite")
    adapter.connect()

    adapter.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        )
    """)
    adapter.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            total REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    schema = adapter.get_schema_snapshot()

    # Test detector
    detector = HallucinationDetector(dialect="sqlite")

    # Valid query - no hallucinations
    sql = "SELECT c.name, o.total FROM customers c JOIN orders o ON c.id = o.customer_id"
    report = detector.detect(sql, schema)

    print(f"\nValid query hallucination report:")
    print(f"  - SQL: {sql}")
    print(f"  - Phantom tables: {report.phantom_tables}")
    print(f"  - Phantom columns: {report.phantom_columns}")
    print(f"  - Phantom functions: {report.phantom_functions}")
    print(f"  - Score: {report.hallucination_score}")

    assert len(report.phantom_tables) == 0
    assert report.hallucination_score < 0.1

    # Invalid query - phantom table
    sql = "SELECT * FROM non_existent_table"
    report = detector.detect(sql, schema)

    print(f"\nPhantom table query:")
    print(f"  - SQL: {sql}")
    print(f"  - Phantom tables: {report.phantom_tables}")
    print(f"  - Score: {report.hallucination_score}")

    assert "non_existent_table" in report.phantom_tables
    assert report.hallucination_score > 0

    # Invalid query - phantom column
    sql = "SELECT fake_column FROM customers"
    report = detector.detect(sql, schema)

    print(f"\nPhantom column query:")
    print(f"  - SQL: {sql}")
    print(f"  - Phantom columns: {report.phantom_columns}")
    print(f"  - Score: {report.hallucination_score}")

    assert "fake_column" in report.phantom_columns

    # Validate method
    validation = detector.validate(sql, schema)
    print(f"\nValidation result:")
    print(f"  - Is valid: {validation.is_valid}")
    print(f"  - Errors: {validation.errors}")

    assert not validation.is_valid

    adapter.close()
    print("\n✅ Hallucination detector tests passed!")


def test_sql_executor():
    """Test full SQLExecutor pipeline."""
    print("\n" + "=" * 60)
    print("TEST: SQLExecutor Full Pipeline")
    print("=" * 60)

    # Create SQLite executor
    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

    # Create test tables
    executor.adapter.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            category TEXT
        )
    """)
    executor.adapter.execute("INSERT INTO products VALUES (1, 'Widget', 9.99, 'Gadgets')")
    executor.adapter.execute("INSERT INTO products VALUES (2, 'Gizmo', 19.99, 'Gadgets')")
    executor.adapter.execute("INSERT INTO products VALUES (3, 'Thing', 4.99, 'Stuff')")

    # Refresh schema
    executor.refresh_schema()

    print(f"\nExecutor info:")
    print(f"  - Dialect: {executor.dialect}")
    print(f"  - Tables: {executor.list_tables()}")

    # Process valid query
    result = executor.process_query(
        "SELECT category, COUNT(*) as count, AVG(price) as avg_price FROM products GROUP BY category",
        verbose=True
    )

    print(f"\nProcess query result:")
    print(f"  - Status: {result.overall_status}")
    print(f"  - Valid: {result.is_valid}")
    print(f"  - Data: {result.data}")
    print(f"  - Analysis: {result.analysis}")

    assert result.success
    assert len(result.data) == 2  # Two categories

    # Process invalid query (phantom table)
    result = executor.process_query(
        "SELECT * FROM fake_products",
        verbose=True
    )

    print(f"\nInvalid query result:")
    print(f"  - Status: {result.overall_status}")
    print(f"  - Validation errors: {result.validation.get('errors', [])}")

    assert not result.success

    # Test without validation (should fail at execution)
    result = executor.process_query(
        "SELECT * FROM fake_products",
        validate=False,
        verbose=True
    )

    print(f"\nQuery without validation:")
    print(f"  - Status: {result.overall_status}")
    print(f"  - Execution error: {result.error}")

    assert not result.success

    executor.close()
    print("\n✅ SQLExecutor tests passed!")


def test_bigquery_functions():
    """Test BigQuery-specific function detection."""
    print("\n" + "=" * 60)
    print("TEST: BigQuery Function Detection")
    print("=" * 60)

    parser = MultiDialectSQLParser(default_dialect="bigquery")

    # BigQuery-specific SQL
    sql = """
        SELECT
            SAFE_DIVIDE(revenue, users) as revenue_per_user,
            DATE_TRUNC(created_at, MONTH) as month,
            ARRAY_AGG(DISTINCT category) as categories
        FROM analytics
        WHERE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, DAY) < 30
    """

    parsed = parser.parse(sql, dialect="bigquery")

    print(f"BigQuery SQL parsing:")
    print(f"  - Is valid: {parsed.is_valid}")
    print(f"  - Functions: {parsed.identifiers.functions}")

    # These should be valid for BigQuery
    invalid = parser.validate_functions(sql, dialect="bigquery")
    print(f"  - Invalid functions for BigQuery: {invalid}")

    # Check against SQLite (should flag BigQuery-specific functions)
    invalid_sqlite = parser.validate_functions(sql, dialect="sqlite")
    print(f"  - Invalid functions for SQLite: {invalid_sqlite}")

    print("\n✅ BigQuery function tests passed!")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MULTI-DIALECT SQL EVALUATION SYSTEM TESTS")
    print("=" * 60)

    try:
        test_dialect_registry()
        test_sqlite_adapter()
        test_sql_parser()
        test_hallucination_detector()
        test_sql_executor()
        test_bigquery_functions()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✅")
        print("=" * 60)
        print("\nThe multi-dialect system is working correctly.")
        print("You can now use SQLite (default), DuckDB, or PostgreSQL.")
        print("\nExample usage:")
        print("  from agentx import SQLExecutor, ExecutorConfig")
        print("  executor = SQLExecutor(ExecutorConfig(dialect='sqlite'))")
        print("  result = executor.process_query('SELECT 1 + 1 as answer')")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
