"""
Multi-dialect SQL parser using sqlglot.

Supports parsing and identifier extraction for:
- SQLite
- DuckDB
- PostgreSQL
- BigQuery
- Snowflake
- MySQL
"""

import sqlglot
from sqlglot import exp
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..dialects import get_dialect_config


@dataclass
class IdentifierSet:
    """Extracted SQL identifiers from a query."""
    tables: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    aliases: Dict[str, str] = field(default_factory=dict)  # alias -> actual name
    select_aliases: Set[str] = field(default_factory=set)  # aliases defined in SELECT
    cte_columns: Dict[str, Set[str]] = field(default_factory=dict)  # CTE name -> its columns

    def __post_init__(self):
        # Deduplicate while preserving order
        self.tables = list(dict.fromkeys(self.tables))
        self.columns = list(dict.fromkeys(self.columns))
        self.functions = list(dict.fromkeys(self.functions))


@dataclass
class ParsedSQL:
    """Result of parsing a SQL query."""
    ast: Any  # sqlglot AST
    dialect: str
    identifiers: IdentifierSet
    raw_sql: str
    is_valid: bool = True
    parse_error: Optional[str] = None

    @property
    def query_type(self) -> str:
        """Get the type of query (SELECT, INSERT, etc.)."""
        if self.ast is None:
            return "UNKNOWN"
        return type(self.ast).__name__.upper()

    @property
    def is_select(self) -> bool:
        """Check if query is a SELECT statement."""
        return isinstance(self.ast, exp.Select)


