# Text2SQL Interactive Playground — Design Doc

**Date:** 2026-02-24
**Status:** Approved

## Overview

A chat-style SQL playground with a live agent graph visualization panel. Single HTML file (Tailwind CDN + vanilla JS) connecting to the existing A2A Flask server via Server-Sent Events.

## Architecture

```
Browser (index.html)
   │
   ├── GET /schema              → schema sidebar
   ├── GET /query/stream?q=...  → SSE connection per question
   │     ├── event: graph   → full node/edge structure
   │     ├── event: step    → node running/done/error
   │     └── event: done    → final answer + scores
   └── closed
```

- **Frontend:** Single `frontend/index.html` — Tailwind CDN, vanilla JS, no build tools
- **Backend addition:** One SSE endpoint (`GET /query/stream`) added to `eval/agentx_a2a/server.py`
- **Agent integration:** SSE endpoint imports LangGraph agent, streams node events from `graph.stream()`

## Dashboard Layout

Three-panel dashboard (dark theme):

1. **Graph Panel (left, ~300px, collapsible):** Top-down directed graph of the LangGraph pipeline rendered with SVG. Nodes light up in real-time (gray=pending, pulsing blue=running, green=done, red=error). Retry loops shown as curved arrows. Multi-query plans fan out from planner. Clicking a node scrolls chat to that step.

2. **Chat Panel (center, main):** Conversational thread. User messages on one side, agent responses as collapsible step cards. SQL and Results steps expand by default. SQL gets syntax highlighting. Results render as HTML tables. Score shown as colored progress bar.

3. **Schema Panel (right, toggle):** Slides in over graph panel. Shows tables and columns from `/schema` endpoint.

Header: `Text2SQL Playground` with [Schema] [Graph] [Chat] toggles.
Footer: Input bar with send button.

## SSE Endpoint

```
GET /query/stream?question=<text>&dialect=sqlite
Content-Type: text/event-stream
```

| Event   | Data                                           | When                |
|---------|------------------------------------------------|---------------------|
| `graph` | `{nodes: [...], edges: [...]}`                 | Once at start       |
| `step`  | `{node, status: "running"}`                    | Node begins         |
| `step`  | `{node, status: "done", output, duration_ms}`  | Node completes      |
| `step`  | `{node, status: "error", error, retry_count}`  | Failure/retry       |
| `done`  | `{final_answer, queries, scores, total_ms}`    | Pipeline complete   |

## UI Behaviors

- Pipeline steps appear in real-time as SSE events arrive
- Steps are collapsible — SQL and Results expand by default
- SQL syntax highlighting via lightweight regex (no library)
- Score progress bar: red < 0.5, yellow < 0.7, green >= 0.7
- Graph node edges animate (dashed → solid) as data flows
- Chat history persists in session (scrollable)
- Mobile-responsive via Tailwind breakpoints

## Tech Stack

- Tailwind CSS via CDN
- Vanilla JavaScript (ES modules)
- SVG for graph rendering (no external graph library)
- EventSource API for SSE
- Flask `Response(stream_with_context(...))` for server-side SSE

## Files to Create/Modify

1. **Create** `frontend/index.html` — the entire frontend
2. **Modify** `eval/agentx_a2a/server.py` — add `/query/stream` SSE endpoint
3. **Possibly modify** `agent/graph.py` — ensure node events are interceptable for streaming
