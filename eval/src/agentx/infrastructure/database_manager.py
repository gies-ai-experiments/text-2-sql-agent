"""Database connection manager using psycopg3 connection pooling.

Provides zero-ORM PostgreSQL connectivity with connection pooling,
transaction management, and raw SQL execution.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connections using psycopg3 connection pool.

    This class provides:
    - Connection pooling with configurable min/max size
    - Context manager for transactional operations
    - Raw SQL execution with parameterized queries
    - Health checks and connection validation

    Example:
        db = DatabaseManager("postgresql://user:pass@localhost/db")
        db.open()
        try:
            result = db.execute("SELECT * FROM users WHERE id = %s", (1,))
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO logs (msg) VALUES (%s)", ("test",))
                conn.commit()
        finally:
            db.close()
    """

    def __init__(
        self,
        database_url: str,
        pool_min_size: int = 2,
        pool_max_size: int = 10,
        pool_timeout: float = 30.0,
    ):
        """Initialize the database manager.

        Args:
            database_url: PostgreSQL connection URL
            pool_min_size: Minimum number of connections in the pool
            pool_max_size: Maximum number of connections in the pool
            pool_timeout: Timeout in seconds for acquiring a connection
        """
        self._database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._pool_timeout = pool_timeout
        self._pool: ConnectionPool | None = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        """Check if the connection pool is open."""
        return self._is_open and self._pool is not None

    def open(self) -> None:
        """Open the connection pool.

        Creates the connection pool and validates connectivity.

        Raises:
            OperationalError: If connection to the database fails
        """
        if self._is_open:
            logger.warning("Connection pool is already open")
            return

        logger.info(f"Opening connection pool (min={self._pool_min_size}, max={self._pool_max_size})")

        self._pool = ConnectionPool(
            conninfo=self._database_url,
            min_size=self._pool_min_size,
            max_size=self._pool_max_size,
            timeout=self._pool_timeout,
            open=True,
            configure=self._configure_connection,
        )

        # Validate connectivity
        try:
            with self._pool.connection() as conn:
                conn.execute("SELECT 1")
            self._is_open = True
            logger.info("Connection pool opened successfully")
        except Exception as e:
            self._pool.close()
            self._pool = None
            logger.error(f"Failed to validate connection: {e}")
            raise

    def close(self) -> None:
        """Close the connection pool.

        Gracefully closes all connections in the pool.
        """
        if self._pool is not None:
            logger.info("Closing connection pool")
            self._pool.close()
            self._pool = None
        self._is_open = False

    def _configure_connection(self, conn: Connection) -> None:
        """Configure new connections.

        Called by the pool when creating new connections.

        Args:
            conn: The connection to configure
        """
        # Set autocommit to False for explicit transaction control
        conn.autocommit = False

    def _ensure_open(self) -> None:
        """Ensure the connection pool is open.

        Raises:
            RuntimeError: If the pool is not open
        """
        if not self.is_open or self._pool is None:
            raise RuntimeError(
                "Connection pool is not open. Call open() first."
            )

    @contextmanager
    def connection(self) -> Generator[Connection, None, None]:
        """Get a connection from the pool.

        Provides a context manager that automatically returns the
        connection to the pool when done. The connection is set up
        for explicit transaction control (autocommit=False).

        Yields:
            A psycopg Connection object

        Raises:
            RuntimeError: If the pool is not open
            OperationalError: If unable to acquire a connection

        Example:
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users")
                    rows = cur.fetchall()
                conn.commit()
        """
        self._ensure_open()
        assert self._pool is not None

        with self._pool.connection() as conn:
            yield conn

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
        *,
        fetch: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute a SQL query and return results as dictionaries.

        This is a convenience method for simple queries. For complex
        transactions, use the connection() context manager directly.

        Args:
            sql: SQL query string (use %s for parameters)
            params: Query parameters (tuple or dict)
            fetch: If True, fetch and return results. If False, return empty list.

        Returns:
            List of dictionaries representing the result rows

        Raises:
            RuntimeError: If the pool is not open
            Exception: Database errors are propagated

        Example:
            users = db.execute("SELECT * FROM users WHERE active = %s", (True,))
            db.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (1,), fetch=False)
        """
        self._ensure_open()
        assert self._pool is not None

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                if fetch and cur.description is not None:
                    result = list(cur.fetchall())
                else:
                    result = []
                conn.commit()
                return result

    def execute_many(
        self,
        sql: str,
        params_seq: list[tuple[Any, ...]] | list[dict[str, Any]],
    ) -> int:
        """Execute a SQL query multiple times with different parameters.

        Uses executemany for efficient batch operations.

        Args:
            sql: SQL query string (use %s for parameters)
            params_seq: Sequence of parameter tuples or dicts

        Returns:
            Total number of affected rows

        Raises:
            RuntimeError: If the pool is not open

        Example:
            db.execute_many(
                "INSERT INTO users (name, email) VALUES (%s, %s)",
                [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]
            )
        """
        self._ensure_open()
        assert self._pool is not None

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, params_seq)
                rowcount = cur.rowcount or 0
                conn.commit()
                return rowcount

    def check_health(self) -> bool:
        """Check if the database connection is healthy.

        Returns:
            True if the connection is healthy, False otherwise
        """
        if not self.is_open:
            return False

        try:
            self.execute("SELECT 1", fetch=True)
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        if self._pool is None:
            return {"status": "closed"}

        return {
            "status": "open",
            "min_size": self._pool.min_size,
            "max_size": self._pool.max_size,
            "size": self._pool.get_stats().get("pool_size", 0),
            "available": self._pool.get_stats().get("pool_available", 0),
            "waiting": self._pool.get_stats().get("requests_waiting", 0),
        }

    def __enter__(self) -> DatabaseManager:
        """Context manager entry - opens the pool."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes the pool."""
        self.close()
