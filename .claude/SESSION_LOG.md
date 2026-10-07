# Session Log

## Threshold: messages per session
- **Threshold: 25 user messages per session.**
- Why 25: each implementation message produces large tool outputs (code, test runs). Past roughly 25 of them, the conversation context gets compacted and early details are lost. Ending the session at the threshold, and starting a fresh one that reads this log, keeps the context sharp.
- **At the threshold:** close the session with a "Handoff" note (current phase, open questions, next step), then start the next session from `.claude/CLAUDE.md` + this log.
- Every user message gets an index row. Messages that change nothing get "none" in the files column.

## Index

### Session 1: 2026-10-02 → 2026-10-05 · messages used: 25 / 25 (threshold reached: next session starts fresh)

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
| 16 | 10-05 | Build Phase 9 (advanced ML) + theory/ML.md | see entry 16 | `dd76719`…`b86c5a3` |
| 17 | 10-05 | Build Phase 10 (safety + control) | see entry 17 | `d5aa1a9`…`5e04f23` |
| 18 | 10-06 | Build Phase 11 (remaining pages + Ask NetHeal) + `./netheal` launcher; README commands | see entry 18 | `9d7a32b`…`5d6fc47` |
| 19 | 10-06 | Session log entry for msg 18, then Phase 12 (emulated network) | see entry 19 | `c3e2b36`…`a282402` + log commit |
| 20 | 10-05 | Phase 13: evaluation harness, observability, CI + Playwright | see entry 20 | `5aeba41`…(log commit) |
| 21 | 10-06 | Phase 14 (stretch): RL routing agent + Ollama offline LLM | see entry 21 | `f8eaed7`…(log commit) |
| 22 | 10-06 | Finish the two follow-ups (tick cadence, re-plan after a fix), Phase 15 demo hardening; what's left? | see entry 22 | `6b1c9e7`…(log commit) |
| 23 | 10-06 | Clean up the file structure, find all UI errors (browser + CLI), update docs for handover | see entry 23 | `a34ff78`…(log commit) |
| 24 | 10-06 | WhatsApp message for Abeer and Parth: setting the project up from GitHub | none (message text only) | none |
| 25 | 10-06 | "Where do I decide?" on an idle-uplink incident; fix it; how to switch to the emulated network | see entry 25 | `ecf6bb2`…(log commit) |

### Session 2: 2026-10-06 → 2026-10-07 · messages used: 8 / 25

| Msg | Date | Request | Files touched | Commit(s) |
|---|---|---|---|---|
| 1 | 10-06 | Session start: read the rules, project, hackathon and team | `.claude/SESSION_LOG.md` (this row) | log commit |
| 2 | 10-06 | Landing windows, Ask NetHeal redesign + round button, no "AI-native"/hyphens, 3D map default, cursor-shy blob | see entry S2·2 | `7563ed0`…(log commit) |
| 3 | 10-06 | Push; lighter blob in light mode; remove the tagline pill; blob bursts after 2 s on it and merges back; push after verifying from now on | see entry S2·3 | `b31ad98`…(log commit) |
| 4 | 10-07 | Prep for the judges: pitch + demo script (2.5 + 2.5 min), tech-stack Q&A, build process, Qualcomm usage | local `omkar-understanding/` only (not in git) | log commit |
| 5 | 10-07 | Presentation slides from the Infosys template; found and fixed Ask NetHeal falling back from Qualcomm | `services/copilot/agent.py`, `tests/test_copilot.py`; deck in `documents/` (not in git) | `c5a0043`, `02e7494`, log commit |
| 6 | 10-07 | Add Abeer Chaturvedi and Parth Mande to the deck; new colour palette for the slides only | deck in `documents/` (not in git) | log commit |
| 7 | 10-07 | "Does it self heal or only reroute?" (answered from `healer.py`: reroute/drain for physical faults, config rollback fixes misconfig; ECMP split, rate limit and quarantine are defined in contracts but not built) | none in git (local prep notes corrected) | log commit |
| 7 | 10-07 | Review Abeer's audit report; implement the safe set (security, correctness without number changes, dead code, docs) | see entry S2·7 | `14df05e`…(log commit) |
| 8 | 10-07 | WhatsApp message for Abeer about the audit changes; CI then failed → fixed a real 3D-map bug | see entry S2·8 | `4ca9fdb`…(log commit) |

### Session 3: 2026-10-07 · messages used: 3 / 25

| Msg | Date | Request | Files touched | Commit(s) |
|---|---|---|---|---|
| 1 | 10-07 | Pull Abeer's push, check it is in sync with our commits, gather context for the PPT (don't build it yet) | `.claude/SESSION_LOG.md` (this row + entry S3·1) | log commit |
| 2 | 10-07 | Fix the 2 CI failures; README with Mac and Windows commands; PPT plan (Abeer → Omkar → Parth, sales → technical) | see entry S3·2 | `eada858`, `46e583d` |
| 3 | 10-07 | Build the PPT and a script for everyone, fast | see entry S3·3 | log commit |

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

### Msg 16 · Phase 9: advanced ML + `theory/ML.md` ✅
- Request: Phase 9, plus a doc in a new folder explaining the ML. "thoery" was read as a typo for **`theory/`**; Omkar was told.
- Libraries: torch 2.14.1 (CPU-only in Docker), torch-geometric 2.8.0, mlflow 3.16.1, shap 0.52.0 (optional extra `train`), matplotlib.
- **Created:**
  - `ml/{__init__,datagen,train_gnn,train_forecast,train_lstm_ae}.py`
  - `services/ml/{__init__,graph,gnn,forecast,lstm_ae}.py`
  - `services/ml/models/{rca_gnn.pt, rca_eval.json, forecaster.joblib, forecast_eval.json, forecast_shap.png, lstm_ae.pt, lstm_ae_eval.json}`
  - `theory/ML.md`
- **Modified:**
  - `services/rca/engine.py` (`RCAEngine(gnn=...)`, `update(..., detector=)`, `_with_gnn` ensemble 0.45/0.25/0.30)
  - `services/detector/detector.py` (`forecaster=`, `autoencoder=`, forecast warnings + upgrade, LSTM-AE third opinion; `clear()` restores warm-up baselines and clears ML history)
  - `services/gateway/main.py` (loads all 3 models)
  - `frontend/src/components/dashboard/{Alerts,Diagnosis}.tsx` (forecast text, LSTM chip, GNN bar)
  - `tests/{test_rca,test_detector,test_healer}.py`
  - `pyproject.toml`, `.gitignore` (ship `services/ml/models/*.pt`), `docker/python.Dockerfile` (CPU torch), `Makefile` (`train`, `mlflow`), `.claude/launch.json` (mlflow on 5001), `README.md`, `.claude/PHASES.md`
- **Results** (held-out, all in `theory/ML.md`):
  - GNN 95.0% vs rules 90.3% vs 007-alone 1.5%; ensemble 94.7%. Flapping: GNN 83.6% vs rules 62.8%. Link failure: ensemble 100%.
  - Forecaster warns before the SLA breach on 95.9% of gradual faults (median 2.5 s), with 0 false warnings on 28,620 healthy moments. Top SHAP signal: loss change over 5 s (42%).
  - LSTM-AE: 100% fault detection, 0% false positives.
  - MLflow: 3 experiments with params, metrics and artifacts, verified in the UI at :5001.
- **Verified:** 91 tests pass; Docker image 374 MB (CPU torch); `make demo` + `make e2e` pass; live after-heal diagnosis 87% with GNN 100% (was 44% / 0%).
- Bugs found and fixed:
  1. A `multiprocessing` spawn hang on macOS when running from stdin; training now runs as modules (`python -m ml.…`).
  2. The unfair 007 baseline (voting on devices always blamed the internet gateway) was replaced with the faithful link-only 1/path-length vote.
  3. The forecaster had no history after warm-up, so its first prediction came after the breach. History is now kept from tick 1.
  4. Reset kept stale re-learned baselines and the forecaster's memory, which caused a false forecast warning. Fixed, test first.
  5. **GNN out-of-distribution after healing** ("GNN agrees: 0%"). The healer was added to the datagen.
  6. **Datagen snapshotted after healing** within the tick, unlike the live engine, so the GNN never saw "broken + unhealed". Snapshots are now taken before healing.
