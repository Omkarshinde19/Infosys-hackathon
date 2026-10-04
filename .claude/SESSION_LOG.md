# Session Log

## Threshold: messages per session
- **Threshold: 25 user messages per session.**
- Why 25: each implementation message produces large tool outputs (code, test runs). Past roughly 25 of them, the conversation context gets compacted and early details are lost. Ending the session at the threshold, and starting a fresh one that reads this log, keeps the context sharp.
- **At the threshold:** close the session with a "Handoff" note (current phase, open questions, next step), then start the next session from `.claude/CLAUDE.md` + this log.
- Every user message gets an index row. Messages that change nothing get "none" in the files column.

## Index

### Session 1: 2026-10-02 → 2026-10-04 · messages used: 9 / 25

| Msg | Date | Request | Files touched | Commit(s) |
|---|---|---|---|---|
| 1 | 10-02 | Read event deck + problem statement; first plan | `PLAN.md` (v1) | none (no git yet) |
| 2 | 10-04 | Research papers, prior art, learning list | none | none |
| 3 | 10-04 | Tech stack (minimal version) | none | none |
| 4 | 10-04 | Maximised stack + full plan | `PLAN.md` (v2) | none |
| 5 | 10-04 | Push docs to repo; ownership swap; many-commits goal | `README.md`, `PLAN.md`, `CONTRIBUTING.md`, `docs/CONTRACTS.md`, `docs/RESEARCH.md`, `.gitignore` | `44ee1a3`…`dd5dc48` |
| 6 | 10-04 | Non-tech list of features and pages | none (chat) | none |
| 7 | 10-04 | Save the overview as md + flowcharts | `docs/PRODUCT_OVERVIEW.md`, `README.md` | `a975b47`, `777ced3`, `8aef28a` |
| 8 | 10-04 | Rules, phases, session log | `.claude/CLAUDE.md`, `.claude/PHASES.md`, `.claude/SESSION_LOG.md` | `9b0d3bf`…`35855d2` |
| 9 | 10-04 | Answers + build Phases 0–2 | see entry 9 | `f07092d`…(this commit) |

---

## Entries

### Msg 1 · Hackathon context + first plan
- Read `documents/Hack-AI-Thon_Student_Briefing.pptx` + the 2 confirmation screenshots (Pune, 7 Oct, 5 + 5 min format, scoring weights).
- **Created:** `PLAN.md` (v1). `documents/` is private and gitignored.

### Msg 4 · Maximised stack
- **Modified:** `PLAN.md`, rewritten as v2 (Redpanda, TimescaleDB, Neo4j, PyG, OPA, MLflow, Next.js, Mininet/os-ken). The demo-safe fallback is kept.

### Msg 5 · Repo setup
- **Created:** `README.md`, `CONTRIBUTING.md`, `docs/CONTRACTS.md`, `docs/RESEARCH.md`, `.gitignore`
- **Modified:** `PLAN.md` §6 ownership rows (~L224–226), §11 demo roles (~L330)

### Msg 7 · Product overview
- **Created:** `docs/PRODUCT_OVERVIEW.md` (+3 Mermaid flowcharts) · **Modified:** `README.md` (reading list, item 0)

### Msg 8 · Rules + phases
- **Created:** `.claude/CLAUDE.md`, `.claude/PHASES.md`, `.claude/SESSION_LOG.md`
- Decision: all code is written by Omkar + Claude (teammates aren't writing code for now). Memory updated.

### Msg 9 · Phases 0–2 built ✅
- Answers: the threshold means messages per session (set to 25, see above). Palette = `colour pllate.jpeg` (`#021024 #052659 #5483B3 #7DA0CA #C1E8FF`). The PPT is left for last. README/PLAN ownership tables are left as they are. Use installed tool versions (Python 3.13.7, Node 24.15) + the latest packages.
- **Created:**
  - `pyproject.toml`, `Makefile`, `contracts/__init__.py`, `services/__init__.py`, `services/netsim/__init__.py`, `services/gateway/__init__.py`
  - `contracts/models.py` (all contracts + `Envelope`)
  - `topology/campus.yaml` (15 nodes, 27 links, 9 flows)
  - `services/netsim/topology.py` (`load_topology`)
  - `services/netsim/engine.py` (`Network`: `step`, `inject_fault`, `set_route`, `snapshot`)
  - `services/gateway/main.py` (`/topology`, `/fault`, `/reset`, `/ws/live`)
  - `tests/test_contracts.py`, `tests/test_topology.py`, `tests/test_netsim.py`, `tests/test_gateway.py`
- **Modified:** `README.md` ("Running it" section), `.claude/PHASES.md` (status of phases 0–2; note on the snapshot design)
- **Verified:** 31 tests pass, ruff clean, real uvicorn smoke test OK.
- Decisions:
  - The simulator does **not** auto-reroute on failure. Routes change only via `set_route()` (the SDN controller role), so faults stay broken until NetHeal heals them.
  - Latency model: `base + 2ms·ρ/(1−ρ)` (M/M/1-style, capped at ρ = 0.99).
  - Rule 3 applied: Starlette deprecated `httpx` for its TestClient, so the dev dependency was switched to `httpx2`.
  - `snapshot()` (deep copy) replaces the planned `snapshot()/restore()` pair: simpler, same use.
- Next: Phase 3 (frontend). UI questions are pending with Omkar.
