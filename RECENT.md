# RECENT.md — Short-Term Memory

This file tracks recent Claude activity and performance on this project.
**Update it at the end of every session and check it at the start.**

---

## 2026-02-21 — Project Setup Session

**Accomplished:**
- Created root `CLAUDE.md` (overview + directory map)
- Created `agent/CLAUDE.md` with full purple agent spec:
  - A2A protocol interface definition
  - 7-dimension scoring table
  - Complex query goals (CTEs, window functions, date arithmetic, etc.)
  - Meta-update instructions and Learnings & Discoveries log
- Created this `RECENT.md` for short-term memory

**State of the codebase:**
- `eval/` — fully built, do not modify without care
- `agent/` — directory exists, CLAUDE.md only, no code yet

**Next logical steps:**
- Scaffold the agent server (`agent/server.py`)
- Implement the SQL generation logic using `claude-opus-4-6`
- Wire up the A2A protocol handler
- Run first benchmark against the green agent

**Notes on this session:**
- User wants CLAUDE.md files kept alive with learnings after long sessions
- User specifically called out complex real-world business queries as a priority
- No code was written — this was purely documentation/setup

---

<!-- Template for future entries:

## YYYY-MM-DD — [Session title]

**Accomplished:**
- ...

**What worked well:**
- ...

**What didn't work / surprises:**
- ...

**Benchmark scores (if run):**
- Overall: X%
- Hardest dimension: X

**State of the codebase:**
- ...

**Next logical steps:**
- ...

-->
