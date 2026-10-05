# Session Log

## Threshold: messages per session
- **Threshold: 25 user messages per session.**
- Why 25: each implementation message produces large tool outputs (code, test runs). Past roughly 25 of them, the conversation context gets compacted and early details are lost. Ending the session at the threshold, and starting a fresh one that reads this log, keeps the context sharp.
- **At the threshold:** close the session with a "Handoff" note (current phase, open questions, next step), then start the next session from `.claude/CLAUDE.md` + this log.
- Every user message gets an index row. Messages that change nothing get "none" in the files column.

## Index

### Session 1: 2026-10-02 → 2026-10-05 · messages used: 15 / 25

| Msg | Date | Request | Files touched | Commit(s) |
|---|---|---|---|---|
| 1 | 10-02 | Read event deck + problem statement; first plan | `PLAN.md` (v1) | none (no git yet) |
| 2 | 10-04 | Research papers, prior art, learning list | none | none |
| 3 | 10-04 | Tech stack (minimal version) | none | none |
| 4 | 10-04 | Maximised stack + full plan | `PLAN.md` (v2) | none |
| 5 | 10-04 | Push docs to repo; ownership swap; many-commits goal | `README.md`, `PLAN.md`, `CONTRIBUTING.md`, `docs/CONTRACTS.md`, `docs/RESEARCH.md`, `.gitignore` | `44ee1a3`…`dd5dc48` |
| 6 | 10-04 | Non-tech list of features and pages | none (chat) | none |
| 7 | 10-04 | Save the overview as md + flowcharts | `docs/PRODUCT_OVERVIEW.md`, `README.md` | `a975b47`, `777ced3`, `8aef28a` |
| 8 | 10-04 | Rules, phases, session log | `.claude/CLAUDE.md`, `.claude/PHASES.md`, `.claude/SESSION_LOG.md` | `cf9137f`…`35855d2` |
| 9 | 10-04 | Answers + build Phases 0–2 | see entry 9 | `f07092d`…`852c18a` |
| 10 | 10-05 | UI answers + references; build Phase 3 (homepage + Control Room) | see entry 10 | `aec3c5b`…`bc38b8c` |
| 11 | 10-05 | Build Phase 4 (detection) | see entry 11 | `ef1dbac`…`d6d72be` |
| 12 | 10-05 | Build Phase 5 (root cause analysis) | see entry 12 | `a1b229a`…`094a23a` |
| 13 | 10-05 | Build Phase 6 (self-healing, core demo loop) | see entry 13 | `3ddb98c`…`4baa3f4` |
| 14 | 10-05 | Build Phase 7 (incidents + AI reports) | see entry 14 | `ceacd8f`…`ead2396` |
| 15 | 10-05 | Build Phase 8 (data platform, Docker) | see entry 15 | `ca94b46`…`dcc4180` |

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

### Msg 10 · Phase 3: homepage + Control Room ✅
- UI decisions (Omkar):
  - light/dark toggle
  - soft status colours that blend with the blues
  - creative 3D allowed
  - left vertical nav
  - 2D map flows left → right
  - long scrolling page with per-section navigation
  - a homepage is required
  - references: the glass card snippet + Dribbble "Trading Landing Page" (starfield + glossy liquid blob)
- Research (Rule 3):
  - Dribbble viewed in the browser (dark starfield, metallic blob rising from the bottom, centered headline, pill buttons)
  - web search for 3D topology ideas (react-three-topology, nettopo-3d)
  - read Next 16 bundled docs (`frontend/node_modules/next/dist/docs/`: version-16 upgrade, rewrites, lazy-loading, preventing-flash-before-hydration)
  - drei `Html` dev warning = known issue pmndrs/drei#2867 (React 19 StrictMode, dev-only), so no workaround added
- **Created:**
  - `frontend/` (create-next-app: Next 16.3.8, React 19.2.8, Tailwind v4)
  - `.claude/launch.json` (preview servers: gateway on 8001 because 8000 is used by another local app; frontend on 3000)
  - `frontend/src/components/{ThemeToggle,Logo,Reveal}.tsx`
  - `frontend/src/components/landing/{HeroScene,HeroCanvas}.tsx`
  - `frontend/src/components/dashboard/{Sidebar,Section,Overview,Topology2D,Topology3DScene,NetworkView,LiveChart,FaultLab}.tsx`
  - `frontend/src/lib/{live,health}.ts`
  - `frontend/src/app/dashboard/{layout,page}.tsx`
- **Modified:**
  - `frontend/src/app/{layout.tsx,page.tsx,globals.css}`, `frontend/next.config.ts` (`/api` → gateway rewrite), `frontend/package.json`
  - `README.md` (frontend run section), `.claude/PHASES.md` (Phase 3 ✅; stack line updated)
