"""
Hallucination Detector - Detects phantom identifiers in SQL queries.

Identifies:
- Phantom tables: Tables that don't exist in the schema
- Phantom columns: Columns that don't exist in any table
- Phantom functions: Functions not valid for the dialect
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any

from ..dialects import get_dialect_config
from ..infrastructure.models import SchemaSnapshot
from .sql_parser import MultiDialectSQLParser, IdentifierSet


@dataclass
class HallucinationReport:
    """
    Report of hallucinated (phantom) identifiers in SQL.

    Contains:
    - phantom_tables: Tables referenced that don't exist
    - phantom_columns: Columns referenced that don't exist
    - phantom_functions: Functions not valid for the dialect
    - hallucination_score: 0.0 (no hallucinations) to 1.0 (all phantom)
    """
    phantom_tables: List[str] = field(default_factory=list)
    phantom_columns: List[str] = field(default_factory=list)
    phantom_functions: List[str] = field(default_factory=list)
    dialect: str = ""
    hallucination_score: float = 0.0

    @property
    def total_hallucinations(self) -> int:
        """Total count of all phantom identifiers."""
        return (
            len(self.phantom_tables) +
            len(self.phantom_columns) +
            len(self.phantom_functions)
        )

    @property
    def has_hallucinations(self) -> bool:
        """Check if any hallucinations were detected."""
        return self.total_hallucinations > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phantom_tables": self.phantom_tables,
            "phantom_columns": self.phantom_columns,
            "phantom_functions": self.phantom_functions,
            "dialect": self.dialect,
            "hallucination_score": self.hallucination_score,
            "total_hallucinations": self.total_hallucinations,
        }


@dataclass
class ValidationResult:
    """
    Complete validation result for a SQL query.

    Contains:
    - is_valid: Whether the query is valid
    - errors: List of error messages
    - warnings: List of warning messages
    - hallucination_report: Detailed hallucination analysis
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hallucination_report: Optional[HallucinationReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "hallucination_report": (
                self.hallucination_report.to_dict()
                if self.hallucination_report else None
            ),
        }


