# Text-2-SQL Agent

LangGraph-based text-to-SQL agent and evaluation framework for the [AgentBeats](https://agentbeats.dev) platform.

## Repo layout

- **`agent/`** — SQL-generating agent (LangGraph, GPT-5, quality-gated retries). See `agent/CLAUDE.md` and `agent/plans/`.
- **`eval/`** — Benchmark framework (7-dimension scoring, hallucination detection, A2A protocol). See `eval/README.md`.

## Quick start

```bash
# Agent (from repo root)
cd agent && pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
python main.py        # or run as A2A server

# Eval
cd eval && pip install -r requirements.txt
python run_benchmark.py --output results/
```

## Docs

- Root: `CLAUDE.md`, `RECENT.md`
- Agent: `agent/CLAUDE.md`, `agent/plans/2026-02-21-text2sql-agent-design.md`
- Eval: `eval/README.md`, `eval/CLAUDE.md`