- **Verified:**
  - `tsc` clean, eslint clean, `next build` OK
  - in the browser: live map and charts, a link-down injected from the Fault Lab turns the link and the Library node coral, health drops to 62 "Degraded", and reset recovers to 99
- Decisions:
  - The 3D view is "Network Strata": layers as floating tiers, packets travelling along links.
  - Node health = the worst of its own health and the flows starting at it.
  - Network score = 0.7·mean + 0.3·min of flow health (so one dead building is visible).
  - Gateway URLs come from env (`GATEWAY_URL`, `NEXT_PUBLIC_GATEWAY_WS`).
- Not committed (left in the working folder): `colour pllate.jpeg`, `Hack-AI-Thon_Solution_Presentation_Template.pptx` (PPT left for last).

### Msg 11 · Phase 4: detection ✅
- **Created:**
  - `services/detector/__init__.py`
  - `services/detector/detector.py` (`Detector`: warm-up → robust z + IsolationForest vote → debounce)
  - `tests/test_detector.py`
  - `frontend/src/components/dashboard/Alerts.tsx`
- **Modified:**
  - `pyproject.toml` (scikit-learn 1.9.1, detector package)
  - `services/gateway/main.py` (detector runs each tick; `broadcast()`; `anomaly` envelope; `GET /anomalies`; async `/reset` broadcasts cleared alerts)
  - `tests/test_gateway.py` (anomaly stream + reset test)
  - `docs/CONTRACTS.md` (anomaly event + `/anomalies`)
  - `frontend/src/lib/live.ts` (anomalies, alertLog, detector warm-up polling)
  - `frontend/src/components/dashboard/Sidebar.tsx` (Alerts item + badge)
  - `frontend/src/app/dashboard/page.tsx` (Alerts section)
  - `.claude/PHASES.md` (Phase 4 ✅)
- **Verified:**
  - 42 backend tests pass
  - every fault type detected in ≤ 3 s; 0 false alerts over 5 healthy minutes (also checked on seeds 10–14)
  - browser: warm-up bar → gray failure shows 2 critical cards ("packet loss 10.00%, normal 0.01%", z-score + IsolationForest) → link down shows 3 "Unreachable" cards → reset shows "All clear"
- Rule 3 / decisions:
  - First version used "IsolationForest score > max warm-up score" as its threshold. Measured scores saturate around 0.7 (max warm-up 0.74), which vetoed real 12σ faults. Switched to the standard `predict()` rule (score > 0.5, Liu et al. 2008, scikit-learn `contamination="auto"`), since the z-score gate already guards against false positives. Tests went from 4 failing in 23 s to all passing in 2 s.
  - Robust z threshold 6 (stricter than the usual 3.5 for modified z-scores) plus per-metric noise floors, so healthy noise never alerts.
  - Bug found by reading the code: reset cleared server alerts silently. A test was written first, then fixed by broadcasting `cleared`.

### Msg 12 · Phase 5: root cause analysis ✅
- **Created:**
  - `services/rca/__init__.py`
  - `services/rca/engine.py` (`RCAEngine`: signature rules + 007 voting, confidence = 0.6·signature + 0.4·vote, stable `incident_id` per episode, flap history)
  - `tests/test_rca.py`
  - `frontend/src/lib/names.ts`
  - `frontend/src/components/dashboard/Diagnosis.tsx`
- **Modified:**
  - `pyproject.toml` (rca package)
  - `services/netsim/engine.py` (`_path_links` → public `path_links`)
  - `services/gateway/main.py` (RCA each tick; `rca` envelope only on change; `GET /rca`; reset clears)
  - `tests/test_gateway.py` (rca stream test)
  - `docs/CONTRACTS.md` (rca event)
  - `frontend/src/lib/live.ts` (diagnosis state)
  - `frontend/src/components/dashboard/Alerts.tsx` (uses the shared names)
  - `frontend/src/components/dashboard/Topology2D.tsx` (root-cause glow / "root cause" edge label)
  - `frontend/src/components/dashboard/Sidebar.tsx`, `frontend/src/app/dashboard/page.tsx` (Diagnosis section)
  - `.claude/PHASES.md`
- **Verified:**
  - 54 backend tests pass; correct top-1 cause + target for all 6 fault types (both congestion severities); flapping is refined from link_failure once it has flipped twice (≤ 10 s)
  - browser: "Device overload · Distribution North A · 97%", with evidence "CPU at 74% (normal 22%)" and "5 of 5 affected flows pass through it"; node glow on the map; reset shows "No active incident"; a link fault shows the "root cause" edge label
