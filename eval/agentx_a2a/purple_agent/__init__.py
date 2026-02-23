"""
AgentX Purple Agent - Sample LLM-based SQL Generator.

This module implements a sample Purple Agent that generates SQL queries
using LLMs (Gemini or OpenAI) for testing with the AgentX Green Agent.
"""

from .sql_generator_agent import SampleSQLAgent
from .prompts import SQLPromptBuilder

__all__ = [
    "SampleSQLAgent",
    "SQLPromptBuilder",
]
