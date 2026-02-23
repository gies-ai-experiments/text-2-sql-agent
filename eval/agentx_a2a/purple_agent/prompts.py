"""
SQL Generation Prompts for the Purple Agent.

Contains prompt templates for generating SQL queries from natural language.
"""

from typing import Any, Dict, List


class SQLPromptBuilder:
    """Builds prompts for SQL generation."""

    SYSTEM_PROMPT = """You are an expert SQL developer. Your task is to generate valid SQL queries based on natural language questions and database schemas.

Guidelines:
- Generate ONLY the SQL query, no explanations
- Use proper SQL syntax for the specified dialect
- Be precise with column and table names from the schema
- Use appropriate JOINs when multiple tables are needed
- Handle NULL values appropriately
- Use aliases for readability in complex queries
- Avoid SELECT * - specify columns explicitly when possible
- Add appropriate LIMIT clauses for potentially large result sets"""

    @staticmethod
    def build_prompt(
        question: str,
        schema: Dict[str, Any],
        dialect: str = "sqlite",
    ) -> str:
        """
        Build a prompt for SQL generation.

        Args:
            question: Natural language question
            schema: Database schema information
            dialect: SQL dialect (sqlite, postgresql, etc.)

        Returns:
            Complete prompt string
        """
        schema_str = SQLPromptBuilder._format_schema(schema)

        prompt = f"""Database Schema:
{schema_str}

SQL Dialect: {dialect}

Question: {question}

Generate a SQL query to answer this question. Return ONLY the SQL query, nothing else."""

        return prompt

    @staticmethod
    def _format_schema(schema: Dict[str, Any]) -> str:
        """Format schema dictionary into readable string."""
        if not schema:
            return "No schema provided"

        lines = []

        # Handle different schema formats
        if "tables" in schema:
            # Format: {"tables": {"table_name": {"columns": [...]}}}
            for table_name, table_info in schema.get("tables", {}).items():
                columns = table_info.get("columns", [])
                if isinstance(columns, list):
                    if columns and isinstance(columns[0], dict):
                        # Format: [{"name": "col", "type": "INT"}]
                        col_strs = [
                            f"  - {c.get('name', 'unknown')}: {c.get('type', 'unknown')}"
                            for c in columns
                        ]
                    else:
                        # Format: ["col1", "col2"]
                        col_strs = [f"  - {c}" for c in columns]
                else:
                    col_strs = [f"  - {columns}"]

                lines.append(f"Table: {table_name}")
                lines.extend(col_strs)
                lines.append("")

        elif isinstance(schema, dict):
            # Simple format: {"table_name": ["col1", "col2"]}
            for table_name, columns in schema.items():
                if isinstance(columns, list):
                    col_strs = [f"  - {c}" for c in columns]
                else:
                    col_strs = [f"  - {columns}"]

                lines.append(f"Table: {table_name}")
                lines.extend(col_strs)
                lines.append("")

        return "\n".join(lines) if lines else str(schema)

    @staticmethod
    def build_chat_messages(
        question: str,
        schema: Dict[str, Any],
        dialect: str = "sqlite",
    ) -> List[Dict[str, str]]:
        """
        Build chat messages for chat-based LLM APIs.

        Args:
            question: Natural language question
            schema: Database schema information
            dialect: SQL dialect

        Returns:
            List of chat messages
        """
        user_prompt = SQLPromptBuilder.build_prompt(question, schema, dialect)

        return [
            {"role": "system", "content": SQLPromptBuilder.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
