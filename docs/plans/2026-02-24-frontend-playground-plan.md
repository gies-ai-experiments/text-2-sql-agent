# Text2SQL Interactive Playground — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a chat-style SQL playground with live agent graph visualization, connecting to the A2A Flask server via SSE.

**Architecture:** Single HTML file (`frontend/index.html`) with Tailwind CDN + vanilla JS. One new SSE endpoint (`GET /query/stream`) added to `eval/agentx_a2a/server.py` that runs the LangGraph agent and streams node events. Dashboard layout with left graph panel + center chat panel + toggleable schema panel.

**Tech Stack:** Flask SSE (stream_with_context), LangGraph stream_mode="updates", Tailwind CSS CDN, vanilla JS + SVG for graph rendering, EventSource API.

---

## Task 1: Add SSE streaming endpoint to Flask server

**Files:**
- Modify: `eval/agentx_a2a/server.py` (add `/query/stream` route inside `create_app()`)

**Step 1: Add the SSE endpoint**

Add a new route inside `create_app()` after the existing `/schema` endpoint (around line 671). The endpoint:
1. Reads `question` and `dialect` from query params
2. Imports and runs the LangGraph agent via `build_graph()` + `graph.stream()`
3. Yields SSE events for each node update
4. Sends a `graph` event first with the static node/edge structure
5. Sends `step` events as each node completes
6. Sends a `done` event with final results

```python
@app.route("/query/stream", methods=["GET"])
def query_stream():
    """Stream agent pipeline execution as Server-Sent Events."""
    question = request.args.get("question", "")
    dialect = request.args.get("dialect", "sqlite")

    if not question:
        return jsonify({"error": "question parameter required"}), 400

    def generate():
        import time as _time

        # Add agent to path
        agent_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent")
        if agent_root not in sys.path:
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

        from agent.graph import build_graph as _build_graph

        # Send graph structure first
        graph_structure = {
            "nodes": [
                {"id": "schema_analyzer", "label": "Schema Analysis"},
                {"id": "planner", "label": "Planner"},
                {"id": "set_first_task", "label": "Set Task", "hidden": True},
                {"id": "query_generator", "label": "SQL Generator"},
                {"id": "executor_eval", "label": "Executor & Scorer"},
                {"id": "retry_handler", "label": "Retry Handler"},
                {"id": "check_remaining", "label": "Check Remaining", "hidden": True},
                {"id": "set_next_task", "label": "Next Task", "hidden": True},
                {"id": "summarizer", "label": "Summarizer"},
            ],
            "edges": [
                {"from": "schema_analyzer", "to": "planner"},
                {"from": "planner", "to": "query_generator"},
                {"from": "query_generator", "to": "executor_eval"},
                {"from": "executor_eval", "to": "retry_handler", "type": "retry"},
                {"from": "executor_eval", "to": "summarizer", "type": "done"},
                {"from": "retry_handler", "to": "query_generator", "type": "retry"},
            ],
        }
        yield f"event: graph\ndata: {json.dumps(graph_structure)}\n\n"

        # Build initial state (mirrors agent/main.py)
        db_path = server._get_executor().adapter.db_path if hasattr(server._get_executor().adapter, 'db_path') else ":memory:"
        initial_state = {
            "question": question,
            "dialect": dialect,
            "db_path": db_path,
            "schema_context": "",
            "plan": {"plan_type": "single", "tasks": [], "confidence": 0.0},
            "current_task": {"id": "", "description": "", "sql": "", "depends_on": []},
            "queries": [],
            "query_results": [],
            "retry_count": 0,
            "retry_feedback": "",
            "final_answer": "",
        }

        graph = _build_graph()
        start = _time.perf_counter()
        all_queries = []
        all_results = []
        last_event = {}

        for event in graph.stream(initial_state, stream_mode="updates"):
            for node_name, update in event.items():
                if not update:
                    continue

                # Accumulate
                if "queries" in update:
                    all_queries.extend(update["queries"])
                if "query_results" in update:
                    all_results.extend(update["query_results"])

                last_event = event

                # Build step payload — include key outputs per node
                step_data = {
                    "node": node_name,
                    "status": "done",
                    "duration_ms": round((_time.perf_counter() - start) * 1000),
                }

                # Attach relevant output per node type
                if node_name == "schema_analyzer":
                    step_data["output"] = {"schema": update.get("schema_context", "")[:2000]}
                elif node_name == "planner":
                    step_data["output"] = {"plan": update.get("plan", {})}
                elif node_name == "query_generator":
                    task = update.get("current_task", {})
                    step_data["output"] = {"sql": task.get("sql", ""), "task_id": task.get("id", "")}
                elif node_name == "executor_eval":
                    results = update.get("query_results", [{}])
                    r = results[0] if results else {}
                    step_data["output"] = {
                        "score": r.get("score", 0),
                        "status": r.get("status", ""),
                        "rows_returned": r.get("rows_returned", 0),
                        "data": r.get("data", [])[:50],
                        "error": r.get("error", ""),
                        "eval_report": r.get("eval_report", {}),
                    }
                elif node_name == "retry_handler":
                    step_data["output"] = {
                        "retry_count": update.get("retry_count", 0),
                        "feedback": update.get("retry_feedback", ""),
                    }
                    step_data["status"] = "retry"
                elif node_name == "summarizer":
                    step_data["output"] = {"answer": update.get("final_answer", "")}
                else:
                    # Helper nodes (set_first_task, check_remaining, etc.)
                    step_data["output"] = {}
                    step_data["hidden"] = True

                yield f"event: step\ndata: {json.dumps(step_data)}\n\n"

        elapsed = round((_time.perf_counter() - start) * 1000)

        # Final done event
        final_answer = ""
        if "summarizer" in last_event:
            final_answer = last_event["summarizer"].get("final_answer", "")

        done_data = {
            "final_answer": final_answer,
            "queries": all_queries,
            "results": all_results,
            "total_ms": elapsed,
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
```

