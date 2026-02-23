# AgentX SQL Benchmark - Docker Image
#
# Multi-dialect SQL evaluation framework for LLM agents
#
# Build:
#   docker build -t agentx-benchmark .
#
# Run A2A Server:
#   docker run -p 5000:5000 agentx-benchmark
#
# Run with PostgreSQL:
#   docker run -p 5000:5000 -e DIALECT=postgresql \
#     -e PG_CONNECTION_STRING="postgresql://user:pass@host/db" \
#     agentx-benchmark

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    DIALECT=sqlite \
    PORT=5000 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY evaluation/ ./evaluation/
COPY a2a/ ./a2a/
COPY tasks/ ./tasks/
COPY run_evaluation_pipeline.py .
COPY test_*.py ./

# Create non-root user for security
RUN useradd -m -u 1000 agentx && \
    chown -R agentx:agentx /app

USER agentx

# Expose the A2A server port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT}/health').raise_for_status()" || exit 1

# Default command: Start A2A server
CMD ["python", "-m", "a2a.server"]
