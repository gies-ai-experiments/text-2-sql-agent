# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Text-2-SQL Agent is a multi-dialect SQL evaluation framework for LLM-powered SQL agents. It provides hallucination detection, multi-dimensional scoring, and an A2A (Agent-to-Agent) REST API interface.

## Common Commands

### Setup
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running Tests
```bash
# All test files (run individually)
python test_multi_dialect.py        # Multi-dialect support tests
python test_enhanced_scoring.py     # Scoring component tests
python test_evaluation_pipeline.py  # Integration tests
python test_a2a.py                  # A2A interface tests
```

### Running the A2A Server
```bash
python -m a2a.server                           # SQLite, port 5000
python -m a2a.server --dialect postgresql --port 8080
```

### Running Evaluation Pipeline
```bash
python run_evaluation_pipeline.py "SELECT * FROM users"
python run_evaluation_pipeline.py "SELECT * FROM users" --dialect duckdb
```

### Running Benchmarks
```bash
python run_benchmark.py --output results/
python run_benchmark.py --difficulty easy,medium --output results/
python run_benchmark.py --schema enterprise --output results/  # Enterprise benchmark
```

### Docker
```bash
docker-compose up agentx          # SQLite on port 5000
docker-compose up agentx-postgres postgres  # PostgreSQL on port 5001
docker-compose run --rm test      # Run tests in Docker
```

## Architecture

### Core Components

**`src/agentx/`** - Core evaluation library
- `executor/sql_executor.py`: Main entry point. `SQLExecutor` orchestrates validation → execution → analysis pipeline
- `validation/hallucination.py`: `HallucinationDetector` identifies phantom tables/columns/functions before execution
- `validation/sql_parser.py`: `MultiDialectSQLParser` uses sqlglot for AST parsing and dialect-specific validation
- `infrastructure/database.py`: Database adapters (SQLite, DuckDB, PostgreSQL) with unified interface via `create_adapter()`
- `dialects/registry.py`: Dialect configurations including supported functions per dialect

**`evaluation/`** - Scoring system
- `enhanced_scorer.py`: 7-dimension scorer (correctness 35%, safety 20%, efficiency 15%, completeness 10%, semantic accuracy 10%, best practices 5%, plan quality 5%)
- `scorer.py`: Basic 4-dimension scorer
- `result_comparator.py`: Flexible result comparison with numeric tolerance and order-agnostic matching
- `advanced_scoring.py`: `QueryComplexityAnalyzer` for adaptive scoring thresholds

**`a2a/`** - REST API for agent integration
- `server.py`: Flask server with endpoints: `/evaluate`, `/schema`, `/tasks`, `/agents/register`, `/leaderboard`
- `client.py`: `A2AClient` for programmatic benchmark access

**`tasks/`** - Benchmark definitions
- `enterprise_schema.py`: Sets up 19-table enterprise data warehouse schema
- `gold_queries/sqlite/`: JSON task files with SQL queries and expected results

### Key Data Flow

1. SQL query → `SQLExecutor.process_query()`
2. `HallucinationDetector` validates against `SchemaSnapshot`
3. Dialect adapter executes query
4. `EnhancedScorer.score()` produces multi-dimensional evaluation

### Scoring Presets

Use `create_enhanced_scorer("preset")` with: `default`, `strict` (higher correctness/safety), `performance` (higher efficiency), `quality` (higher best practices)
