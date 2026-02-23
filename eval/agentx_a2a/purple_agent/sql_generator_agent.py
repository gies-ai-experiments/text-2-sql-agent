"""
Sample SQL Generator Agent (Purple Agent).

A sample Purple Agent that generates SQL queries using LLMs for testing
with the AgentX Green Agent benchmark.
"""

import os
import re
from typing import Any, Dict, Optional

from .prompts import SQLPromptBuilder


class LLMClient:
    """
    Simple LLM client supporting Gemini and OpenAI.

    Usage:
        client = LLMClient(provider="gemini")  # or "openai"
        response = await client.generate(prompt)
    """

    def __init__(
        self,
        provider: str = "gemini",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize LLM client.

        Args:
            provider: LLM provider ("gemini" or "openai")
            model: Model name (defaults to provider's default)
            api_key: API key (defaults to env variable)
        """
        self.provider = provider.lower()

        if self.provider == "gemini":
            self.model = model or "gemini-3-flash-preview"
            self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        elif self.provider == "openai":
            self.model = model or "gpt-4o-mini"
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self._client = None

    def _get_client(self):
        """Lazy-load the appropriate client."""
        if self._client is not None:
            return self._client

        if self.provider == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError("Install google-generativeai: pip install google-generativeai")

        elif self.provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("Install openai: pip install openai")

        return self._client

    async def generate(self, prompt: str) -> str:
        """
        Generate response from LLM.

        Args:
            prompt: Input prompt

        Returns:
            Generated text response
        """
        client = self._get_client()

        if self.provider == "gemini":
            response = client.generate_content(prompt)
            return response.text

        elif self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return response.choices[0].message.content

        return ""

    def generate_sync(self, prompt: str) -> str:
        """
        Synchronous version of generate.

        Args:
            prompt: Input prompt

        Returns:
            Generated text response
        """
        client = self._get_client()

        if self.provider == "gemini":
            response = client.generate_content(prompt)
            return response.text

        elif self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return response.choices[0].message.content

        return ""


class SampleSQLAgent:
    """
    Sample Purple Agent that generates SQL using an LLM.

    This agent receives natural language questions and database schemas,
    and generates SQL queries using LLM inference.
    """

    def __init__(
        self,
        llm_provider: str = "gemini",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the SQL agent.

        Args:
            llm_provider: LLM provider ("gemini" or "openai")
            model: Model name (optional, uses provider default)
            api_key: API key (optional, uses env variable)
        """
        self.llm = LLMClient(
            provider=llm_provider,
            model=model,
            api_key=api_key,
        )
        self.prompt_builder = SQLPromptBuilder()

    async def handle_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a SQL generation task from the Green Agent.

        Args:
            task: Task payload containing:
                - question: Natural language question
                - schema: Database schema information
                - dialect: SQL dialect (sqlite, postgresql, etc.)
                - task_id: Task identifier (optional)

        Returns:
            Response containing:
                - sql: Generated SQL query
                - reasoning: Optional explanation
                - task_id: Echo of task_id if provided
        """
        question = task.get("question", "")
        schema = task.get("schema", {})
        dialect = task.get("dialect", "sqlite")
        task_id = task.get("task_id")

        if not question:
            return {
                "sql": "",
                "error": "No question provided",
                "task_id": task_id,
            }

        try:
            # Build prompt
            prompt = self.prompt_builder.build_prompt(question, schema, dialect)

            # Generate SQL
            response = await self.llm.generate(prompt)

            # Extract SQL from response
            sql = self._extract_sql(response)

            return {
                "sql": sql,
                "reasoning": response,
                "task_id": task_id,
            }

        except Exception as e:
            return {
                "sql": "",
                "error": str(e),
                "task_id": task_id,
            }

    def handle_task_sync(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous version of handle_task.

        Args:
            task: Task payload

        Returns:
            Response with generated SQL
        """
        question = task.get("question", "")
        schema = task.get("schema", {})
        dialect = task.get("dialect", "sqlite")
        task_id = task.get("task_id")

        if not question:
            return {
                "sql": "",
                "error": "No question provided",
                "task_id": task_id,
            }

        try:
            # Build prompt
            prompt = self.prompt_builder.build_prompt(question, schema, dialect)

            # Generate SQL
            response = self.llm.generate_sync(prompt)

            # Extract SQL from response
            sql = self._extract_sql(response)

            return {
                "sql": sql,
                "reasoning": response,
                "task_id": task_id,
            }

        except Exception as e:
            return {
                "sql": "",
                "error": str(e),
                "task_id": task_id,
            }

    def _extract_sql(self, response: str) -> str:
        """
        Extract SQL query from LLM response.

        Handles various response formats:
        - Plain SQL
        - SQL in code blocks (```sql ... ```)
        - SQL with explanations

        Args:
            response: Raw LLM response

        Returns:
            Extracted SQL query
        """
        if not response:
            return ""

        # Try to extract from code block
        code_block_pattern = r"```(?:sql)?\s*([\s\S]*?)```"
        matches = re.findall(code_block_pattern, response, re.IGNORECASE)
        if matches:
            return matches[0].strip()

        # Try to find SQL statement
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "CREATE"]
        lines = response.strip().split("\n")

        sql_lines = []
        in_sql = False

        for line in lines:
            line_upper = line.strip().upper()

            # Start of SQL
            if any(line_upper.startswith(kw) for kw in sql_keywords):
                in_sql = True

            if in_sql:
                # Stop at explanatory text
                if line.strip().startswith("This") or line.strip().startswith("Note:"):
                    break
                sql_lines.append(line)

                # Check for statement end
                if line.strip().endswith(";"):
                    break

        if sql_lines:
            sql = "\n".join(sql_lines).strip()
            # Remove trailing semicolon if present (for consistency)
            if sql.endswith(";"):
                sql = sql[:-1].strip()
            return sql

        # Fallback: return entire response (might be just SQL)
        return response.strip()