class HallucinationDetector:
    """
    Dialect-aware hallucination detection for SQL queries.

    Detects phantom (non-existent) identifiers by comparing
    SQL query references against the actual database schema.
    """

    def __init__(self, dialect: str = "sqlite"):
        """
        Initialize the detector.

        Args:
            dialect: SQL dialect for function validation
        """
        self.dialect = dialect
        self.parser = MultiDialectSQLParser(default_dialect=dialect)

        try:
            self.config = get_dialect_config(dialect)
        except ValueError:
            self.config = None

    def detect(
        self,
        sql: str,
        schema: SchemaSnapshot,
        dialect: str = None
    ) -> HallucinationReport:
        """
        Detect hallucinated identifiers in SQL query.

        Args:
            sql: SQL query to analyze
            schema: Database schema for validation
            dialect: Override dialect (optional)

        Returns:
            HallucinationReport with phantom identifiers and score
        """
        dialect = dialect or self.dialect
        parsed = self.parser.parse(sql, dialect)

        if not parsed.is_valid:
            return HallucinationReport(
                dialect=dialect,
                hallucination_score=1.0,  # Can't validate, assume worst case
            )

        # Detect phantom tables
        phantom_tables = self._detect_phantom_tables(
            parsed.identifiers.tables,
            parsed.identifiers.aliases,
            schema
        )

        # Detect phantom columns
        phantom_columns = self._detect_phantom_columns(
            parsed.identifiers.columns,
            parsed.identifiers.tables,
            parsed.identifiers.aliases,
            schema,
            select_aliases=parsed.identifiers.select_aliases,
            cte_columns=parsed.identifiers.cte_columns
        )

        # Detect phantom functions (dialect-aware)
        phantom_functions = self._detect_phantom_functions(
            parsed.identifiers.functions,
            dialect
        )

        # Calculate hallucination score
        total_identifiers = (
            len(parsed.identifiers.tables) +
            len(parsed.identifiers.columns) +
            len(parsed.identifiers.functions)
        )
        total_phantoms = (
            len(phantom_tables) +
            len(phantom_columns) +
            len(phantom_functions)
        )

        score = total_phantoms / max(1, total_identifiers)

        return HallucinationReport(
            phantom_tables=phantom_tables,
            phantom_columns=phantom_columns,
            phantom_functions=phantom_functions,
            dialect=dialect,
            hallucination_score=round(score, 4),
        )

    def validate(
        self,
        sql: str,
        schema: SchemaSnapshot,
        dialect: str = None
    ) -> ValidationResult:
        """
        Validate SQL and return complete validation result.

        Convenience method that wraps detect() and formats results.

        Args:
            sql: SQL query to validate
            schema: Database schema for validation
            dialect: Override dialect (optional)

        Returns:
            ValidationResult with errors, warnings, and hallucination report
        """
        dialect = dialect or self.dialect
        report = self.detect(sql, schema, dialect)

        errors = []
        warnings = []

        # Convert phantom tables to errors
        for table in report.phantom_tables:
            errors.append(f"Table '{table}' does not exist in schema")

        # Convert phantom columns to errors
        for col in report.phantom_columns:
            errors.append(f"Column '{col}' does not exist")

        # Convert phantom functions to warnings (might be UDFs)
        for func in report.phantom_functions:
            warnings.append(
                f"Function '{func}' may not be valid for {dialect}"
            )

        return ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            hallucination_report=report,
        )

    def _detect_phantom_tables(
        self,
        tables: List[str],
        aliases: Dict[str, str],
        schema: SchemaSnapshot
    ) -> List[str]:
        """
        Find tables that don't exist in the schema.

        Handles:
        - Simple table names
        - Qualified names (schema.table, catalog.schema.table)
        - CTE and subquery aliases (not phantom)
        """
        phantom = []

        # Get alias names that represent CTEs/subqueries
        cte_aliases = {
            alias for alias, target in aliases.items()
            if target in {"(cte)", "(subquery)"}
        }

        for table in tables:
            # Skip CTE/subquery aliases
            if table in cte_aliases:
                continue

            # Handle qualified names
            table_name = table.split(".")[-1]

            # Check if table exists (case-insensitive)
            if not schema.has_table(table_name) and not schema.has_table(table):
                phantom.append(table)

        return phantom

    def _detect_phantom_columns(
        self,
        columns: List[str],
        tables: List[str],
        aliases: Dict[str, str],
        schema: SchemaSnapshot,
        select_aliases: Set[str] = None,
        cte_columns: Dict[str, Set[str]] = None
    ) -> List[str]:
        """
        Find columns that don't exist in any referenced table.

        Handles:
        - Unqualified column names (checks all tables)
        - Qualified names (table.column)
        - Alias-qualified names (alias.column)
        - SELECT aliases (e.g., COUNT(*) as total -> total is valid)
        - CTE columns (columns defined in WITH clauses)
        """
        phantom = []
        select_aliases = select_aliases or set()
        cte_columns = cte_columns or {}

        # Build set of valid columns from all referenced tables
        valid_columns: Set[str] = set()
        valid_qualified: Set[str] = set()

        # Add SELECT aliases as valid columns
        valid_columns.update(select_aliases)

        # Add CTE columns as valid
        for cte_name, cte_cols in cte_columns.items():
            valid_columns.update(cte_cols)
            # Also add qualified versions (cte_name.column)
            for col in cte_cols:
                valid_qualified.add(f"{cte_name}.{col}")

        # Add columns from explicitly referenced tables
        for table in tables:
            table_name = table.split(".")[-1]
            table_info = schema.get_table(table_name) or schema.get_table(table)

            if table_info:
                for col in table_info.columns:
                    col_lower = col.name.lower()
                    valid_columns.add(col_lower)
                    valid_qualified.add(f"{table_name.lower()}.{col_lower}")

                    # Also add alias-qualified columns
                    for alias, target in aliases.items():
                        if target == table_name or target == table:
                            valid_qualified.add(f"{alias.lower()}.{col_lower}")

        # Also add columns from aliased tables
        for alias, actual in aliases.items():
            alias_lower = alias.lower()

            if actual in {"(cte)", "(subquery)"}:
                # For CTEs and subqueries, use the cte_columns if available
                if alias_lower in cte_columns:
                    for col in cte_columns[alias_lower]:
                        valid_qualified.add(f"{alias_lower}.{col}")
                continue

            actual_table = schema.get_table(actual)
            if actual_table:
                for col in actual_table.columns:
                    col_lower = col.name.lower()
                    valid_columns.add(col_lower)
                    valid_qualified.add(f"{alias_lower}.{col_lower}")

        # Check each column
        for col in columns:
            col_lower = col.lower()
            col_name_only = col.split(".")[-1].lower()

            # Skip if it's a SELECT alias
            if col_lower in select_aliases:
                continue

            # Skip if it's a valid qualified column
            if col_lower in valid_qualified:
                continue

            # Skip if it's an unqualified column that exists somewhere
            if "." not in col and col_lower in valid_columns:
                continue

            # Handle qualified columns
            if "." in col:
                parts = col.split(".")
                table_part = parts[0].lower()
                col_part = parts[-1].lower()

                # Check if it's a CTE/subquery column reference
                if table_part in cte_columns:
                    if col_part in cte_columns[table_part]:
                        continue

                # Check if it's an alias
                if table_part in {a.lower() for a in aliases}:
                    actual = None
                    for a, t in aliases.items():
                        if a.lower() == table_part:
                            actual = t
                            break

                    # For CTEs/subqueries, check if column is in cte_columns
                    if actual in {"(cte)", "(subquery)"}:
                        if table_part in cte_columns and col_part in cte_columns[table_part]:
                            continue
                        # If we don't know the CTE columns, assume it's valid
                        # (better to have false negatives than false positives)
                        if table_part not in cte_columns:
                            continue

                # Check if the column exists in any table
                found_in_any = False
                for table_info in schema.tables.values():
                    if any(c.name.lower() == col_part for c in table_info.columns):
                        found_in_any = True
                        break

                # Also check if it's a SELECT alias or CTE column
                if col_part in select_aliases or col_part in valid_columns:
                    found_in_any = True

                if not found_in_any:
                    phantom.append(col)
            else:
                # Unqualified column not found anywhere
                # Check across all schema tables
                found_anywhere = False
                for table_info in schema.tables.values():
                    if any(c.name.lower() == col_name_only for c in table_info.columns):
                        found_anywhere = True
                        break

                if not found_anywhere:
                    phantom.append(col)

        return phantom

    def _detect_phantom_functions(
        self,
        functions: List[str],
        dialect: str
    ) -> List[str]:
        """
        Find functions that aren't valid for the dialect.

        Note: This is advisory - functions might be UDFs.
        """
        phantom = []

        try:
            config = get_dialect_config(dialect)
            valid_functions = config.builtin_functions
        except ValueError:
            return []  # Unknown dialect, skip validation

        # Common AST artifacts to skip
        skip_names = {
            "ANONYMOUS", "PAREN", "BRACKET", "SUBQUERY",
            "PLACEHOLDER", "LITERAL", "STAR"
        }

        for func in functions:
            func_upper = func.upper()

            # Skip AST artifacts
            if func_upper in skip_names:
                continue

            # Check if valid
            if func_upper not in valid_functions:
                # Also check common aliases
                if not self._is_function_alias(func_upper, valid_functions):
                    phantom.append(func)

        return phantom

    def _is_function_alias(
        self,
        func: str,
        valid_functions: Set[str]
    ) -> bool:
        """Check if function is a known alias of a valid function."""
        # Common function aliases across dialects
        aliases = {
            "LEN": {"LENGTH"},
            "SUBSTR": {"SUBSTRING"},
            "CHARINDEX": {"POSITION", "INSTR"},
            "ISNULL": {"IFNULL", "COALESCE", "NVL"},
            "NVL": {"IFNULL", "COALESCE"},
            "GETDATE": {"NOW", "CURRENT_TIMESTAMP"},
            "DATEPART": {"EXTRACT", "DATE_PART"},
            "DATEDIFF": {"DATE_DIFF", "TIMESTAMPDIFF"},
            "DATEADD": {"DATE_ADD", "TIMESTAMPADD"},
            "INT": {"INTEGER", "CAST"},
            "VARCHAR": {"TEXT", "STRING"},
        }

        if func in aliases:
            return any(alias in valid_functions for alias in aliases[func])

        return False