**Step 2: Verify server starts**

Run: `cd /Users/ash/Desktop/text2sql && python -m agentx_a2a.server --port 5000`
Expected: Server starts without import errors, `/query/stream` shows in endpoint list.

**Step 3: Commit**

```bash
git add eval/agentx_a2a/server.py
git commit -m "feat: add SSE /query/stream endpoint for frontend playground"
```

---

## Task 2: Create the frontend HTML file — base layout and chat UI

**Files:**
- Create: `frontend/index.html`

**Step 1: Create the base HTML with dashboard layout**

Build the full single-file HTML with:

1. **Head:** Tailwind CDN, dark theme CSS vars, custom styles for chat bubbles / code blocks / score bars
2. **Header bar:** Title "Text2SQL Playground", toggle buttons [Schema] [Graph]
3. **Left panel (graph):** SVG container for the pipeline visualization, ~300px wide, collapsible
4. **Center panel (chat):** Scrollable message thread + fixed input bar at bottom
5. **Right panel (schema):** Slides over graph panel when toggled, shows tables from `/schema`

The HTML structure:
```html
<div id="app" class="h-screen flex flex-col bg-gray-950 text-gray-100">
  <!-- Header -->
  <header>...</header>
  <!-- Main content -->
  <div class="flex flex-1 overflow-hidden">
    <!-- Graph panel -->
    <aside id="graph-panel">
      <svg id="pipeline-graph">...</svg>
    </aside>
    <!-- Chat panel -->
    <main id="chat-panel">
      <div id="messages" class="flex-1 overflow-y-auto">...</div>
      <div id="input-bar">...</div>
    </main>
  </div>
</div>
```

**Step 2: Implement the chat message system (JS)**

Chat message types:
- **User message:** Right-aligned bubble with the question text
- **Agent message:** Left-aligned card containing collapsible pipeline steps

Each agent message is a container that accumulates step cards as SSE events arrive:
```javascript
function addUserMessage(text) { ... }
function addAgentMessage() { return container; }  // returns element to append steps to
function addStepCard(container, stepData) { ... }  // adds a collapsible step
```

Step card rendering by node type:
- `schema_analyzer`: Shows truncated schema text
- `planner`: Shows plan type, task count, confidence
- `query_generator`: Shows SQL with syntax highlighting (regex-based)
- `executor_eval`: Shows results table + score bar + error if any
- `retry_handler`: Shows retry count + feedback text
- `summarizer`: Shows final natural language answer

**Step 3: Implement SSE connection**

```javascript
function submitQuestion(question) {
  addUserMessage(question);
  const container = addAgentMessage();

  const url = `${API_BASE}/query/stream?question=${encodeURIComponent(question)}&dialect=sqlite`;
  const source = new EventSource(url);

  source.addEventListener("graph", (e) => {
    const data = JSON.parse(e.data);
    initGraph(data);  // draw SVG nodes
  });

  source.addEventListener("step", (e) => {
    const data = JSON.parse(e.data);
    if (!data.hidden) addStepCard(container, data);
    updateGraphNode(data.node, data.status);
  });

  source.addEventListener("done", (e) => {
    const data = JSON.parse(e.data);
    source.close();
    // Show elapsed time
  });

  source.onerror = () => { source.close(); /* show error */ };
}
```

**Step 4: Implement SQL syntax highlighting**

Lightweight regex-based highlighter — no external library:
```javascript
function highlightSQL(sql) {
  // Keywords: SELECT, FROM, WHERE, GROUP BY, ORDER BY, JOIN, etc.
  // Functions: COUNT, SUM, AVG, MAX, MIN, COALESCE, etc.
  // Strings: 'quoted values'
  // Numbers: \b\d+\b
  // Returns HTML with <span class="sql-keyword">, etc.
}
```

**Step 5: Implement results table renderer**

Converts array of row objects into an HTML `<table>`:
```javascript
function renderTable(data) {
  if (!data.length) return '<p class="text-gray-500">(empty result set)</p>';
  const cols = Object.keys(data[0]);
  // Build <thead> from cols, <tbody> from data rows
  // Limit to 50 rows with "N more rows" footer
}
```

**Step 6: Implement score bar**