- Bug found in the browser:
  - A gray failure on the idle standby link dist4-cafeteria showed "0 of 0 affected flows" with an inflated 98%, because voting counted no flows as full agreement.
  - Test first, then fixed: voting is now neutral (0.5) and the evidence reads "No user traffic is affected yet (idle or standby path)".
- Research (Rule 3): the voting follows 007 (Arzani et al., NSDI'18) from `docs/RESEARCH.md`. The signature rules follow the fault catalogue in `PLAN.md` §3.

### Msg 13 · Phase 6: self-healing, core demo loop ✅
- **Created:**
  - `services/healer/__init__.py`
  - `services/healer/healer.py` (`Healer`: plan → twin dry-run on `net.snapshot()` → guardrails → apply → verify 3 s → commit/rollback → next/escalate)
  - `services/healer/incidents.py` (`IncidentTracker`: detect/diagnose/decide/heal/verify/rollback/close timeline, MTTD, MTTR)
  - `tests/test_healer.py`
  - `frontend/src/components/dashboard/SelfHealing.tsx`
- **Modified:**
  - `services/netsim/engine.py` (`rollback_config()`, `now`)
  - `tests/test_netsim.py`
  - `pyproject.toml`
  - `services/gateway/main.py` (`heal()` each tick, `action` + `incident` envelopes, `GET /incident`, reset closes the incident)
  - `tests/test_gateway.py` (e2e heal test; wider look-ahead in the anomaly test)
  - `docs/CONTRACTS.md`
  - `frontend/src/lib/live.ts`, `frontend/src/components/dashboard/Sidebar.tsx`, `frontend/src/app/dashboard/page.tsx`
  - `.claude/PHASES.md`
- **Verified:**
  - 67 backend tests pass. All 6 faults are healed with MTTD 1.5 s and MTTR 4.5 s (requirement ≤ 15 s), and traffic is within 10% of baseline afterwards.
  - Examples: congestion 201 → 8.3 ms and 28.6 → 0.05% loss; link down unreachable → 8.7 ms.
  - A forced bad reroute is rolled back and the routes restored; an idle-link fault needs no action; an overloaded building switch (can't be drained) escalates.
  - Browser: congestion on Hostel A gives a full green stepper, 207.4 → 9.8 ms, 33.7% → 0.06%, and 3 twin-ranked reroutes; the fastest (via Core Router 2) is applied and verified.
- Bugs found and fixed (test first):
  1. The guardrail measured peak load on every link, including the congested link being avoided, so all congestion fixes were denied. It now checks only the links the rerouted traffic uses.
  2. The tracker dropped the "verified" event when a full fix cleared the alerts on the same tick. Events are now processed before closing.
  3. MTTD was silently 0: every healthy tick wiped the fault-injection time. Found by tightening the test to MTTD ≥ 1 s.
- Notes:
  - Detect, diagnose, decide and heal all land on the same tick (+1.5 s); verify follows 3 s later.
  - After a reroute, the broken element stays flagged (alerts remain) until it is repaired; the UI says so.
  - The dashboard isn't laid out for narrow panes (~750 px) yet; noted for Phase 15.

### Msg 14 · Phase 7: incidents + AI reports ✅
- Platform: Omkar chose Cirrascale AI Suite (Qualcomm Cloud AI inference). `.env` holds `INFERENCE_CLOUD_API_KEY` and `INFERENCE_CLOUD_ENDPOINT` (gitignored; values never printed).
- Research (Rule 3):
  - Cirrascale blog (Bearer auth, `/apis/v2/completions`)
  - probed `GET /models`: llm = DeepSeek-R1-Distill-Llama-70B, Llama-3.1-8B, Llama-3.3-70B, Qwen-QwQ-32B; embedding = bge-base/large
  - `/chat/completions` is OpenAI-compatible (1.5 s), so the `openai` SDK is used with `base_url`
- **Created:**
  - `services/llm/__init__.py`
  - `services/llm/reports.py` (`make_client`, `entity_namer`, `incident_facts`, `write_report` with grounding check + timeout, `template_report`)
  - `tests/__init__.py`, `tests/test_reports.py` (fake LLM, no network)
  - `.env.example`
  - `frontend/src/components/dashboard/ReportPanel.tsx`
  - `frontend/src/app/dashboard/incidents/page.tsx`, `frontend/src/app/dashboard/incidents/[id]/page.tsx`
- **Modified:**
  - `services/healer/incidents.py` (per-incident context: anomalies, diagnosis, actions; `get()`)
  - `services/detector/detector.py` (`relearn()`: change-aware re-baselining)
  - `services/healer/healer.py` (`rebaseline` events, `_changed()`)
  - `services/gateway/main.py` (tracker context replaces `action_log`; `GET /incidents`, `GET /incidents/{id}`, `POST /incidents/{id}/report`; rebaseline → detector)
  - `tests/test_healer.py`, `tests/test_gateway.py`
  - `docs/CONTRACTS.md`, `pyproject.toml` (openai 3.24, python-dotenv 1.2)
  - `frontend/package.json` (react-markdown, remark-gfm)
  - `frontend/src/components/dashboard/{SelfHealing,Sidebar}.tsx`, `frontend/src/app/{globals.css,dashboard/layout.tsx}`
  - `README.md`, `.claude/PHASES.md`
- **Verified:**
  - 78 backend tests pass; `tsc`, eslint and `next build` clean
  - live: Llama-3.3-70B reports pass grounding in 10–15 s (congestion and link-down)
  - browser: Incidents list → detail → "Generate report" shows the loading state, then the AI report credited "Llama-3.3-70B on Qualcomm Cloud AI (Cirrascale)"
  - with no key, the template fallback is used (tested)
- Bugs found and fixed (test first):
  1. `json.dumps` escaped "↔" to `\u2194` in the facts sent to the AI. Fixed with `ensure_ascii=False`.
  2. The grounding check was too literal: it rejected an accurate draft that wrote "between Distribution North A and Hostel A". It now requires the cause name, every device name and the real MTTR.
  3. **Healing caused a false alert**: traffic moved onto an idle backup link was flagged against its idle baseline, so the incident could never close. Fixed with change-aware detection: the healer emits `rebaseline` for newly used links and nodes, and the detector re-learns their normal for 10 s.
- Decision: the template uses f-strings instead of Jinja2 (Rule 2, one less dependency).

### Msg 15 · Phase 8: data platform ✅
- Decisions (asked first, Rule 1):
  - "Event backbone": the loop stays in one `engine`, everything goes to Redpanda, and consumers are `sink` (TimescaleDB) and `stream` (WebSocket + Redis).
  - The full microservices split was rejected because the twin needs live state, it adds latency, and it's high risk with 2 days left.
  - Everything, including the frontend, runs in Docker.
- Research (Rule 3):
  - Redpanda Docker quickstart (internal/external listeners)
  - Redpanda v26 rejects `--set` on `redpanda start`; verified empirically that `--mode dev-container` already has `auto_create_topics_enabled=true`, so the flag was dropped
  - all images checked for arm64 (Redpanda v26.2.3, timescaledb latest-pg17, redis 8-alpine, python 3.13-slim, node 24-alpine)
- **Created:**
  - `services/bus.py` (topic map, `KAFKA_BOOTSTRAP`)
  - `services/sink/{__init__,main}.py` (`to_rows`, `write`, consumer group "sink")
  - `services/stream/{__init__,main}.py` (Kafka → WS fan-out, Redis `last:*` catch-up)
  - `infra/timescale/init.sql` (telemetry hypertable + anomalies/incidents/events)
  - `docker/python.Dockerfile`, `.dockerignore` (excludes `.env`, so the key is never baked into an image), `frontend/Dockerfile`, `frontend/.dockerignore`
  - `docker-compose.yml` (ports: frontend 3000, engine 8001, stream 8002, timescale 5433, redpanda 19092; 8000 avoided because another local app uses it)
  - `tests/test_sink.py`, `tests/test_stream.py`, `tests/e2e/{__init__,test_stack}.py`
- **Modified:**
  - `services/gateway/main.py` (AIOKafkaProducer in lifespan; `broadcast()` also publishes)
  - `tests/test_gateway.py` (fake producer test)
  - `pyproject.toml` (aiokafka 0.14, asyncpg 0.31, redis 8.1; sink/stream packages)
  - `Makefile` (`demo`, `down`, `logs`, `e2e`)
  - `README.md` (Docker section), `docs/CONTRACTS.md` (implemented topics), `.claude/PHASES.md`
- **Verified:**
  - 84 unit tests pass (e2e skipped without the stack)
  - `docker compose down -v` then `make demo`: all 7 containers healthy in 9 s (cached images)
  - `make e2e` passes on a fresh DB: link_down → healed incident received over the **stream** WS (via Redpanda) → `incidents` row resolved in TimescaleDB, telemetry rows, rca + action events stored
  - browser on the Docker frontend: dashboard live (health 100), with the stream service showing 1 client
  - the whole stack uses ~580 MB RAM
- Notes:
  - Docker Desktop wasn't running; Claude started it with `open -a Docker`.
  - The local dev path (`make dev` / `.claude/launch.json` on 8001) still works without Kafka.
  - Before the venue, run `make demo` once while online so the images are cached.