- Honest findings:
  - At the first instant a flapping link is physically identical to a dead link; the GNN keeps a calibrated ~50/50 belief.
  - 007 alone fails on a campus (about one flow per building).

### Msg 17 · Phase 10: safety + control ✅
- Research and decisions (Rule 3):
  - `regopy` 1.5.2 (Microsoft's Rego interpreter) runs real OPA Rego in-process (<5 ms per check), so there's no OPA sidecar and tests stay self-contained.
  - PyJWT 2.15 (HS256, 12 h) for sessions; stdlib PBKDF2-SHA256 (200k iterations, salted) for password hashes.
  - Reads and the WebSocket stay public (NOC wall-screen style); actions need roles.
- **Created:**
  - `policies/healing.rego` (6 guardrails with readable reasons)
  - `services/policy.py`, `services/auth.py`, `services/ledger/{__init__,ledger}.py`
  - `config/users.yaml` (hashes only), `config/DEMO_ACCOUNTS.md` (demo passwords; never put in the Docker image, never repeated in chat)
  - `tests/{test_policy,test_ledger,accounts}.py`
  - `frontend/src/lib/auth.ts`, `frontend/src/app/login/page.tsx`, `frontend/src/app/dashboard/{approvals,audit}/page.tsx`
- **Modified:**
  - `contracts/models.py` (`ActionCandidate.policy_reasons`, `LedgerEntry.payload`, `Envelope` type `audit`)
  - `services/bus.py` (`audit` topic)
  - `services/healer/healer.py` (Rego policy decides; `LEVELS` 0–4, `approve`/`reject`, rate-limit history)
  - `services/gateway/main.py`:
    - roles on fault/reset/report/approvals/autonomy
    - `/auth/login`, `/auth/me`, `/autonomy`, `/approvals`, `/audit`, `/audit/verify`
    - `audit()` + `handle()`; the tick loop survives exceptions
  - `tests/{test_healer,test_gateway}.py`, `tests/e2e/test_stack.py` (operator login; waits for the engine)
  - `docker/python.Dockerfile` (+policies, +hashed users, +libatomic1)
  - `pyproject.toml` (regopy, pyjwt, pytest-timeout with timeout = 120)
  - `frontend/src/lib/live.ts` (auth header, awaiting, new event kinds), `frontend/src/app/dashboard/layout.tsx`
  - `frontend/src/components/dashboard/{SelfHealing,FaultLab,Sidebar}.tsx`
  - `docs/CONTRACTS.md`, `README.md`, `.gitignore` (mlflow.db), `.claude/PHASES.md`
- **Verified:**
  - 114 tests pass. Policy: each of the 6 rules blocks with a readable reason; draining a core router escalates.
  - Levels: L0 alerts only, L1 recommends, L2 waits then heals on approve, a rejection applies nothing, L3 automates only 1-flow fixes.
  - Roles: anonymous gets 401, a viewer gets 403 on fault and approve, an operator gets 403 on autonomy; the demo login works.
  - Ledger: an edited payload, a re-hashed edit and a deleted entry are all detected.
  - Browser (Docker): signed out the Fault Lab is locked; signed in as admin, L2 → link fault → "waiting for approval" card with twin predictions → Approve → healed (MTTR 20 s, including the human) → Audit log "Integrity verified: all 20 entries untouched".
  - The e2e test is stable right after engine restarts.
- Bugs found and fixed:
  1. `summary()` assumed every list held candidates; the rebaseline list of names crashed it, which **silently killed the tick loop** and hung every test. Fixed, and the loop now logs errors and keeps running. pytest-timeout added.
  2. The image lacked `policies/`, `config/users.yaml` and `libatomic` (regopy), so the engine was unhealthy.
  3. The audit order put `incident.opened` after that tick's healing step. Now causal order (test first).
  4. The e2e test was flaky right after an engine restart (connection refused). It now waits for the engine.

### Msg 18 · Phase 11: remaining pages, Ask NetHeal, `./netheal` launcher ✅
- Requests:
  - Phase 11
  - a terminal start/stop program
  - the Ask NetHeal design based on Behance "AI Assistant SaaS" in our palette
  - (interrupted, then) "continue!" plus launcher docs in the README
- Research (Rule 3):
  - Behance viewed in the browser: dark starfield, a light beam onto a glowing logo, "How can I help you today?", a glass input with a mode chip, suggestion chips
  - Cirrascale probes: embeddings (`BAAI/bge-base-en-v1.5`, 768-d, 1.2 s) and Llama-3.3-70B tool calling (3.1 s) both work, so a real tool-using agent was built
- **Created:**
  - `services/healer/whatif.py` (`what_if()` on a twin snapshot)
  - `services/copilot/{__init__,rag,agent}.py` (doc RAG with keyword fallback; read-only tools; evidence IDs E1…; citation check → one rewrite → fallback)
  - `tests/{test_whatif,test_copilot}.py`
  - `frontend/src/app/dashboard/{copilot,whatif,insights,settings}/page.tsx`
  - `netheal` (bash launcher)
- **Modified:**
  - `services/gateway/main.py` (`POST /whatif`, `POST /copilot` (viewer+, audited), `GET /insights`, `GET /insights/shap.png`, `GET /settings`)
  - `services/auth.py` (load `.env` for a stable `JWT_SECRET`)
  - `tests/test_gateway.py`
  - `frontend/src/components/dashboard/{FaultLab,Sidebar}.tsx` (7 fire drills, auto-heal toggle L4↔L0, new nav)
  - `frontend/src/app/dashboard/layout.tsx`
  - `docker/python.Dockerfile` (+README/docs/theory for RAG)
  - `pyproject.toml`, `.gitignore` (`.netheal/`), `.env.example` (`JWT_SECRET`), `README.md` (launcher table), `.claude/PHASES.md` (Phase 11 ✅)
- **Verified:**
  - 126 tests pass
  - `./netheal restart` → `status` all green → `e2e` passes
  - browser (Docker):
    - Insights, What-If ("No safe automatic fix: NetHeal would escalate to a human" for core1) and Settings (3 models loaded, AI connected) work
    - Ask NetHeal answered "What if Core Router 1 got overloaded?" via the `what_if` tool, with hoverable evidence chips, "Llama-3.3-70B on Qualcomm Cloud AI · 3 evidence cited"
    - sessions survive an engine restart (HTTP 200)
- Bugs found and fixed:
  1. The copilot page crashed after an answer: Chrome's `scrollIntoView()` now returns a Promise, and a one-line `useEffect` returned it as "cleanup". All effects now use block bodies.
  2. The random JWT secret per engine start signed everyone out on any restart. Now there's a stable `JWT_SECRET` in `.env`.
  3. **The launcher corrupted Omkar's `.env`**: `echo >>` glued `JWT_SECRET=` onto `INFERENCE_CLOUD_ENDPOINT` (no trailing newline). Repaired (endpoint verified to end with `/apis/v2`, no values printed); `ensure_secret` now adds a newline first (tested on a scratch file).
- Notes:
  - Ask NetHeal answers take ~15–30 s (multi-round tool calls), so the UI shows rotating "thinking" text.
  - The copilot stage stays dark in light theme, matching the reference.
  - The turn ended at the usage limit; this entry was written in msg 19.

### Msg 19 · Session log for msg 18, then Phase 12: emulated network ✅
- Request: "no worries about the time, do the session log entry and then begin with the phase 12"
- Research (Rule 3):
  - Docker Desktop's kernel has Open vSwitch built in (`CONFIG_OPENVSWITCH=y`), so `ovs-ctl`'s `modprobe` fails and Mininet hangs. Fix: start `ovsdb-server` with `ovs-ctl --no-ovs-vswitchd`, then run `ovs-vswitchd` by hand.
  - os-ken controller dropped: the engine already owns path computation, so OpenFlow 1.3 rules go straight to the switches with `ovs-ofctl` (one cookie per flow, `add-flows` / `replace-flows` from a file). Less to run, same real data plane.
  - iperf3 UDP `--pacing-timer 100` (default 1000 µs) smooths the bursts that made queue-delay samples spiky.
- **Created:**
  - `emulab/Dockerfile`, `emulab/entrypoint.sh`, `emulab/agent.py` (Mininet campus from `topology/campus.yaml`; TCLink htb + netem at bandwidth × 0.01; iperf3 per flow; 10 pings per tick; faults via tc / link status / OpenFlow drop rules; `/health /reset /route /fault /clear_faults /rollback_config /telemetry`)
  - `services/netsim/emu.py` (`EmuNetwork`: simulator interface, agent-backed, simulator twin for dry runs)
  - `tests/test_emu.py` (FakeAgent, 4 tests), `tests/e2e/test_emulated.py`
- **Modified:**
  - `docker-compose.yml` (`emulab` service, profile `emu`, privileged, port 9000; engine `EMULAB_URL`)
  - `services/gateway/main.py` (`GET/POST /backend` admin switch, 409 if the emulator isn't ready, clears emulator faults when leaving emu, audited `backend.switched`; `net.step` runs in a thread)
  - `services/healer/healer.py` (`tried` / `acted` instead of `handled`: re-plan when a diagnosis is corrected before any fix)
  - `services/detector/detector.py` (latency-only anomalies need 6 of the last 8 ticks; latency floor 0.5 ms)
  - `services/ml/gnn.py:53-72` (ensemble ignores a GNN with no valid pick: NaN → 0, no "none" candidate)
  - `services/ml/models/{rca_gnn.pt,rca_eval.json,lstm_ae.pt,lstm_ae_eval.json}` (retrained for the new floor; the forecaster got worse, 85.9% with 3 false warnings, so it was kept as before)
  - `frontend/src/app/dashboard/settings/page.tsx` (`BackendCard`), `frontend/src/components/dashboard/Sidebar.tsx` (backend badge)
  - `netheal` (`./netheal emu`; `stop` also stops the emulator)
  - `tests/{test_gateway,test_healer,test_detector,test_rca}.py`
  - `README.md` (simulated vs emulated table), `docs/CONTRACTS.md` (backend + agent API), `theory/ML.md` (new numbers, persistence rule), `.claude/PHASES.md` (Phase 12 ✅)
- **Verified:**
  - emulated e2e on real packets: `MTTD 1.5 s, MTTR 4.5 s, latency 1000.0 -> 8.4 ms, loss 100% -> 0.0%`
  - `test_emulated` then `test_stack` in one run (emu → sim switch): 2 passed; no `ValidationError` in the engine log
  - 135 unit tests pass, ruff clean
  - zero false alerts over 240 s of idle emulated traffic
- Bugs found and fixed:
  1. `POST /backend` timed out: the agent's `/reset` took ~15 s (30 `ovs-ofctl` calls per route). Cookie-tagged batched rules: reset 0.49 s, reroute 0.14 s.
  2. Emulated healing never happened: a flow alert arrived before its link alert, RCA said misconfig, the healer escalated and never looked again. The healer now re-plans for a new (cause, target) unless it already acted (test first).
  3. False latency alerts on busy access links from real queue snapshots (z ≈ 20–30). EWMA alone (0.2, then 0.1) didn't fix it; the persistence rule plus the 0.5 ms floor did (test first).
  4. Switching back to the simulator left emulator faults in place: now cleared on switch.
  5. After an emu → sim switch, RCA crashed every tick building an `RCAHypothesis` with cause "none": the GNN's top pick had no valid probability. Could not reproduce in-process or against the real emulator, so it was fixed defensively in `ensemble()` with a regression test (all-zero and NaN probabilities).
- Notes:
  - One full-suite failure was seen once under emulator CPU load; reruns pass. Watch for it in Phase 13 CI.
  - Node overload is emulated as extra delay + loss on attached links; node CPU stays modelled (Mininet switches have no real CPU to load).

### Msg 20 · Phase 13: evaluation, observability, CI ✅
- Request: "go ahead with phase 13"
- Research (Rule 3):
  - PyPI: prometheus-client 0.26, opentelemetry-sdk / OTLP exporter 1.45, instrumentation-fastapi / aiokafka 0.66b0. The aiokafka instrumentation carries trace context in Kafka headers, so one trace spans engine → Redpanda → stream + sink.
  - Docker Hub: jaegertracing/jaeger 2.21.0 (takes OTLP directly, no collector needed), prom/prometheus v3.15.0, grafana/grafana 13.2.3. GitHub: actions/checkout, setup-python, setup-node, upload-artifact all at v7. npm: @playwright/test 1.63.0.
  - Plan §5 (PLAN.md) for policies and metrics. Training seeds 0..N and base seeds 101–404 are avoided, so every eval scenario is held out.
- **Created:**
  - `services/evaluator/{__init__,harness}.py` (4 policies, paired scenarios, summary + markdown); `tests/test_evaluator.py`
  - `docs/EVALUATION.md`, `docs/evaluation.json` (300 scenarios × 4 policies)
  - `services/observability.py` (metrics + opt-in tracing); `tests/test_observability.py`
  - `infra/prometheus/prometheus.yml`, `infra/grafana/provisioning/{datasources,dashboards}/*.yml`, `infra/grafana/dashboards/netheal.json` (12 panels)
  - `frontend/src/app/dashboard/evaluation/page.tsx` (charts with PNG export, tables, trade-off notes)
  - `frontend/playwright.config.ts`, `frontend/e2e/demo.spec.ts`
  - `.github/workflows/ci.yml` (python, frontend, then docker e2e with test_stack + Playwright)
- **Modified:**
  - `services/gateway/main.py` (stage spans/timers in `tick()`, healing/incident/MTTD/MTTR metrics, `/metrics`, `GET /evaluation`, WebSocket gauge, copilot timer)
  - `services/stream/main.py`, `services/sink/main.py` (bus message metrics, tracing)
  - `services/copilot/rag.py` (Ask NetHeal also searches `docs/EVALUATION.md`)
  - `docker-compose.yml` (profile `obs`: jaeger, prometheus, grafana; `OTEL_EXPORTER_OTLP_ENDPOINT` from `NETHEAL_OTLP`)
  - `netheal` (`obs`, `eval`; `start` keeps tracing while Jaeger runs; `stop` also stops obs)
  - `Makefile` (`make eval`), `pyproject.toml` (5 deps, `services.evaluator`)
  - `frontend/src/components/dashboard/Sidebar.tsx`, `frontend/package.json` (+`e2e` script), `frontend/.gitignore`
  - `tests/test_gateway.py`, `README.md`, `docs/CONTRACTS.md`, `.claude/PHASES.md` (Phase 13 ✅)
- **Results** (300 held-out faults; 104 hurt users without healing):
  - recovered: no healing 0%, reactive 87%, NetHeal 84%, NetHeal + prediction 84%; median MTTR 4.5 s; SLA violation 5,624 s → 918 s
  - detection 100% recall, 0 false alarms on 26 healthy runs; gradual-fault MTTD 2.5 s → 1.75 s with prediction; root cause top-1 84% (007 alone 3%)
- **Verified:**
  - 145 unit tests, ruff, eslint, `next build`
  - Playwright demo test passes on the local Docker stack
  - `./netheal obs`: all 4 Prometheus targets up; Grafana dashboard provisioned with data; one Jaeger trace per tick across netheal-engine, -stream and -sink
  - Evaluation page checked in the browser (labels/legend fixed after a first look)
  - CI green on `main` on the first run (run 37349644947: python 2 min, frontend 1 min, e2e 5 min)
- Findings and decisions:
  1. Policies were first compared on different denominators (a fast fix keeps some gradual faults from ever breaking the SLA). Fixed: every policy is judged on the faults that hurt users *without* healing (test first).
  2. Reactive recovers a few more faults than NetHeal only because it ignores the blast-radius guardrail (max 5 flows moved automatically), e.g. moving 8 flows off a flapping internet uplink. Kept the guardrail; explained in the report and on the page rather than tuning the policy to the benchmark.
  3. Overloaded access switches have no detour; every policy escalates. No rollbacks happen in the simulator because every detour around a fault works there.
  4. Prediction's measurable value is earlier detection of gradual faults; its earlier first diagnosis is wrong on 6 slow gray failures (corrected before acting).
  5. Rates are stored with 4 decimals so the report and the page round the same way (90/104 was stored as 0.865).
  6. Metrics showed the live loop at ≈1.84 ticks/s (it sleeps 0.5 s after each ~40–85 ms tick). Pre-existing, so flagged as a separate task instead of changed here.
  7. No mypy or Vitest in CI (plan listed them): the code has no type-check baseline and the frontend has no unit tests; adding them would be new scope.

### Msg 21 · Phase 14: RL routing agent + offline LLM ✅
- Request: "go ahead with phase 14". Asked for scope (AskUserQuestion): Omkar chose the **RL routing agent** and **Ollama offline LLM** with **qwen2.5:7b**; Neo4j and k3d + Helm not built; the 3D campus view already existed (Phase 3).
- Research (Rule 3):
  - RL for routing: Valadarsky et al., "Learning to Route" (HotNets 2017); DRL-TE and ENERO (deep-RL traffic engineering); safe RL by *shielding* (block unsafe actions at run time). NetHeal's twin + OPA act as the shield, so the agent only proposes.
  - PyPI: stable-baselines3 2.9.0 (no longer needs pandas/matplotlib), gymnasium 1.4.0.
  - Ollama (Homebrew 0.34.4, server 0.35.1) serves an OpenAI-compatible `/v1` API with tool calling for qwen2.5. Verified: qwen2.5:7b called `get_diagnosis` correctly through our client.
  - openai 3.24 uses `httpx2`, not `httpx` (found when the engine image crashed; see bugs).
- **Created:**
  - `services/ml/rl.py` (RoutingSpace: 237-number observation, 8 candidate paths per flow; RLPlanner; `load()`)
  - `ml/train_rl.py` (Gymnasium env: one healing decision per episode, reward = twin dry run + OPA verdict; PPO 300k steps, 8 workers; comparison with the rule planner on 600 held-out decisions; MLflow `netheal-rl-router`)
  - `services/ml/models/rl_router.zip` (1.3 MB), `services/ml/models/rl_eval.json`
- **Modified:**
  - `services/healer/healer.py` (`Healer(rl=…)`: the agent's proposal joins the candidates with `params.planner = "rl"`, twin-tested and OPA-checked like the rest; `plan(h, net, latest)`)
  - `services/llm/reports.py` (`Failover` client: cloud first, then `OLLAMA_URL`/`OLLAMA_MODEL`; responses stamped with model + provider; 3 s connect timeout via httpx2; reports carry `provider`)
  - `services/copilot/agent.py` (answers carry the serving model and `provider`)
  - `services/gateway/main.py` (loads the RL planner; `/settings` lists providers and `rl_router`; RAG embeddings use the cloud client only)
  - `services/evaluator/harness.py` (5th policy `rl` = live configuration; notes on mitigations, rollbacks, missing re-plan)
  - `docs/EVALUATION.md`, `docs/evaluation.json` (5 policies)
  - `frontend/src/app/dashboard/{evaluation,settings,copilot}/page.tsx`, `frontend/src/components/dashboard/{SelfHealing,ReportPanel}.tsx`, `frontend/src/lib/live.ts` (RL badge, provider labels, 5th policy)
  - `docker-compose.yml` (engine `OLLAMA_URL` → host, `extra_hosts` for Linux), `.env.example`, `netheal` (`ollama` command, status line, `dev` uses local Ollama)
  - `pyproject.toml` (+stable-baselines3, gymnasium), `Makefile` (`train-rl`, in `train`)
  - `tests/{test_healer,test_evaluator,test_reports,test_copilot}.py`
  - `theory/ML.md` (§6 RL agent; offline LLM; MLflow and files tables), `README.md`, `docs/CONTRACTS.md`, `.claude/PHASES.md`
- **Results:**
  - RL vs rule planner, 600 held-out decisions: fixed 80.0% vs 77.3%; twin picks the better of both 80.5%. All 21 wins are overloaded access switches, where the rules have no candidate: the agent mitigates by moving traffic onto less-loaded paths. It is worse on 3 distribution switches.
  - Evaluation, `rl` vs `predictive_twin`: recovered 85% vs 84%; escalated 12% vs 16%; SLA violation 864 s vs 918 s; node overload recovered 19% vs 12%. Rollbacks 6% (vs 0%), all ending no worse than without the agent.
  - Offline: with the cloud endpoint unroutable, Ask NetHeal answered in 26 s from qwen2.5:7b inside Docker (tools used, evidence cited, labelled "Ollama on this laptop").
- **Verified:**
  - 153 unit tests, ruff
  - `test_stack` e2e and the Playwright demo test on the rebuilt stack
  - Settings shows both models and "rl router: loaded"
  - live access-switch overload: RL proposal applied, failed the 3 s check, rolled back, escalated (shield working)
- Bugs and findings:
  1. **The emulator container was still running from Phase 12** and used about 10 cores. It slowed RL training (25 min instead of about 10) and the Phase 13 eval (17 min; 6 min without it). Stopped with `docker compose --profile emu stop emulab`.
  2. **The engine image crashed on `import httpx`**: openai 3 uses `httpx2`. Plain `httpx` only existed locally via another package, so local tests passed. Fixed by using httpx2.
  3. A first smoke test of the "local only" path still went to Cirrascale, because `load_dotenv` re-read `.env`. The cloud variables are now set to empty strings for such checks. Values were never printed.
  4. My first explanation of the RL wins was wrong ("rules move too many flows"). An episode-by-episode check showed the wins are access-switch mitigations, and the doc was corrected.
  5. The agent moves an unaffected flow in 33 of 600 decisions. Restricting it would cost 4 of its 480 fixes, so it is kept and documented.
  6. Gradually worsening overloads: a mitigation can pass verification and break later, and the healer never re-plans after a verified fix. Flagged as a separate task (needs a test plus an eval rerun).

### Msg 22 · Follow-ups + Phase 15: demo hardening ✅
- Request: "go ahead with phase 15 and make sure to complete the two running tasks, then i guess we are done with the coding part? what are the remaining tasks or the features?"
- The two follow-up chips had never been started (no sessions, worktrees or branches existed), so both were done here.
- Research (Rule 3):
  - React #418 is a hydration mismatch. Found by bisecting on a local production build with Playwright request interception (which slows script loading enough to reproduce it).
  - Web search found no specific Motion issue, so the fix is based on the bisect.
- **Follow-up 1, tick cadence:** `services/gateway/main.py` `tick_loop()` now ticks on a fixed 0.5 s cadence (no catch-up burst after a slow tick). Test: `tests/test_gateway.py::test_loop_keeps_two_ticks_per_second_when_a_tick_takes_time`.
- **Follow-up 2, re-plan after a fix:** `services/healer/healer.py` now watches a verified fix (`holding`).
  - If the fixed traffic breaks again for 6 ticks during the same incident, it emits `relapsed` and re-plans once.
  - If the cause is unclear (confidence < 0.7), it escalates right away. The first version waited forever on a 0.6 diagnosis; the test caught it.
  - `services/healer/incidents.py`: a relapse puts the incident back to "healing". The UI status text was added.
  - Tests: `test_replans_when_a_verified_fix_stops_holding`, `test_a_fix_that_keeps_holding_is_left_alone`, `test_a_clear_new_cause_after_a_relapse_is_fixed_again`.
  - Eval rerun: `rl` escalations 12% → 16% (broken mitigations now go to a human instead of a false "healed"); recovered unchanged at 85%.
- **Phase 15, created:**
  - `frontend/e2e/helpers.ts` (`blockInternet`, `signIn`, `demoPassword`)
  - `frontend/e2e/offline.spec.ts` (every page: no internet requests, no page errors)
  - `frontend/e2e/record.spec.ts` (backup video, RECORD=1)
  - `docs/DEMO.md` (checklist, 5-minute script, fallbacks, Q&A)
  - `demo/netheal-demo.webm` (1:45, gitignored)
- **Phase 15, modified:**
  - `frontend/e2e/demo.spec.ts` (internet blocked; plus the script's drills: gray failure heals, core router escalates)
  - `netheal` (`reset`, `rehearse`, `record`), `Makefile` (`reset`), `.gitignore` (`demo/`)
  - `frontend/src/components/landing/HeroCanvas.tsx` (lazy + mount after hydration)
  - `frontend/src/components/Reveal.tsx` (CSS + IntersectionObserver instead of motion; `motion` dependency removed)
  - `frontend/src/components/dashboard/FaultLab.tsx` (resync after a reset)
  - `frontend/src/components/dashboard/{Sidebar,SelfHealing,ReportPanel}.tsx`, `frontend/src/app/dashboard/layout.tsx` (phone menu, relapsed status, neutral "AI is writing" text)
  - `services/copilot/agent.py` (whole answer capped at 75 s; list_incidents before get_incident)
  - `tests/test_copilot.py`, `README.md`, `.claude/launch.json` (dev preview on :3005), `.claude/PHASES.md`
- **Verified:**
  - `./netheal rehearse`: pre-flight all green; the 2 demo tests ×5 = 10 of 10 with the internet blocked; page tour clean
  - 158 unit tests, ruff, eslint, `next build`
  - no horizontal overflow on 8 pages at 390 px and 1024 px
  - the CS Lab gray-failure drill healed 3 of 3 (MTTD 2.5 s, MTTR 9 s)
  - Ask NetHeal answers the past-incident question correctly (list_incidents → get_incident)
- Bugs found and fixed:
  1. **Landing hydration error (React #418), intermittent.**
     - A first fix for the `next/dynamic` ssr:false hero canvas wasn't enough.
     - Bisected on a production build: with Motion's `whileInView`, 1 in 4 slow loads failed; without it, 0 in 16. Replaced with a CSS fade-in.
     - This matters because a hydration error makes React re-render the page, wiping its state.
  2. **Stale alert after a reset:** the WebSocket "cleared" message could arrive before an older `/anomalies` snapshot, which then overwrote it. The dashboard now re-fetches after a reset.
  3. **Recording typed before hydration**, so the question was lost. The test now waits until Send is enabled; Ask NetHeal itself was fine (manual and probe runs).
  4. **Ask NetHeal answered "couldn't find" about a past incident** (it guessed ids). The prompt now says to list incidents first.
  5. **A whole answer could take about 200 s** with a slow cloud. It is now capped at 75 s, then a template answer.
  6. **Phone layout:** the fixed sidebar covered the screen. It is now a slide-in menu.
- Not done / known:
  - CI on GitHub could not run the Python job: GitHub Actions incident ("delays in assigning hosted runners"). Rerun when resolved.
  - Assistant times are in UTC, not IST.
  - Range citations like "[E5-E11]" aren't turned into chips.
  - A real Wi-Fi-off rehearsal on the demo laptop is still to do (`docs/DEMO.md`).

### Msg 23 · Repo cleanup, UI error sweep, handover docs ✅
- Request: "clean up the file structure… keep it compact and clean… find all the UI errors possible through the browser and through the CLI… keep the md files up to date (ML etc.) — I'll hand over the project"
- **File structure** (root: 29 → 20 visible entries):
  - `topology/campus.yaml`, `policies/healing.rego` → `config/`
  - `docker/python.Dockerfile` → `infra/`
  - `PLAN.md` → `docs/PLAN.md` (`.claude/CLAUDE.md` path updated)
  - `mlruns/` + `mlflow.db` → `data/mlflow/`: 15 absolute paths rewritten in the SQLite store; old runs and artifacts verified readable. New helper `ml/tracking.py` is used by all 4 training scripts.
  - `demo/` → `data/demo/`; pytest and ruff caches → `.cache/`; `./netheal dev` logs → `.cache/dev`
  - Makefile removed: `./netheal` is the single entry point (new: `lint`, `train [rl]`; `test`, `e2e`, `eval` and `mlflow` inlined)
  - setuptools → hatchling (no `netheal.egg-info`; the package list is just `contracts`, `services`)
  - The pptx template and colour palette moved into `documents/` (gitignored, nothing deleted)
- **UI errors, CLI:**
  - New `frontend/e2e/audit.spec.ts`: 12 pages × 3 sizes × 2 themes × 2 roles. Collects console errors and warnings, exceptions, HTTP ≥ 400, failed requests, broken links, overflow, and axe serious/critical violations.
  - New `frontend/e2e/interactions.spec.ts`: one flow per role.
  - Shared ignore list in `helpers.ts` (headless GPU, Next CSS preload, `THREE.Clock` inside R3F 9.8).
  - New command `./netheal ui-check`; `@axe-core/playwright` 4.13 added.
  - Run against both the production build and the dev server.
- **UI errors, browser:** full-page screenshots of every page in light and dark at 1280 px, reviewed visually.
- **Found and fixed:**
  1. **3D → 2D switch threw** `removeChild … not a child of this node` every time (drei `<Html>` on unmount). The 3D view now stays mounted and paused (`frameloop="never"`) once opened.
  2. **Playwright repeats ran in parallel** against the one live network, so a core-router drill landed mid fibre-cut test. Now `workers: 1`.
  3. React Flow attribution was hidden (pro-only option, dev warning). It is now shown, styled via `--xy-attribution-background-color`.
  4. The dev-only WebSocket "closed before established" warning (StrictMode double mount). Fixed in `live.ts`.
  5. Candidate table row numbers had no column spacing.
  6. Alert timeline said "Nothing yet." next to an active alert.
  7. The audit log rendered 200 rows; it now shows 50 at a time, newest first.
  8. The Insights page lacked the RL agent: `/insights` now serves `rl_eval.json` (test first) and a card was added.
  9. The report rounded 864.5 half-even to 864 while the page showed 865. Both now round half up (865 s, 5,625 s); `docs/DEMO.md` numbers updated.
- **Not fixed (known):** the landing page in the production build occasionally (≈1 in 12 headless loads) throws React #418. Not reproducible on the dev server (0 of 16) or under 6× CPU throttling. It is recoverable and there is no state to lose on the landing page; the dashboard pages showed none.
- **Docs for handover:**
  - `README.md` rewritten: real stack, measured results, layout, commands, ports, a working API example (verified)
  - `CONTRIBUTING.md`: real tooling and scopes, pre-push checks
  - `docs/PLAN.md`: marked as the original plan
  - `theory/ML.md`: MLflow location, link to the end-to-end evaluation
  - `docs/PRODUCT_OVERVIEW.md`: pages and demo list match the build; planned items marked
  - `docs/CONTRACTS.md`: every endpoint with its role (generated from the app's routes), all healing event kinds and statuses
- **Verified:**
  - `./netheal lint`; 158 unit tests; `next build`; `./netheal e2e`
  - `./netheal rehearse`: 10 of 10 + page tour
  - `./netheal ui-check`: 0 findings, all flows pass (also rerun on the final build)
  - **CI green** on `260d517` (python, frontend, Docker e2e + Playwright), after GitHub's outage ended. The first run exposed a race in `tests/e2e/test_stack.py`: it read the incident row before the sink stored the final "resolved" update. Fixed by waiting for that status.
- **Handoff:**
  - The coding phases are complete (0–15).
  - Open items:
    - the presentation (template in `documents/`)
    - a real Wi-Fi-off rehearsal on the demo laptop
    - small polish: assistant times in UTC; range citations like "[E5-E11]" not turned into chips
  - Start the next session from `.claude/CLAUDE.md` + this log.

### Msg 25 · "No action needed" incidents looked stuck ✅ + session handoff
- Omkar's screenshot: incident "Link failure · Internet Gateway ↔ Core Router 2", status resolved, with Decide/Heal/Verify showing "…" and no explanation. He asked where to decide.
- Cause (checked via the API): the link is the idle standby uplink (no flow routed via core2). The healer emitted `no_action` ("No user traffic is affected; flagged for maintenance."), but the incident timeline never recorded the decision and the page didn't show the reason.
- **Fixed:**
  - `services/healer/incidents.py`: `no_action` now marks the `decide` stage. Test first: `tests/test_healer.py::test_fault_on_idle_link_needs_no_action`.
  - `frontend/src/components/dashboard/SelfHealing.tsx`: Stepper shows Heal/Verify as "not needed" (resolved without a fix) or "to a human" (failed), with no pulse.
  - `frontend/src/app/dashboard/incidents/[id]/page.tsx`: shows "NetHeal decided: …" from the last `no_action`/`escalated` event.
- **Verified:**
  - reproduced live (link_down on internet-core2): timeline detect → diagnose → decide; screenshot of the incident page
  - 158 unit tests, lint, Playwright demo + offline tour
- Answered: humans decide on the Approvals page at comfort levels 1–3 (2 = ask approval); at 4 NetHeal applies the safest tested fix itself. Emulated network: `./netheal emu`, then Settings → Network backend (admin).

## Handoff (end of session 1)
- **State:** Phases 0–15 done, CI green, `./netheal rehearse` and `./netheal ui-check` clean. README, `docs/DEMO.md`, `theory/ML.md` and `docs/CONTRACTS.md` are up to date for Abeer and Parth.
- **Open:**
  1. the presentation (template in `documents/`)
  2. a real Wi-Fi-off rehearsal on the demo laptop
  3. cosmetic: assistant times shown in UTC; range citations ("[E5-E11]") not turned into chips; rare production-only React #418 on the landing page
- **Next session:** start from `.claude/CLAUDE.md` + this log; the presentation is the next task.

## Session 2 entries

### S2 · Msg 2 · Landing windows, Ask NetHeal redesign, copy, 3D default, blob ✅
- Request (with 3 reference screenshots):
  1. landing page: Mac-style app windows after the blob, themed with our palette
  2. Ask NetHeal: more features, blended into the background (no card), moving stars, plus a round button on the dashboard that opens it
  3. remove "AI-native" and unneeded "-" from the site
  4. the network map opens in 3D
  5. the blob avoids the cursor like a magnet, shivers on hover, and is a little darker
- Asked first (Rule 1), Omkar chose:
  - chat features: greeting + live timer only (not follow-up cards, model picker or voice)
  - a light sky version of the chat background
  - mini HTML UI inside the windows, not screenshots
- **Created:**
  - `frontend/src/components/landing/Window.tsx` (macOS window frame)
  - `frontend/src/components/landing/Showcase.tsx` (`LoopShowcase`: Control Room + Diagnosis + report windows; `ApprovalShowcase`: Approvals window)
  - `frontend/src/components/dashboard/AskButton.tsx` (round button, every dashboard page except Ask NetHeal)
- **Modified:**
  - `frontend/src/app/page.tsx`: loop section = windows + exclusive `<details name="loop">` accordion; safety section = text + Approvals window; tagline "Tested on a digital twin · Explainable"
  - `frontend/src/app/globals.css`: `--window`, `--window-bar`, `--window-shadow`, `--shape` per theme; `.sky`, `.sky-stars`, `.sky-stars-far` (two drifting layers, seamless loop, off with reduced motion)
  - `frontend/src/components/landing/HeroScene.tsx`: colour `#4f77a5`; pushed away within 1.6 units of the surface (mostly sideways: the centre is below the screen, so pushing straight away sank it out of view); on hover distort 0.35 → 0.6 plus a fast scale/position wobble (`speed` is not changed: it scales the shader clock and would jump)
  - `frontend/src/app/dashboard/copilot/page.tsx`: fixed full-area sky behind the page; "Hey, {username}. Ready to dive in?"; `WorkLog` ("Thinking for Ns" live, then "Worked for Ns · N steps" folded, listing the real tools); pill composer pinned to the bottom; theme tokens instead of hardcoded navy
  - `frontend/src/app/dashboard/layout.tsx` (AskButton), `frontend/src/components/dashboard/NetworkView.tsx` (3D default, 3D always mounted), `frontend/src/app/dashboard/page.tsx` (subtitle)
  - Copy without hyphens or dashes (kept only in "Hack-AI-Thon" and "z-score"): `layout.tsx`, `Sidebar.tsx` ("Healing", "What If planner"), `whatif`, `incidents`, `insights`, `settings`, `evaluation` ("n/a", "0 to 2 s"), `FaultLab.tsx` ("Auto heal"), `ReportPanel.tsx` ("NetHeal's own template")
  - Tests: `frontend/e2e/{helpers,interactions,record,offline}.spec.ts`
  - Docs: `docs/DEMO.md` ("Healing" table, 3D map)
- Research (Rule 3): drei `<Html>` logs "Attempted to synchronously unmount a root while React was already rendering" under StrictMode, because each label owns a React root and unmounts it in a layout effect ([react-three-a11y#52](https://github.com/pmndrs/react-three-a11y/issues/52)).
  - Measured: 18 warnings (one per label) on the dev server, the same with the old code after clicking 3D; 0 on the production build. React prints it in development only.
  - Two mount-timing experiments did not change it and were reverted. Added to the e2e ignore list with the reason.
- **Verified:**
  - browser: 3D by default and 2D still fits; blob shifts away and stays touchable; both landing sections in light and dark at 1280 px; no overflow at 390 px; Ask NetHeal in both themes (stars drift: background position changes over 2 s); a real question showed "Thinking for 5s" → "Worked for 12s · 1 step"; the round button on Incidents
  - `./netheal lint`, `next build`
  - `./netheal ui-check` on the rebuilt production container: 0 findings, all 3 flows pass
  - Playwright demo drills and the offline tour pass (the offline test was updated for the new greeting)
- Not done / notes:
  - In light mode the darker blob reads quite heavy at its base. It could take a lighter colour in light mode if Omkar prefers.
  - The "Thinking" lines while waiting are the existing canned steps; the folded "Worked for" list is the real tools.

### S2 · Msg 3 · Blob burst + merge, lighter light mode blob, no tagline pill ✅
- Request: push; make the blob lighter in light mode; remove the "Tested on a digital twin · Explainable" pill; hold the cursor on the blob for 2 s and it explodes into droplets, which merge back into one blob in its original spot once the cursor leaves; from now on push as soon as a change is tested and verified (saved to memory: `push-after-verify`).
- Pushed the 17 earlier commits first.
- **Modified:**
  - `frontend/src/app/page.tsx`: tagline pill removed
  - `frontend/src/components/ThemeToggle.tsx`: `useTheme()` exported (the toggle's existing `data-theme` subscription), reused by the blob
  - `frontend/src/components/landing/HeroScene.tsx`:
    - light mode: colour `#8fb0d6`, metalness 0.25 (at 0.65 it mostly mirrored the navy light formers, so a lighter colour alone barely showed)
    - phases `whole → burst → merging`: hover time builds up the shiver; at 2 s the blob pops (0.12 s) into 60 instanced droplets (`MeshDistortMaterial`, mostly small, a few big, flung up and sideways, then damped to a float)
    - merge starts once the cursor is off the blob's area or out of the hero (`onPointerLeave` on the Canvas wrapper div, checked in R3F's source) and at least 0.8 s after the burst; droplets fly back to the surface and shrink while the blob regrows (1.4 s)
- **Verified:**
  - a timed Playwright run (1280×800), dark and light: still whole at 1.5 s; burst at 3.6 s; merged back in place 1.7 s after the cursor left; no console errors
  - light/dark blob screenshots
  - `./netheal lint`, `next build`
  - `./netheal ui-check` on the rebuilt production container: 0 findings, 3 flows pass
  - offline tour passes

### S2 · Msg 4 · Judge prep folder (local only) ✅
- Request: the Infosys email sets 10 minutes per team: 5 min presentation + demo (suggested 2.5 + 2.5) and 5 min Q&A. Omkar asked for:
  1. an industrial, sales-style pitch that ends with a question
  2. tech-stack prep: every feature/page with its file, why each language/tool over the alternatives, how the project was prompted and built in phases, and how Qualcomm Cloud AI is used
  3. all of it in a local folder that is never pushed
- **Created (local only, excluded via `.git/info/exclude`, never committed):** `omkar-understanding/`
  - `README.md` (index, reading order)
  - `01-pitch-and-demo-script.md` (≈360-word pitch with a slide map onto the Infosys template, 3 closing questions, a 2.5 min demo table, fallbacks)
  - `02-why-us-vs-existing-tools.md`, `03-features-pages-files.md`, `04-architecture-diagrams.md` (6 Mermaid diagrams), `05-tech-choices-and-alternatives.md`, `06-how-we-built-it.md`, `07-qualcomm-ai.md`, `08-qa-bank.md` (45 questions), `09-numbers-cheatsheet.md`
- Research (Rule 3), sources cited in the files:
  - ITIC 2024: one hour of downtime costs more than $300K for over 90% of mid-size and large firms
  - New Relic 2024: median MTTR for high-impact outages is 51 min
  - Uptime Institute 2025: 50% of major network outages come from configuration/change failures
  - Microsoft HotOS 2017: gray failure
  - Juniper Marvis Actions and the Mist subscription; Cisco Catalyst Center's machine reasoning engine
  - Qualcomm Cloud AI 100 Ultra: 870 TOPS, 150 W
- Measured for the Q&A: a twin tick takes 0.18 ms; a twin dry run (3 s simulated) takes 1.27 ms; 160 pytest tests are collected today (the README still says 158).
- Corrections made while writing:
  - the old "30–60 min" claim has no source and is replaced by New Relic's 51 min
  - Q43 (learning from new faults) states that this is roadmap, not built
- Open: confirm with the Pune coordinator whether pre-built code is allowed (`docs/PLAN.md` noted this), and answer Q10 honestly either way.

### S2 · Msg 5 · Presentation deck + Qualcomm tool-call fix ✅
- Request: build the presentation slides from the Infosys template. No rules: creative, bold, professional, with the team name and every detail.
- **Deck** (12 slides, 16:9, built with pptxgenjs in the scratchpad):
  - `documents/NetHeal_Syntax_Cartel_Presentation.pptx` + `.pdf` (gitignored, like the template)
  - order follows the template: title · team · problem · solution · live proof · results · architecture · AI · comparison · future/scale/security · demo question · thank you
  - dark NetHeal palette; the template's ENG NEXT 2026 banner and Infosys logo; real dashboard screenshots in Mac-style windows (the landing page's motif); a native chart; a comparison table
  - speaker notes from the pitch script; alt text on every image (pptxgenjs otherwise writes the local file path into `descr`)
  - team details from the college's registration email: Syntax Cartel, lead Omkar Jitendra Shinde, Dr. D. Y. Patil Institute of Technology, Pimpri, Pune, lane Networks & Connectivity
  - QA: `validate.py` passed; every slide rendered and checked; fixed title alignment, slide 5/7/8/10/11 overflow and overlap, and a path leak in alt text
- **Bug found while taking screenshots:** Ask NetHeal answered from qwen2.5:7b (offline), not Qualcomm.
  - The key and endpoint were fine: `GET /models` returned 200 and a plain chat returned 200 in 1.5 s.
  - Reproduced the agent's rounds: the Cirrascale endpoint returns **HTTP 500 "Model Config not found, please contact admin"** when one assistant turn carries 2+ tool calls (3 of 3 failed; single calls 3 of 3 OK; split into single-call turns, 3 of 3 OK). The failover hid it by falling back per call.
  - **Fixed:** `services/copilot/agent.py` sends each tool call and its result as its own turn. Test first: `tests/test_copilot.py::test_parallel_tool_calls_go_back_one_per_turn`.
  - **Verified:**
    - 160 pytest tests, ruff
    - engine container rebuilt
    - 3 API questions, two of them multi-tool, answered by Llama-3.3-70B · Qualcomm Cloud AI (Cirrascale) in 10–18 s
    - Playwright user flows (3/3)
- Not done / notes:
  - one question ("Is the network healthy right now, and are there any alerts?") was answered with no tool call and no citations, because the citation check only runs when tools returned evidence. Pre-existing; candidate follow-up.
  - Abeer's and Parth's surnames are not in the deck (not in any document); add them in PowerPoint.
- Local prep folder updated: the slide map in `01-pitch-and-demo-script.md`; the bug story in `06` and `07`.

### S2 · Msg 6 · Deck: full names + new palette ✅
- Request:
  - add the full names Abeer Chaturvedi and Parth Mande
  - switch the slides (only the slides, not the app) to a new palette: FFFDF6 cream, E2D4E0 lavender, 949AB1 grey blue, 7C7E9D slate, 4C5372 ink
- **Rebuilt** `documents/NetHeal_Syntax_Cartel_Presentation.pptx` + `.pdf` (same 12 slides and content; gitignored):
  - cream content slides; dark ink title, demo and thank-you slides
  - soft blob shapes and dots from the palette art
  - lavender problem cards; ink highlight cards (engine, 85%, Qualcomm, NetHeal column)
  - full names on the team and closing slides
- Light slides use light-theme screenshots (retaken today: gray failure healed in 9.0 s, loss 4.1% → 0.05%; Ask NetHeal answered by Llama-3.3-70B on Qualcomm). The dark slides keep the dark landing and 3D map shots.
- QA:
  - `validate.py` passed; all 12 slides rendered and checked; fixed the slide 1 team line, the slide 2 circle, the slide 9 tagline centring and the slide 11 demo pill
  - names present, no placeholders, no local paths in alt text
  - layout ellipse/roundRect shapes aren't rendered by pptxgenjs, so they were removed
- Memory: `hackathon-project` now has the full names, the college and the deck palette.

### S2 · Msg 7 · Audit report: the safe set on demo day ✅
- Request: Abeer's audit (`audit_report.md`, written against `fdbd9df`): what can we implement in ~2 hours, focused on cleanup?
- **Triage:** every concrete claim was checked against the current code.
  - Confirmed: ports open to the LAN; `JWT_SECRET=change-me` kept by setup; raw assistant history; level-0 incidents marked resolved; approvals applied without re-checking; first candidate batch shown after a relapse; per-flow verification averaged; reachability muted while re-learning.
  - Not a bug: "unverified shown as rolled back" (`rolled_back` is always `not verified`).
  - Roadmap, not today: outbox/persistence, joint route optimisation, calibration, PPO redesign, OSPF/ECMP baselines, cookie sessions, lockfiles.
- Omkar chose (AskUserQuestion) the **safe set**: no change to any evaluation number on the slides.
- **Security:**
  1. `docker-compose.yml`: all 9 published ports bound to `127.0.0.1`. Verified: `lsof` shows 127.0.0.1; the LAN IP is refused on 3000/8001/5433.
  2. `services/auth.py`: `signing_secret()` refuses missing, placeholder or short secrets; `exp`, `sub` and a known role are required (else 401, not 500). `netheal` `ensure_secret` replaces placeholder or short values (tested on 5 scratch `.env` shapes); `.env.example` no longer ships `change-me`. Omkar's own `.env` was fine (64 chars, checked as booleans only).
  3. `services/gateway/main.py`: `CopilotRequest` takes `Turn` items (`user`/`assistant` only, ≤ 8000 chars, ≤ 200 items) and a 1–2000-character question; the copilot textarea has `maxLength` 2000.
  - Tests: `tests/test_auth.py` (new); `tests/test_gateway.py::test_assistant_rejects_injected_roles_and_oversized_input`
- **Correctness (no evaluation impact):**
  4. Level 0 now emits `alert_only` and the incident status is `alerted` (added to `IncidentStatus` in `contracts/models.py`; `services/healer/{healer,incidents}.py`, `services/llm/reports.py`). UI: "to a human".
  5. `Healer.approve` re-runs the twin and policy. A stale fix is refused (event and status `replanning`) and the incident is planned again.
  6. `frontend/src/components/dashboard/SelfHealing.tsx`: the latest candidate batch and decision are shown (`findLast`). Verified live on a relapse scenario: 2 batches, the latest one shown.
  - Tests: `tests/test_healer.py::test_alert_only_level_does_not_claim_the_incident_is_resolved`, `::test_an_approval_is_rechecked_against_the_network_as_it_is_now`
- **Dead code:**
  - vulture: only false positives (FastAPI routes, Pydantic fields, torch `forward`, gym spaces), plus `y_val` in `ml/train_forecast.py`, now `_`.
  - knip: 3 exports only used locally were un-exported.
  - Removed `frontend/public/` (5 unreferenced Next.js template SVGs).
  - Every Python dependency is used (`uvicorn` via the CLI).
  - `audit_report.md` moved to `documents/` (contains local Windows paths).
  - Kept, flagged: `contracts.FeatureVector` (defined, documented and tested, but never produced; it is a public contract, so it needs a decision).
- **Docs:**
  - `docs/CONTRACTS.md`: statuses, events, assistant input, token rules
  - `docs/DEMO.md`: video path `data/demo/`, localhost-only dashboard
  - `README.md`: ports note, link to the limitations doc
  - new `docs/LIMITATIONS.md` (the deferred audit items, honestly stated)
- **Verified:**
  - 169 unit tests, lint, `next build`
  - `./netheal e2e`
  - `./netheal rehearse`: 10 of 10 + page tour
  - `./netheal ui-check`: 0 findings, 3 role flows, including approving at level 2
  - 36 stored evaluation runs replayed with the new code: 0 differences, so the slide numbers still hold
- **Teammates:** Abeer and Parth must run `./netheal start` once more; it replaces `change-me` in their `.env` (they will have to sign in again).

### S2 · Msg 8 · Message for Abeer; CI failure → 3D map unmount bug ✅
- Wrote the WhatsApp summary of the audit changes for Abeer (text only).
- **CI for `36f09bf` failed** in the Playwright demo test. After "Healed", the incident link was clicked but the URL stayed `/dashboard`.
  - First guess, a slow runner: gave it 15 s (`4ca9fdb`). Still failed, so that guess was wrong. The CI trace showed the incident page fetched and rendered within 1 s while the URL never changed.
  - Real cause: today's other session made **3D the default map**. Leaving the dashboard unmounts the 3D scene, and drei's `<Html>` labels threw `removeChild … not a child of this node` on every navigation. That is the same bug fixed earlier for the 3D → 2D toggle, which only covered the toggle. On CI the exception left the URL behind.
  - Why the UI check missed it: it opened every page with full loads and never navigated in-app away from a mounted 3D map.
- **Fixed:** `frontend/src/components/dashboard/Topology3DScene.tsx`: the labels render (`portal`) into an overlay div we own, laid over the canvas. Labels are visually unchanged.
- **Test:** `frontend/e2e/interactions.spec.ts` "in-app navigation": clicks every sidebar page from the live dashboard and back, failing on page errors or a stuck URL.
  - Passes on the fix.
  - Against the old scene (temporarily rebuilt) it fails with exactly the `removeChild` errors, so the test is proven to catch it.
- **Verified:** demo spec (2), interaction specs (4), **CI green on `505231f`** (python, frontend, Docker e2e + Playwright).


## Session 3 entries

### S3 · Msg 1 · Pulled Abeer's push; sync check; PPT context ✅
- Pulled `8174f27` (Abeer, "Complete guarded NetHeal simulator and publish hackathon deliverables", 105 files). Fast-forward: its parent is our `fb690e8`, so nothing of ours was dropped.
- Checked our latest fixes survived: the 3D label overlay (`Topology3DScene.tsx`) and the in-app navigation test (`interactions.spec.ts`) are kept and extended; `services/auth.py` adds a check that the token's user and role match `users.yaml`.
- **Verified locally (macOS):** 279 pytest passed, 2 skipped (emulator); ruff, eslint and `tsc --noEmit` clean. Matches `deliverables/verification.json` (Abeer ran on Windows; Docker, Mininet and live Qualcomm were not in his run).
- **CI is red** (not fixed, waiting for Omkar):
  1. `8174f27`: `tests/e2e/test_stack.py:93` expects 2 event topics, gets 3. Abeer's sink now also stores the anomaly envelopes in `events` (`services/sink/main.py`), so the assertion is stale, not a bug. That step only runs in Docker, which Abeer couldn't run.
  2. `fb690e8` (docs only): `e2e/demo.spec.ts` stayed on `/dashboard` after clicking the incident link. The same code passed on `252fea5`, so it is intermittent.
- **Evaluation numbers changed** (new harness: 7 policies, per-flow scoring, 148 impacted faults instead of 104). Policy `rl` (live config) vs `no_heal`:
  - recovered 72% vs 2% (old: 85% vs 0%); verified fix 76%; median MTTR 4.5 s; MTTD 1.5 s; 0 false alarms; 0 collateral breaches
  - SLA violation 1,991 s vs 7,647 s (−74%; old: 865 vs 5,625); p95 latency 10.2 vs 107.8 ms; escalated 24%; 8 relapses; RCA top-1 84%
  - new: `native_shortest` (OSPF-like reference) recovers 12%; 100-scenario hidden-delay stress suite: `rl` 54/92 vs `no_heal` 36/92
- Stale against the new numbers: `docs/DEMO.md:36` (85%, 865 vs 5,625 s), our deck in `documents/` (slides 6 and 12), `omkar-understanding/01` and `09`.
- New from Abeer: `deliverables/` (8-slide detection/RCA/evaluation deck, 75 s demo video, study companion HTML, verification record), `netheal.ps1` (Windows launcher), `services/storage.py` (SQLite history), `docs/LIMITATIONS.md` rewritten.

### S3 · Msg 2 · CI fixes, README, PPT plan
- `tests/e2e/test_stack.py:93`: expects 3 event topics (anomalies, rca.hypotheses, actions), matching Abeer's sink (`eada858`). Not run locally: the Docker rebuild re-downloads PyTorch because `infra/python.Dockerfile` copies the source before `pip install` (slow, also in CI; left as is). CI is the check.
- Flaky `e2e/demo.spec.ts` (`fb690e8`): the CI trace shows the incident page rendered with no page errors while the URL stayed `/dashboard`. Same code passed on `252fea5`. Cause not found yet; not changed.
- `README.md`: Quick start split into macOS/Linux (Docker, `./netheal`) and Windows (PowerShell, `netheal.ps1`) (`46e583d`).
- PPT plan: `omkar-understanding/10-ppt-plan-and-script.md` (local). Checked Parth's architecture text against the code; corrections: `engine.py` sends no UDP (maths only; the emulator uses iperf3 UDP and reports over HTTP); the loop is direct calls in one process, Redpanda carries events out; z score + Isolation Forest must agree (LSTM AE and forecaster add opinions); safety rules are now 8.
- Measured on 7 Oct: Llama 3.3 70B on Cirrascale, median of 3: first token 1.5 s, 18 tokens/s, 8.2 s for 116 tokens; bge embedding 1.2 s; Ask NetHeal through the engine 13.5 s and 14.1 s (provider Qualcomm). Twin: 0.2 ms per tick, 1.4 ms per dry run.

### S3 · Msg 3 · Deck v2 + pitch script ✅
- **Deck** `documents/NetHeal_Syntax_Cartel_Presentation_v2.pptx` + `.pdf` (gitignored; built with pptxgenjs in the scratchpad): 13 slides + 3 backup, sections per speaker (Abeer 1 to 5, Omkar 6 to 9 + live demo, Parth 10 to 13), speaker chip on every slide, native chart and tables, minimal flowcharts, no hyphens in slide text, new evaluation numbers (72% vs 2%, 4.5 s, 0 false alarms, 74% less hurt time), Claude six layers (purpose, date, model, system, trust, impact). `validate.py` passed; every slide rendered and checked; fixed title alignment, title chips overlap, a wrapped role and cut arrow labels.
- **Script** `docs/PITCH_SCRIPT.md` (new): per speaker lines, demo steps, Q&A table with owners.
- `docs/DEMO.md:36`: Evaluation line updated to the new numbers.
