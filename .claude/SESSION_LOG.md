# Session Log

## Logging threshold
> **PROPOSED, awaiting Omkar's confirmation.**
- **Log a message** when it creates, modifies or deletes at least **1 file**, or makes a decision that changes the plan, stack, roles or rules.
- **Don't log** pure Q&A or explanation messages that change nothing. Instead, add them as a one-line note under the next logged entry.
- **Size limit per entry:** ≤ 15 lines. If a message touches more than 10 files, group paths by folder.

## Index

| # | Date | Message / request | Files touched | Commit(s) |
|---|---|---|---|---|
| 1 | 2026-10-02 | Read event deck + problem statement; first plan | `PLAN.md` (v1) | (not in git yet) |
| 2 | 2026-10-04 | Research papers, prior art, learning list | none (chat only) | none |
| 3 | 2026-10-04 | Tech stack (minimal), then maximised stack + full plan | `PLAN.md` (v2) | none |
| 4 | 2026-10-04 | Push docs to repo; ownership swap; many-commits goal | `README.md`, `PLAN.md`, `CONTRIBUTING.md`, `docs/CONTRACTS.md`, `docs/RESEARCH.md`, `.gitignore` | `44ee1a3`…`dd5dc48` |
| 5 | 2026-10-04 | Non-tech product overview + flowcharts | `docs/PRODUCT_OVERVIEW.md`, `README.md` | `a975b47`, `777ced3`, `8aef28a` |
| 6 | 2026-10-04 | Rules, phases, session log set up | `.claude/CLAUDE.md`, `.claude/PHASES.md`, `.claude/SESSION_LOG.md` | see entry 6 |

---

## Entries

### #1 · 2026-10-02 · Hackathon context + first plan
- Read `documents/Hack-AI-Thon_Student_Briefing.pptx` and the two confirmation screenshots (Pune, 7 Oct, 5 + 5 min format, scoring weights).
- **Created:** `PLAN.md` (v1).
- Notes: `documents/` is private event material and is gitignored.

### #2 · 2026-10-04 · Research
- Chat only, no files. The findings were later saved into `docs/RESEARCH.md` (entry 4).

### #3 · 2026-10-04 · Tech stack and full plan
- **Modified:** `PLAN.md`, rewritten as v2 (maximised stack: Redpanda, TimescaleDB, Neo4j, PyG, OPA, MLflow, Next.js, Mininet/os-ken).
- Decision: maximise the stack (Omkar). The demo-safe fallback (Python twin + template report) is kept.

### #4 · 2026-10-04 · Repo setup
- **Created:** `README.md`, `CONTRIBUTING.md`, `docs/CONTRACTS.md`, `docs/RESEARCH.md`, `.gitignore`
- **Modified:** `PLAN.md` §6 (ownership rows, lines ~224–226) and §11 (demo roles, line ~330)
- Remote: `github.com/Omkarshinde19/Infosys-hackathon`, branch `main`.

### #5 · 2026-10-04 · Product overview
- **Created:** `docs/PRODUCT_OVERVIEW.md` (non-tech overview + 3 Mermaid flowcharts)
- **Modified:** `README.md` (reading-order list, item 0)

### #6 · 2026-10-04 · Rules + phases
- **Created:** `.claude/CLAUDE.md` (Rule 1 Karpathy, Rule 2 session logs, Rule 3 research-first), `.claude/PHASES.md` (16 phases with done-checks), `.claude/SESSION_LOG.md`
- Decision: all code is written by Omkar + Claude (not teammates) for now. Memory updated.
- Open questions: the logging threshold meaning (proposed above); whether to update the README/PLAN ownership tables; whether `colour pllate.jpeg` is the UI palette.
- Environment: macOS arm64, Python 3.13.7, Node 24.15, Docker 29.4, no `uv`.