```javascript
function renderScoreBar(score) {
  const pct = Math.round(score * 100);
  const color = score >= 0.7 ? 'bg-green-500' : score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500';
  return `<div class="flex items-center gap-2">
    <div class="w-48 h-3 bg-gray-700 rounded-full">
      <div class="${color} h-3 rounded-full" style="width:${pct}%"></div>
    </div>
    <span class="text-sm">${pct}%</span>
  </div>`;
}
```

**Step 7: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add interactive playground frontend with chat UI"
```

---

## Task 3: Implement the SVG graph visualization

**Files:**
- Modify: `frontend/index.html` (JS section)

**Step 1: Draw the static pipeline graph**

When the `graph` SSE event arrives, render nodes as rounded rectangles in a top-down layout:

```
[Schema Analysis]
       │
    [Planner]
       │
  [SQL Generator]
       │
[Executor & Scorer]
    ╱       ╲
[Retry]  [Summarizer]
   └──→ [SQL Generator]  (curved retry arrow)
```

Layout algorithm:
- Fixed positions for each node (no force-directed layout needed)
- Nodes: rounded rect (120x40) with label text
- Edges: SVG `<path>` elements with arrowheads
- Retry edge: curved path with red color

```javascript
const NODE_POSITIONS = {
  schema_analyzer: { x: 150, y: 30 },
  planner:         { x: 150, y: 100 },
  query_generator: { x: 150, y: 170 },
  executor_eval:   { x: 150, y: 240 },
  retry_handler:   { x: 40,  y: 310 },
  summarizer:      { x: 260, y: 310 },
};
```

**Step 2: Implement live node state updates**

```javascript
function updateGraphNode(nodeId, status) {
  const el = document.getElementById(`node-${nodeId}`);
  if (!el) return;

  // Remove all state classes
  el.classList.remove('node-pending', 'node-running', 'node-done', 'node-error');

  // Add new state class
  if (status === 'running') el.classList.add('node-running');
  else if (status === 'done') el.classList.add('node-done');
  else if (status === 'retry' || status === 'error') el.classList.add('node-error');
}
```

CSS classes:
- `.node-pending`: gray fill, gray border
- `.node-running`: pulsing blue border (CSS animation)
- `.node-done`: green fill
- `.node-error`: red fill

**Step 3: Implement edge animation**

Edges start as dashed gray lines. When the source node completes, the edge transitions to solid with the node's color:
```javascript
function updateEdge(fromNode, toNode) {
  const edge = document.getElementById(`edge-${fromNode}-${toNode}`);
  if (edge) {
    edge.classList.remove('edge-pending');
    edge.classList.add('edge-active');
  }
}
```

**Step 4: Click-to-scroll interaction**

Clicking a graph node scrolls the chat panel to the corresponding step card:
```javascript
node.addEventListener('click', () => {
  const stepCard = document.querySelector(`[data-node="${nodeId}"]`);
  if (stepCard) stepCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
});
```

**Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add live SVG graph visualization to playground"
```

---

## Task 4: Add schema panel and polish

**Files:**
- Modify: `frontend/index.html`

**Step 1: Implement schema panel**

On page load (or when toggled), fetch `/schema` and render tables:
```javascript
async function loadSchema() {
  const res = await fetch(`${API_BASE}/schema`);
  const schema = await res.json();
  // Render each table as a collapsible section
  // Show column name, type, constraints (PK, FK, nullable)
}
```

Panel slides over the graph panel with a transition.

**Step 2: Add keyboard shortcuts**

- `Enter` in input field → submit question
- `Ctrl+K` → focus input field
- `Escape` → close schema panel

**Step 3: Add loading states**

- Pulsing dot animation next to the currently running step
- Input field disabled while a query is streaming
- Re-enable on `done` or `error`

**Step 4: Add welcome message**

On first load, show a welcome card in the chat:
```
Welcome to the Text2SQL Playground!

Type a natural language question and watch the agent:
1. Analyze the database schema
2. Plan the query strategy
3. Generate SQL
4. Execute and score the results
5. Summarize the answer

Try: "How many customers are in each city?"
```

**Step 5: Mobile responsiveness**

- Graph panel hidden by default on screens < 768px
- Toggle button shows/hides it
- Chat panel takes full width on mobile

**Step 6: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add schema panel, keyboard shortcuts, and polish"
```

---

## Task 5: Integration test

**Files:** None (manual testing)

**Step 1: Start the A2A server**

```bash
cd /Users/ash/Desktop/text2sql/eval
python -m agentx_a2a.server --port 5000
```

**Step 2: Open the frontend**

Open `frontend/index.html` in a browser. Verify:
- Dashboard layout renders (dark theme, graph + chat panels)
- Schema panel loads from `/schema`
- Graph shows pipeline nodes in correct layout

**Step 3: Submit a test question**

Type "How many customers are in each city?" and verify:
- SSE connection opens
- Graph nodes light up in sequence
- Chat shows step cards appearing in real time
- SQL is syntax-highlighted
- Results render as a table
- Score bar shows with correct color
- Final summary appears

**Step 4: Test error handling**

- Submit empty question → should show error
- Kill server mid-stream → should show connection error
- Submit while another query is running → input should be disabled
