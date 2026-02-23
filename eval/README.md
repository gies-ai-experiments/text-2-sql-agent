# Text-2-SQL Agent: Enterprise SQL Benchmark for A2A Agents

> A comprehensive, reproducible benchmark framework for evaluating LLM-powered SQL agents with multi-dimensional scoring, hallucination detection, and standardized A2A protocol support.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/keshavdalmia10/agentx-green)
[![A2A Compatible](https://img.shields.io/badge/A2A-compatible-green.svg)](https://agentbeats.dev)

---

## 📋 Table of Contents

- [Overview](#overview)
- [What Makes Text-2-SQL Agent Unique](#what-makes-text-2-sql-agent-unique)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Benchmark Design Quality](#benchmark-design-quality)
- [Evaluation Methodology](#evaluation-methodology)
- [Error Category Metrics](#error-category-metrics)
- [Docker Deployment](#docker-deployment)
- [Robust Error Handling & Logging](#robust-error-handling--logging)
- [Reproducibility](#reproducibility)
- [Resource Requirements](#resource-requirements)
- [API Reference](#api-reference)
- [Innovation & Impact](#innovation--impact)

---

## Overview

**Text-2-SQL Agent** is a standardized SQL benchmark designed to evaluate AI agents' ability to generate correct, efficient, and safe SQL queries. Unlike simple pass/fail benchmarks, Text-2-SQL Agent provides:

- **7-Dimensional Scoring**: Correctness, Efficiency, Safety, Completeness, Semantic Accuracy, Best Practices, Plan Quality
- **Hallucination Detection**: Pre-execution detection of phantom tables, columns, and invalid functions
- **Error Category Analysis**: Detailed breakdown of failure modes (schema errors, syntax errors, planning errors)
- **Multi-Dialect Support**: SQLite, DuckDB, PostgreSQL, BigQuery
- **A2A Protocol**: Standardized agent-to-agent communication for reproducible tournaments

### Target Audience

- **AI Researchers**: Evaluate and compare SQL generation models
- **LLM Developers**: Benchmark text-to-SQL capabilities
- **Enterprise Teams**: Assess agents for production readiness
- **AgentBeats Platform Users**: Run standardized tournaments

---

## What Makes Text-2-SQL Agent Unique

### 1. Beyond Binary Pass/Fail

Traditional SQL benchmarks only check if queries execute and return correct results. Text-2-SQL Agent evaluates **how** the SQL was generated:

| Dimension | What It Measures | Why It Matters |
|-----------|------------------|----------------|
| **Correctness** (35%) | Result matches expected output | Core functionality |
| **Efficiency** (15%) | Query execution time | Production readiness |
| **Safety** (20%) | No hallucinations, valid syntax | Reliability |
| **Completeness** (10%) | All expected data returned | Data quality |
| **Semantic Accuracy** (10%) | Values match, not just row counts | Precision |
| **Best Practices** (5%) | No SELECT *, proper JOINs | Code quality |
| **Plan Quality** (5%) | Efficient execution plan | Database optimization |

### 2. Pre-Execution Hallucination Detection

Text-2-SQL Agent detects **phantom identifiers** before execution, preventing cryptic database errors:

```
Query: SELECT fake_column FROM nonexistent_table
┌─────────────────────────────────────────────────────────────┐
│ HALLUCINATION DETECTED                                       │
├─────────────────────────────────────────────────────────────┤
│ ⚠ Phantom Table: nonexistent_table                          │
│ ⚠ Phantom Column: fake_column                               │
│ Hallucination Score: 0.0 (severe)                           │
└─────────────────────────────────────────────────────────────┘
```

### 3. Error Category Classification

Inspired by [research on SQL generation failures](https://arxiv.org/abs/2411.07763), Text-2-SQL Agent classifies errors into actionable categories:

```
┌─────────────────────────────────────────────────────────────┐
│                    ERROR DISTRIBUTION                        │
├─────────────────────────────────────────────────────────────┤
│ Schema Errors (54.3%)                                        │
│   ├── Wrong Schema Linking: 27.6%                           │
│   ├── Wrong Column: 16.6%                                   │
│   └── Wrong Table: 10.1%                                    │
│                                                              │
│ Analysis Errors (60.7%)                                      │
│   ├── Erroneous Data Analysis: 35.5%                        │
│   ├── Incorrect Planning: 17.7%                             │
│   └── Incorrect Data Calculation: 7.5%                      │
│                                                              │
│ SQL Errors (37.5%)                                           │
│   ├── Condition Filter Error: 11.5%                         │
│   ├── Dialect/Function Error: 10.3%                         │
│   ├── Join Error: 8.3%                                      │
│   └── Syntax Error: 7.4%                                    │
└─────────────────────────────────────────────────────────────┘
```

### 4. Standardized A2A Protocol

Text-2-SQL Agent implements the AgentBeats A2A protocol for reproducible agent tournaments:

```
┌─────────────────────────────────────────────────────────────┐
│                     TOURNAMENT FLOW                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    Tasks     ┌─────────────────────────┐   │
│  │ GREEN AGENT │ ───────────▶ │     PURPLE AGENTS       │   │
│  │ (Evaluator) │              │  ┌─────────┐ ┌────────┐ │   │
│  │             │ ◀─────────── │  │ Agent A │ │Agent B │ │   │
│  │ Text-2-SQL  │    SQL       │  │ (GPT-4) │ │(Gemini)│ │   │
│  └─────────────┘  Responses   │  └─────────┘ └────────┘ │   │
│         │                     └─────────────────────────┘   │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   ARTIFACT                           │    │
│  │  Rankings, Scores, Error Metrics, Recommendations   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TEXT-2-SQL AGENT EVALUATION SYSTEM                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         SQL EXECUTOR (Multi-Dialect)                  │  │
│  │  ┌───────────┐  ┌───────────┐  ┌────────────┐  ┌───────────┐         │  │
│  │  │  SQLite   │  │  DuckDB   │  │ PostgreSQL │  │  BigQuery │         │  │
│  │  │ (default) │  │(analytics)│  │   (prod)   │  │  (cloud)  │         │  │
│  │  └───────────┘  └───────────┘  └────────────┘  └───────────┘         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      VALIDATION LAYER                                 │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │  │
│  │  │ SQL Parser      │  │ Hallucination   │  │ Schema Validator    │   │  │
│  │  │ • sqlglot AST   │  │ Detector        │  │ • Table existence   │   │  │
│  │  │ • Multi-dialect │  │ • Phantom tables│  │ • Column validation │   │  │
│  │  │ • Transpilation │  │ • Phantom cols  │  │ • Type checking     │   │  │
│  │  └─────────────────┘  │ • Invalid funcs │  └─────────────────────┘   │  │
│  │                       └─────────────────┘                             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      ERROR CLASSIFIER                                 │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │Schema Errors│  │Analysis Err │  │  SQL Errors │  │Other Errors │  │  │
│  │  │• Wrong table│  │• Bad plan   │  │• Syntax     │  │• Prompt len │  │  │
│  │  │• Wrong col  │  │• Bad calc   │  │• Join error │  │• Ext. knowl │  │  │
│  │  │• Bad linking│  │• Data error │  │• Filter err │  │             │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    7-DIMENSIONAL SCORING ENGINE                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ Correctness │  │ Efficiency  │  │   Safety    │  │  Semantic   │  │  │
│  │  │    35%      │  │    15%      │  │    20%      │  │  Accuracy   │  │  │
│  │  │             │  │  Adaptive   │  │  Weighted   │  │    10%      │  │  │
│  │  └─────────────┘  │ Thresholds  │  │ Hallucin.   │  └─────────────┘  │  │
│  │                   └─────────────┘  └─────────────┘                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │  │
│  │  │Completeness │  │    Best     │  │    Plan     │                    │  │
│  │  │    10%      │  │  Practices  │  │  Quality    │                    │  │
│  │  │             │  │     5%      │  │     5%      │                    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **SQL Executor** | Execute queries across databases | Connection pooling, timeout handling, error recovery |
| **Validation Layer** | Pre-execution analysis | AST parsing, schema validation, hallucination detection |
| **Error Classifier** | Categorize failures | Pattern matching, confidence scoring, actionable insights |
| **Scoring Engine** | Multi-dimensional evaluation | Weighted scoring, adaptive thresholds, presets |
| **Artifact Builder** | Generate reports | Rankings, metrics, visualizations |

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/ashcastelinocs124/text-2-sql-agent.git
cd text-2-sql-agent

# Create environment file
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY (for Gemini)

# Start all services (Green Agent + Purple Agent)
docker-compose -f docker-compose.agentbeats.yml up -d

# Verify services are running
curl http://localhost:8001/health  # Green Agent (Evaluator)
curl http://localhost:8080/health  # Purple Agent (SQL Generator)

# Run a tournament
curl -X POST http://localhost:8001/assess \
  -H "Content-Type: application/json" \
  -d '{
    "participants": {
      "gemini": "http://agentx-purple-gemini:8080"
    },
    "config": {
      "task_count": 10,
      "difficulty": ["easy", "medium"],
      "scorer_preset": "default"
    }
  }'

# Stop services
docker-compose -f docker-compose.agentbeats.yml down
```

### Option 2: Local Installation

```bash
# Clone repository
git clone https://github.com/ashcastelinocs124/text-2-sql-agent.git
cd text-2-sql-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run benchmark locally
python run_benchmark.py --output results/

# Run with specific difficulties
python run_benchmark.py --difficulty easy,medium,hard --output results/
```

### Option 3: Programmatic Usage

```python
from agentx import SQLExecutor, ExecutorConfig

# Create executor (SQLite, zero setup)
executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))

# Execute and evaluate a query
result = executor.process_query("SELECT * FROM customers WHERE city = 'NYC'")

print(f"Status: {result.overall_status}")
print(f"Score: {result.scores.overall:.2%}")
print(f"Hallucination Score: {result.scores.hallucination_score:.2%}")

executor.close()
```

---

## Benchmark Design Quality

### Task Difficulty Progression

Text-2-SQL Agent provides **27+ SQL tasks** across 4 difficulty levels:

| Difficulty | Tasks | Skills Tested |
|------------|-------|---------------|
| **Easy** (10) | Basic SELECT, WHERE, LIMIT, COUNT | Schema understanding, simple filters |
| **Medium** (10) | JOINs, Subqueries, GROUP BY, CASE | Multi-table reasoning, aggregation |
| **Hard** (4) | Window functions, CTEs, Ranking | Advanced SQL, analytical queries |
| **Enterprise** (30) | Star schema, SCD, Sessionization, Cohorts | Real-world data warehouse patterns |

### Real-World Representative Tasks

Tasks are modeled on actual production SQL patterns:

```sql
-- Enterprise: Star Schema Analysis (Realistic data warehouse pattern)
SELECT dp.category, ds.region, SUM(sf.quantity * sf.unit_price) as revenue
FROM sales_fact sf
JOIN dim_product dp ON sf.product_id = dp.product_id
JOIN dim_store ds ON sf.store_id = ds.store_id
GROUP BY dp.category, ds.region
ORDER BY revenue DESC

-- Hard: Sessionization with 30-minute timeout (User behavior analytics)
WITH time_diffs AS (
  SELECT user_id, event_timestamp,
    CASE WHEN (julianday(event_timestamp) - 
               julianday(LAG(event_timestamp) OVER (...))) * 24 * 60 > 30
         THEN 1 ELSE 0 END as new_session
  FROM user_events
)
SELECT user_id, SUM(new_session) OVER (...) as session_id FROM time_diffs
```

### Agentic Capability Testing

| Capability | How Text-2-SQL Agent Tests It |
|------------|---------------------|
| **Schema Understanding** | Agents must correctly identify tables/columns from schema |
| **Multi-step Reasoning** | Complex queries require planning (CTEs, subqueries) |
| **Dialect Awareness** | Function validation per database dialect |
| **Error Recovery** | Hallucination detection before execution |
| **Best Practices** | Code quality scoring (avoiding anti-patterns) |

### Why Text-2-SQL Agent Tasks Are Not Trivial

Text-2-SQL Agent is designed to **avoid tasks solvable by simple heuristics**. Here's how our tasks compare:

#### Trivial vs Text-2-SQL Agent Task Comparison

| Aspect | ❌ Trivial Benchmark | ✅ Text-2-SQL Agent Task |
|--------|---------------------|----------------|
| **Query** | `SELECT * FROM users` | `SELECT name, total_spent FROM customers WHERE id IN (SELECT customer_id FROM orders GROUP BY customer_id HAVING SUM(total) > 500)` |
| **Reasoning** | Template matching | Multi-step planning required |
| **Schema** | Single table | 19-table enterprise schema with relationships |
| **Evaluation** | Binary pass/fail | 7-dimensional nuanced scoring |
| **Error Insight** | "Query failed" | "Wrong column: used `user_name` instead of `name` (schema_error)" |

#### Why Simple Heuristics Fail on Text-2-SQL Agent

| Heuristic | Why It Fails |
|-----------|--------------|
| "Just use SELECT *" | Best practices score penalizes SELECT * |
| "Match keywords to columns" | Enterprise schema has similar column names across tables |
| "Use first table mentioned" | Star schema requires correct fact-dimension joins |
| "Copy SQL patterns" | Sessionization, SCD queries require semantic understanding |
| "Ignore schema relationships" | Foreign key joins are required for correct results |

#### Task Complexity Examples

**❌ Trivial (WikiSQL-style):**
```sql
-- Question: "How many employees are there?"
SELECT COUNT(*) FROM employees
-- Solvable by: keyword matching "count" → COUNT(*)
```

**✅ Text-2-SQL Agent Medium:**
```sql
-- Question: "Find customers who have placed orders with a total greater than 100"
SELECT * FROM customers 
WHERE id IN (SELECT customer_id FROM orders WHERE total > 100)
-- Requires: Understanding two tables, subquery planning, correct join logic
```

**✅ Text-2-SQL Agent Enterprise:**
```sql
-- Question: "Calculate cohort retention: for each monthly cohort, 
--            show what percentage of customers made purchases in subsequent months"
WITH first_purchase AS (
  SELECT customer_id, strftime('%Y-%m', MIN(order_date)) as cohort_month
  FROM orders_fact GROUP BY customer_id
),
monthly_activity AS (
  SELECT o.customer_id, f.cohort_month,
    (strftime('%Y', o.order_date) - strftime('%Y', f.cohort_month || '-01')) * 12 +
    (strftime('%m', o.order_date) - strftime('%m', f.cohort_month || '-01')) as months_since
  FROM orders_fact o JOIN first_purchase f ON o.customer_id = f.customer_id
)
SELECT cohort_month, months_since, 
  COUNT(DISTINCT customer_id) as active_customers,
  ROUND(COUNT(DISTINCT customer_id) * 100.0 / 
    FIRST_VALUE(COUNT(DISTINCT customer_id)) OVER (PARTITION BY cohort_month ORDER BY months_since), 2) as retention_rate
FROM monthly_activity
GROUP BY cohort_month, months_since
-- Requires: CTEs, window functions, date arithmetic, multi-step aggregation
```

#### Complexity Metrics

| Difficulty | Avg Tables | Avg Joins | Uses CTEs | Uses Window Funcs | Subqueries |
|------------|------------|-----------|-----------|-------------------|------------|
| Easy | 1.0 | 0 | 0% | 0% | 10% |
| Medium | 1.8 | 0.8 | 20% | 0% | 40% |
| Hard | 2.5 | 1.5 | 60% | 80% | 30% |
| Enterprise | 3.2 | 2.4 | 70% | 60% | 50% |

---

## Evaluation Methodology

### Scoring Criteria

Each dimension has **clear, objective criteria**:

```python
# Correctness: Exact result matching with tolerance
correctness_score = comparator.compare(
    actual_results, 
    expected_results,
    numeric_tolerance=1e-6,
    ignore_row_order=True,
)

# Safety: Weighted hallucination severity
safety_score = 1.0 - (
    0.4 * (1 if phantom_tables else 0) +      # Severe
    0.35 * (1 if phantom_columns else 0) +    # Moderate
    0.25 * (1 if invalid_functions else 0)    # Minor
)

# Efficiency: Adaptive thresholds based on complexity
efficiency_score = score_execution_time(
    time_ms=result.execution_time_ms,
    thresholds=get_thresholds_for_complexity(query_complexity)
)
```

### Scoring Presets

| Preset | Use Case | Weights Modified |
|--------|----------|------------------|
| **default** | Balanced evaluation | Standard weights |
| **strict** | Production safety | +Safety, +Correctness |
| **performance** | Query optimization | +Efficiency, +Plan Quality |
| **quality** | Code review | +Best Practices |

### Automated Evaluation

All evaluation is **fully automated** with no manual intervention:

1. **Parse** SQL using sqlglot AST
2. **Validate** against schema snapshot
3. **Detect** hallucinations before execution
4. **Execute** with timeout and error handling
5. **Compare** results with expected output
6. **Score** across all 7 dimensions
7. **Classify** any errors into categories
8. **Generate** artifact with metrics

---

## Error Category Metrics

Text-2-SQL Agent classifies errors to provide actionable debugging insights:

### Error Categories

| Category | Subcategory | Description |
|----------|-------------|-------------|
| **Schema Error** | `wrong_table` | Table doesn't exist in schema |
| | `wrong_column` | Column doesn't exist in table |
| | `wrong_schema_linking` | Incorrect foreign key / alias usage |
| **Analysis Error** | `erroneous_data_analysis` | Logic error in query |
| | `incorrect_planning` | Missing GROUP BY, wrong aggregation |
| | `incorrect_data_calculation` | Division by zero, numeric overflow |
| **SQL Error** | `syntax_error` | Invalid SQL syntax |
| | `join_error` | Ambiguous/invalid JOIN conditions |
| | `condition_filter_error` | Invalid WHERE/HAVING clauses |
| | `dialect_function_error` | Function not supported in dialect |
| **Other** | `excessive_prompt_length` | Context limit exceeded |
| | `misunderstanding_external_knowledge` | Domain knowledge error |

### Metrics Output

```json
{
  "error_metrics_summary": {
    "total_tasks": 27,
    "successful_tasks": 19,
    "failed_tasks": 8,
    "success_rate": 70.4,
    "category_percentages": {
      "schema_error": 62.5,
      "sql_error": 25.0,
      "analysis_error": 12.5
    },
    "subcategory_percentages": {
      "wrong_column": 37.5,
      "wrong_table": 25.0,
      "syntax_error": 25.0,
      "incorrect_planning": 12.5
    }
  }
}
```

---

## Docker Deployment

### Pre-built Images

| Image | Description | Size |
|-------|-------------|------|
| `ghcr.io/ashcastelinocs124/agentx-green` | SQL Benchmark Evaluator (A2A Protocol) | ~600MB |
| `ghcr.io/ashcastelinocs124/agentx-purple` | LLM SQL Generator | ~400MB |

### Docker Compose

```yaml
# docker-compose.agentbeats.yml
services:
  agentx-green:
    image: ghcr.io/ashcastelinocs124/agentx-green:latest
    ports:
      - "9009:9009"
    command: ["--host", "0.0.0.0", "--port", "9009", "--dialect", "sqlite"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:9009/.well-known/agent.json')"]
      interval: 10s
      timeout: 5s
      retries: 3

  agentx-purple-gemini:
    image: ghcr.io/ashcastelinocs124/agentx-purple:latest
    ports:
      - "8080:8080"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
    command: ["--host", "0.0.0.0", "--port", "8080", "--llm", "gemini"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/.well-known/agent.json')"]
      interval: 10s
      timeout: 5s
      retries: 3
```

### Build from Source

```bash
# Build Green Agent (A2A Protocol Compatible)
docker build --platform linux/amd64 -f docker/Dockerfile.green -t agentx-green .

# Build Purple Agent
docker build --platform linux/amd64 -f docker/Dockerfile.purple -t agentx-purple .

# Multi-platform build for GHCR
docker buildx build --platform linux/amd64 -f docker/Dockerfile.green -t ghcr.io/ashcastelinocs124/agentx-green:latest --push .
docker buildx build --platform linux/amd64 -f docker/Dockerfile.purple -t ghcr.io/ashcastelinocs124/agentx-purple:latest --push .
```

### Key Changes in Latest Docker Images

#### Green Agent (A2A Protocol)
- **A2A Protocol Support**: Now implements standard A2A protocol for AgentBeats compatibility
- **New Entrypoint**: Uses `entrypoint_green_a2a.py` with A2AStarletteApplication
- **Port Change**: Default port changed from 8001 to 9009
- **Dependencies**: Added `a2a-sdk[http-server]>=0.3.20` and `uvicorn>=0.38.0`
- **Health Check**: Uses Python urllib instead of curl (compatible with slim images)

#### Purple Agent
- **Agent Card Support**: Added `/.well-known/agent-card.json` endpoint for AgentBeats
- **Health Check**: Uses Python urllib for compatibility
- **Multi-LLM Support**: Gemini (default) and OpenAI via environment variables

---

## Robust Error Handling & Logging

Text-2-SQL Agent implements production-grade resilience patterns to ensure reliable operation during agent tournaments and benchmarks.

### Circuit Breaker Pattern

Prevents cascading failures when agents become unavailable:

```python
from a2a.resilience import CircuitBreaker, CircuitState

# Circuit breaker automatically opens after 3 failures
breaker = CircuitBreaker(
    failure_threshold=3,      # Open after 3 consecutive failures
    recovery_timeout=30.0,    # Wait 30s before testing recovery
    half_open_max_calls=1,    # Allow 1 test call in half-open state
)

# Usage in agent communication
if breaker.can_execute():
    try:
        result = await send_task_to_agent(endpoint, task)
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        # After 3 failures, circuit opens → fast-fail for 30s
else:
    raise CircuitOpenError(f"Agent {endpoint} unavailable")
```

**Circuit States:**
```
┌─────────┐  3 failures  ┌─────────┐  30s timeout  ┌───────────┐
│ CLOSED  │ ───────────▶ │  OPEN   │ ────────────▶ │ HALF-OPEN │
│(normal) │              │(reject) │               │  (test)   │
└─────────┘              └─────────┘               └───────────┘
     ▲                                                   │
     │              success                              │
     └───────────────────────────────────────────────────┘
```

### Retry with Exponential Backoff

```python
from a2a.resilience import ResilientHTTPClient

# HTTP client with automatic retry and circuit breaker
client = ResilientHTTPClient(
    circuit_failure_threshold=3,
    circuit_recovery_timeout=30.0,
)

# Automatically retries with exponential backoff (1s, 2s, 4s)
response = await client.request(
    "POST",
    "http://agent:8080/generate",
    operation_type="sql_generation",  # 60s timeout for LLM calls
    json={"question": "...", "schema": {...}}
)
```

**Timeout Configuration:**
| Operation Type | Default Timeout | Rationale |
|----------------|-----------------|-----------|
| `health_check` | 5s | Quick liveness/readiness probes |
| `sql_generation` | 60s | LLM generation can be slow |
| `schema_fetch` | 10s | Database schema operations |
| `default` | 30s | Standard operations |

### Comprehensive Health Checks

Kubernetes-compatible liveness and readiness probes:

```python
from a2a.health import HealthChecker, HealthStatus

# Initialize health checker with agent and executor
checker = HealthChecker(
    agent=green_agent,
    executor=sql_executor,
    version="1.0.0",
)

# Liveness probe (quick, <100ms)
liveness = await checker.check_liveness()
# Returns: {"status": "healthy", "checks": [{"name": "process", "status": "pass"}]}

# Readiness probe (thorough)
readiness = await checker.check_readiness()
# Checks: tasks_loaded, database, llm_client, custom checks
```

**Health Response Example:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T01:25:00Z",
  "version": "1.0.0",
  "checks": [
    {"name": "tasks_loaded", "status": "pass", "duration_ms": 0.5, "message": "27 tasks loaded"},
    {"name": "database", "status": "pass", "duration_ms": 1.2, "message": "Database accessible"},
    {"name": "llm_client", "status": "pass", "duration_ms": 0.3, "message": "LLM client configured (gemini)"}
  ]
}
```

### Error Recovery Strategies

| Error Type | Recovery Strategy |
|------------|-------------------|
| **Network Timeout** | Retry 3x with exponential backoff |
| **Agent Unavailable** | Circuit breaker → fast-fail → auto-recover |
| **Database Error** | Log, mark task failed, continue evaluation |
| **LLM API Error** | Retry with backoff, degrade gracefully |
| **Invalid SQL** | Classify error, score as 0, provide feedback |

### Logging Configuration

```python
import logging

# Enable detailed logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Component-specific log levels
logging.getLogger('a2a.server').setLevel(logging.DEBUG)      # API requests
logging.getLogger('a2a.resilience').setLevel(logging.INFO)   # Circuit breaker events
logging.getLogger('a2a.health').setLevel(logging.DEBUG)      # Health checks
logging.getLogger('agentx.executor').setLevel(logging.INFO)  # SQL execution
```

**Sample Log Output:**
```
2025-01-15 01:25:00,123 - a2a.server - INFO - Starting assessment abc123 with 2 participants
2025-01-15 01:25:00,456 - a2a.resilience - INFO - Circuit CLOSED for agent1:8080
2025-01-15 01:25:01,789 - agentx.executor - INFO - Executed query in 2.3ms, 5 rows returned
2025-01-15 01:25:02,012 - a2a.resilience - WARN - Failure 1/3 for agent2:8081
2025-01-15 01:25:05,345 - a2a.resilience - WARN - Circuit OPEN for agent2:8081 (3 failures)
2025-01-15 01:25:35,678 - a2a.resilience - INFO - Circuit HALF-OPEN for agent2:8081, testing...
```

---

## Reproducibility

### Consistent Results Guarantee

Text-2-SQL Agent ensures reproducible benchmark runs through:

| Feature | Implementation |
|---------|----------------|
| **Deterministic Task Order** | Tasks loaded from JSON in fixed order |
| **Fixed Seed Data** | Same sample data for all runs |
| **Schema Snapshots** | Captured before evaluation |
| **Versioned Tasks** | Task definitions in version control |
| **Same-Tasks Mode** | All agents receive identical tasks in tournaments |

### Running the Same Benchmark

```bash
# Same tasks file, same difficulty, same output
python run_benchmark.py \
  --tasks tasks/gold_queries/sqlite/basic_queries.json \
  --difficulty easy,medium \
  --output results/

# Results will be identical across runs (for same agent)
```

### Tournament Reproducibility

```bash
# Configure tournament in scenario.toml
[scenario]
name = "SQL Benchmark Tournament"

[config]
same_tasks = true           # All agents get same tasks
difficulty = ["easy", "medium"]
task_count = 10
scorer_preset = "default"
```

---

## Resource Requirements

### Minimum Requirements

| Resource | Green Agent | Purple Agent |
|----------|-------------|--------------|
| **CPU** | 1 core | 1 core |
| **Memory** | 512MB | 1GB |
| **Disk** | 200MB | 200MB |
| **Time/Task** | ~100ms | ~2-5s (LLM dependent) |

### Recommended for Production

| Resource | Recommendation |
|----------|----------------|
| **CPU** | 2 cores |
| **Memory** | 2GB |
| **Timeout** | 30s per query |
| **Concurrent Agents** | Up to 5 in parallel |

### Performance Benchmarks

```
┌─────────────────────────────────────────────────────────────┐
│ BENCHMARK: 27 tasks, SQLite, default scorer                 │
├─────────────────────────────────────────────────────────────┤
│ Total Time:           0.08 seconds                          │
│ Tasks/Second:         337.5                                 │
│ Avg Execution Time:   0.02ms per query                      │
│ Memory Peak:          150MB                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## API Reference

### Green Agent Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/schema` | Get database schema |
| `GET` | `/.well-known/agent.json` | A2A agent descriptor |
| `POST` | `/assess` | Run tournament assessment |

### Purple Agent Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/.well-known/agent.json` | A2A agent descriptor |
| `POST` | `/generate` | Generate SQL from question |

### Assessment Request

```json
POST /assess
{
  "participants": {
    "agent_id": "http://agent-endpoint:port"
  },
  "config": {
    "task_count": 10,
    "difficulty": ["easy", "medium", "hard"],
    "scorer_preset": "default",
    "same_tasks": true,
    "parallel_evaluation": true
  }
}
```

### Assessment Response

```json
{
  "status": "completed",
  "artifact": {
    "assessment_id": "abc123",
    "rankings": [
      {"rank": 1, "participant_id": "agent1", "overall_score": 0.92}
    ],
    "participants": {
      "agent1": {
        "scores": {
          "overall": 0.92,
          "correctness": 0.95,
          "efficiency": 0.88,
          "safety": 1.0
        }
      }
    },
    "error_metrics_summary": {
      "category_percentages": {"schema_error": 50.0},
      "subcategory_percentages": {"wrong_column": 50.0}
    }
  }
}
```

---

## Innovation & Impact

### Original Contributions

1. **Multi-Dimensional SQL Scoring**: First benchmark to evaluate 7 dimensions beyond correctness
2. **Pre-Execution Hallucination Detection**: Catches phantom identifiers before database errors
3. **Error Category Classification**: Research-backed categorization of SQL generation failures
4. **A2A Protocol Integration**: Standardized tournament interface for agent comparison

### Addressing Evaluation Gaps

| Gap in Existing Benchmarks | Text-2-SQL Agent Solution |
|----------------------------|-----------------|
| Binary pass/fail only | 7-dimensional nuanced scoring |
| No hallucination tracking | Pre-execution phantom detection |
| Cryptic database errors | Actionable error categorization |
| No code quality assessment | Best practices dimension |
| Single dialect focus | Multi-dialect support |

### Use Cases

- **Model Comparison**: Benchmark GPT-4 vs Gemini vs Claude on SQL generation
- **Regression Testing**: Track model quality over versions
- **Production Readiness**: Assess safety and efficiency for deployment
- **Research**: Analyze error patterns in SQL generation

### Complementary to Existing Benchmarks

| Benchmark | Focus | Text-2-SQL Agent Complement |
|-----------|-------|-------------------|
| Spider | Schema understanding | + Safety & efficiency scoring |
| BIRD | Complex queries | + Hallucination detection |
| WikiSQL | Simple queries | + Enterprise patterns |

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

Contributions welcome! Please see our [contribution guidelines](CONTRIBUTING.md).

---

## Citation

If you use Text-2-SQL Agent in your research, please cite:

```bibtex
@software{text2sqlagent2025,
  title = {Text-2-SQL Agent: Enterprise SQL Benchmark for A2A Agents},
  author = {Dalmia, Keshav},
  year = {2025},
  url = {https://github.com/ashcastelinocs124/text-2-sql-agent}
}
```