class MultiDialectSQLParser:
    """
    SQL parser that handles multiple dialects using sqlglot.

    Features:
    - Multi-dialect parsing (SQLite, DuckDB, PostgreSQL, BigQuery, etc.)
    - Identifier extraction (tables, columns, functions)
    - Alias resolution
    - Transpilation between dialects
    """

    def __init__(self, default_dialect: str = "sqlite"):
        """
        Initialize the parser.

        Args:
            default_dialect: Default dialect to use when not specified
        """
        self.default_dialect = default_dialect

    def parse(self, sql: str, dialect: str = None) -> ParsedSQL:
        """
        Parse SQL for the specified dialect.

        Args:
            sql: SQL query string
            dialect: SQL dialect (sqlite, duckdb, postgresql, bigquery, etc.)

        Returns:
            ParsedSQL object with AST and extracted identifiers
        """
        dialect = dialect or self.default_dialect

        try:
            config = get_dialect_config(dialect)
            sqlglot_dialect = config.sqlglot_dialect
        except ValueError:
            sqlglot_dialect = dialect

        try:
            ast = sqlglot.parse_one(sql, read=sqlglot_dialect)
            identifiers = self._extract_identifiers(ast)

            return ParsedSQL(
                ast=ast,
                dialect=dialect,
                identifiers=identifiers,
                raw_sql=sql,
                is_valid=True,
            )

        except sqlglot.errors.ParseError as e:
            # Try with fallback dialects
            ast, fallback_dialect = self._parse_with_fallback(sql, dialect)

            if ast:
                identifiers = self._extract_identifiers(ast)
                return ParsedSQL(
                    ast=ast,
                    dialect=fallback_dialect or dialect,
                    identifiers=identifiers,
                    raw_sql=sql,
                    is_valid=True,
                )

            # Complete parse failure
            return ParsedSQL(
                ast=None,
                dialect=dialect,
                identifiers=IdentifierSet(),
                raw_sql=sql,
                is_valid=False,
                parse_error=str(e),
            )

        except Exception as e:
            return ParsedSQL(
                ast=None,
                dialect=dialect,
                identifiers=IdentifierSet(),
                raw_sql=sql,
                is_valid=False,
                parse_error=str(e),
            )

    def _parse_with_fallback(
        self,
        sql: str,
        primary_dialect: str
    ) -> tuple:
        """
        Try parsing with multiple dialects if primary fails.

        Returns:
            Tuple of (ast, dialect_used) or (None, None) if all fail
        """
        fallback_order = ["sqlite", "postgres", "duckdb", "bigquery", None]

        for fallback in fallback_order:
            if fallback == primary_dialect:
                continue

            try:
                ast = sqlglot.parse_one(sql, read=fallback)
                return (ast, fallback)
            except:
                continue

        # Last resort: parse with error recovery
        try:
            ast = sqlglot.parse_one(
                sql,
                error_level=sqlglot.ErrorLevel.IGNORE
            )
            return (ast, primary_dialect)
        except:
            return (None, None)

    def _extract_identifiers(self, ast: Any) -> IdentifierSet:
        """
        Extract all identifiers from the AST.

        Extracts:
        - Table names (including qualified names like schema.table)
        - Column names (including qualified names like table.column)
        - Function names
        - Table aliases
        - SELECT aliases (column aliases defined in SELECT)
        - CTE columns (columns defined in CTEs)
        """
        tables = []
        columns = []
        functions = []
        aliases = {}
        select_aliases: Set[str] = set()
        cte_columns: Dict[str, Set[str]] = {}

        if ast is None:
            return IdentifierSet()

        # Extract CTEs first - we need their column definitions
        for cte in ast.find_all(exp.CTE):
            cte_name = None
            if hasattr(cte, 'alias') and cte.alias:
                cte_name = cte.alias
                aliases[cte.alias] = "(cte)"

            # Extract columns defined in this CTE
            if cte_name:
                cte_cols = self._extract_cte_columns(cte)
                if cte_cols:
                    cte_columns[cte_name.lower()] = cte_cols

        # Extract SELECT aliases from all SELECT statements (including subqueries)
        for select in ast.find_all(exp.Select):
            sel_aliases = self._extract_select_aliases(select)
            select_aliases.update(sel_aliases)

        # Extract tables
        for table in ast.find_all(exp.Table):
            name = table.name
            if table.db:
                name = f"{table.db}.{name}"
            if table.catalog:
                name = f"{table.catalog}.{name}"
            if name:
                tables.append(name)

            # Track table aliases
            if table.alias:
                aliases[table.alias] = table.name

        # Extract columns
        for col in ast.find_all(exp.Column):
            name = col.name
            if col.table:
                name = f"{col.table}.{name}"
            if name:
                columns.append(name)

        # Extract functions
        for func in ast.find_all(exp.Func):
            func_name = self._get_function_name(func)
            if func_name:
                functions.append(func_name)

        # Extract aliases from subqueries
        for subquery in ast.find_all(exp.Subquery):
            if subquery.alias:
                aliases[subquery.alias] = "(subquery)"
                # Also extract columns from subquery
                subq_cols = self._extract_subquery_columns(subquery)
                if subq_cols:
                    cte_columns[subquery.alias.lower()] = subq_cols

        return IdentifierSet(
            tables=tables,
            columns=columns,
            functions=functions,
            aliases=aliases,
            select_aliases=select_aliases,
            cte_columns=cte_columns,
        )

    def _extract_select_aliases(self, select: exp.Select) -> Set[str]:
        """Extract column aliases defined in a SELECT clause."""
        aliases = set()

        if not select.expressions:
            return aliases

        for expr in select.expressions:
            # Check if this expression has an alias
            if isinstance(expr, exp.Alias):
                alias_name = expr.alias
                if alias_name:
                    aliases.add(alias_name.lower())
            elif hasattr(expr, 'alias') and expr.alias:
                aliases.add(expr.alias.lower())

        return aliases

    def _extract_cte_columns(self, cte: exp.CTE) -> Set[str]:
        """Extract column names defined in a CTE."""
        columns = set()

        # Get the CTE's SELECT statement
        cte_query = cte.this
        if cte_query is None:
            return columns

        # Handle the case where cte.this is a Select or has a Select within it
        select = None
        if isinstance(cte_query, exp.Select):
            select = cte_query
        else:
            # Try to find a Select within the CTE
            selects = list(cte_query.find_all(exp.Select))
            if selects:
                select = selects[0]

        if select and select.expressions:
            for expr in select.expressions:
                col_name = self._get_expression_output_name(expr)
                if col_name:
                    columns.add(col_name.lower())

        return columns

    def _extract_subquery_columns(self, subquery: exp.Subquery) -> Set[str]:
        """Extract column names from a subquery's SELECT."""
        columns = set()

        # Get the subquery's SELECT
        inner = subquery.this
        if isinstance(inner, exp.Select) and inner.expressions:
            for expr in inner.expressions:
                col_name = self._get_expression_output_name(expr)
                if col_name:
                    columns.add(col_name.lower())

        return columns

    def _get_expression_output_name(self, expr: Any) -> Optional[str]:
        """Get the output column name for an expression."""
        # If it's an alias, return the alias name
        if isinstance(expr, exp.Alias):
            return expr.alias

        # If it has an alias attribute
        if hasattr(expr, 'alias') and expr.alias:
            return expr.alias

        # If it's a column reference, return the column name
        if isinstance(expr, exp.Column):
            return expr.name

        # For other expressions, try to get output_name
        if hasattr(expr, 'output_name'):
            return expr.output_name

        return None

    def _get_function_name(self, func: exp.Func) -> str:
        """Get the name of a function from AST node."""
        # Try to get the SQL name
        if hasattr(func, 'sql_name'):
            try:
                return func.sql_name().upper()
            except:
                pass

        # Fall back to class name
        class_name = type(func).__name__

        # Handle common function class names
        name_mapping = {
            "Anonymous": "ANONYMOUS",
            "Count": "COUNT",
            "Sum": "SUM",
            "Avg": "AVG",
            "Min": "MIN",
            "Max": "MAX",
            "Coalesce": "COALESCE",
            "If": "IF",
            "Case": "CASE",
            "Cast": "CAST",
            "Concat": "CONCAT",
            "Substring": "SUBSTRING",
            "Length": "LENGTH",
            "Upper": "UPPER",
            "Lower": "LOWER",
            "Trim": "TRIM",
            "Round": "ROUND",
            "Abs": "ABS",
            "Floor": "FLOOR",
            "Ceil": "CEIL",
            "DateDiff": "DATEDIFF",
            "DateAdd": "DATEADD",
            "CurrentDate": "CURRENT_DATE",
            "CurrentTimestamp": "CURRENT_TIMESTAMP",
        }

        return name_mapping.get(class_name, class_name.upper())

    def validate_functions(
        self,
        sql: str,
        dialect: str = None
    ) -> List[str]:
        """
        Check if functions in SQL are valid for the dialect.

        Args:
            sql: SQL query string
            dialect: SQL dialect

        Returns:
            List of invalid function names
        """
        dialect = dialect or self.default_dialect
        parsed = self.parse(sql, dialect)

        if not parsed.is_valid:
            return []

        try:
            config = get_dialect_config(dialect)
            valid_functions = config.builtin_functions
        except ValueError:
            return []  # Unknown dialect, skip validation

        invalid = []
        for func in parsed.identifiers.functions:
            func_upper = func.upper()
            # Skip common AST artifacts
            if func_upper in {"ANONYMOUS", "PAREN", "BRACKET", "SUBQUERY"}:
                continue
            if func_upper not in valid_functions:
                invalid.append(func)

        return invalid

    def transpile(
        self,
        sql: str,
        from_dialect: str,
        to_dialect: str,
        pretty: bool = True
    ) -> str:
        """
        Convert SQL from one dialect to another.

        Args:
            sql: Source SQL query
            from_dialect: Source dialect
            to_dialect: Target dialect
            pretty: Whether to format the output

        Returns:
            Transpiled SQL string
        """
        try:
            from_config = get_dialect_config(from_dialect)
            to_config = get_dialect_config(to_dialect)

            result = sqlglot.transpile(
                sql,
                read=from_config.sqlglot_dialect,
                write=to_config.sqlglot_dialect,
                pretty=pretty,
            )

            return result[0] if result else sql

        except Exception as e:
            # If transpilation fails, return original SQL
            return sql

    def extract_tables(self, sql: str, dialect: str = None) -> List[str]:
        """Extract table names from SQL query."""
        parsed = self.parse(sql, dialect)
        return parsed.identifiers.tables

    def extract_columns(self, sql: str, dialect: str = None) -> List[str]:
        """Extract column names from SQL query."""
        parsed = self.parse(sql, dialect)
        return parsed.identifiers.columns

    def get_query_type(self, sql: str, dialect: str = None) -> str:
        """Get the type of SQL query (SELECT, INSERT, etc.)."""
        parsed = self.parse(sql, dialect)
        return parsed.query_type
