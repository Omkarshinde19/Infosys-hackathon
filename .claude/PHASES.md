# Implementation Phases

Each phase ends with a **verifiable "done" check** (Rule 1.4). A phase can't start until the one before it is verified. After Phase 6, `main` must always run the full demo loop.

Status: ⬜ not started · 🟨 in progress · ✅ done

| # | Phase | Status |
|---|---|---|
| 0 | Foundation | ✅ |
| 1 | Network twin (simulator) | ✅ |
| 2 | Gateway + live stream | ✅ |
| 3 | Frontend shell + Live Control Room | ⬜ |
| 4 | Detection (z-score + IsolationForest) | ⬜ |
| 5 | Root cause analysis (voting + rules) | ⬜ |
| 6 | Healing (reroute, twin dry-run, verify, rollback) → **core demo loop** | ⬜ |
| 7 | Incidents + LLM reports | ⬜ |
| 8 | Data platform (Redpanda, TimescaleDB, Redis, Docker Compose) | ⬜ |
| 9 | Advanced ML (LSTM-AE, forecaster, datagen, GNN RCA, SHAP, MLflow) | ⬜ |
| 10 | Safety + control (OPA, autonomy levels, approvals, auth, audit ledger) | ⬜ |
| 11 | Remaining pages (Chaos Lab, What-If, Copilot + RAG, Insights, Settings) | ⬜ |
| 12 | Emulated network (Mininet + OVS + os-ken) | ⬜ |
| 13 | Evaluation harness + observability + CI/e2e | ⬜ |
| 14 | Stretch (RL agent, Neo4j, 3D view, Helm, Ollama) | ⬜ |
| 15 | Demo hardening | ⬜ |

---

## Phase 0: Foundation
- Monorepo folders per `PLAN.md` §8 (only the ones needed now), Python project (`pyproject.toml`, ruff, pytest), `Makefile`
- `contracts/` Pydantic models matching `docs/CONTRACTS.md`
- `topology/campus.yaml` (core ×2, distribution ×4, access ×8, redundant links)
- **Done when:** `make test` passes the contract round-trip tests, `make lint` is clean, and the topology loads into networkx with every access node having ≥ 2 paths to core.

## Phase 1: Network twin (simulator)
- Flows on shortest paths; link utilization; latency `base/(1−ρ)`; loss curve; node CPU/queue; seeded noise
- Fault injection: link down, gray failure, congestion, node overload, flapping, misconfig, gradual ramp
- `snapshot()` for twin dry-runs (returns an independent deep copy; no separate `restore()` needed)
- **Done when:** tests show (a) a healthy baseline is stable, (b) link down makes the flows through it lose packets, (c) congestion raises latency non-linearly, and (d) the same seed gives the same output.

## Phase 2: Gateway + live stream
- FastAPI app running the simulator tick loop (500 ms) as a background task
- `ws://…/ws/live` sends telemetry envelopes; REST `POST /fault`, `POST /reset`, `GET /topology`
- **Done when:** a test WebSocket client receives ≥ 2 ticks/s, and `POST /fault` changes the next ticks.

## Phase 3: Frontend shell + Live Control Room
- Next.js 15 + TS + Tailwind + shadcn/ui; the colour palette from `colour pllate.jpeg` (to confirm)
- React Flow topology (health colours, animated traffic), ECharts live latency/loss, KPI tiles, fault buttons
- **Done when:** in the browser, the map and charts update live, and clicking "inject link down" turns a link red.

## Phase 4: Detection
- EWMA + robust z-score (MAD), IsolationForest trained on the healthy warm-up, ensemble vote + debounce
- **Done when:** for each fault type, a test detects it within ≤ 3 s, with zero alerts across 5 min of healthy run.

## Phase 5: Root cause analysis
- 007-style flow voting + signature rules → ranked hypotheses with confidence + evidence
- **Done when:** a test gives the correct top-1 cause and target for every fault type in the catalogue.

## Phase 6: Healing → core demo loop ✦
- Action catalogue (reroute, ECMP split, rate-limit, drain node, quarantine, rollback config)
- Twin dry-run ranks candidates; Python guardrail checks (OPA arrives in Phase 10); verify window → commit or rollback
- MTTD / MTTR / before–after KPIs; pipeline stepper in the UI
- **Done when:** an end-to-end test shows link failure → detected → diagnosed → healed, with latency back within 10% of baseline in ≤ 15 s; a forced bad action gets rolled back; and the UI shows the whole thing.

## Phase 7: Incidents + LLM reports
- Incident model + timeline; Incidents list + Incident detail pages
- Qualcomm Cloud AI Playground client (OpenAI SDK) + Jinja2 template fallback; Markdown report + PDF export
- **Done when:** after a healed fault, "Generate report" returns a report citing real numbers, and it still works with the API key removed (fallback).

## Phase 8: Data platform
- Docker Compose (`demo` / `full` profiles): Redpanda, TimescaleDB (+pgvector), Redis
- Split the pipeline stages into services talking over topics per `docs/CONTRACTS.md`
- **Done when:** `make demo` brings everything up from cold, the Phase 6 e2e test passes against the compose stack, and metrics persist in Timescale.

## Phase 9: Advanced ML
- Synthetic labelled dataset generator (thousands of scenarios → Parquet)
- LSTM autoencoder, forecaster (predictive alerts), GNN RCA (PyG), Bayes ensemble, SHAP / GNNExplainer, MLflow tracking
- **Done when:** on a held-out set, the RCA ensemble beats voting alone on top-1 accuracy; the forecaster warns before the SLA breach on gradual faults; and the runs are visible in MLflow.

## Phase 10: Safety + control
- OPA (Rego) guardrails; autonomy levels L0–L4; Approvals page; JWT auth + roles; hash-chained audit ledger + Audit page
- **Done when:** tests show a policy-violating action is blocked, L2 waits for approval, viewers can't inject faults, and tampering with a ledger row fails the integrity check.

## Phase 11: Remaining pages
- Chaos Lab (scenarios, severity, auto-heal toggle), What-If Planner, Ask NetHeal Copilot (read-only tools + RAG), Performance & AI Insights, Settings, Login
- **Done when:** every page in `docs/PRODUCT_OVERVIEW.md` exists and works against live data, and the Copilot answers cite evidence IDs.

## Phase 12: Emulated network
- Mininet + Open vSwitch + os-ken controller in a Linux VM/container; tc netem faults; iperf/ping telemetry; reroute via flow rules
- Backend toggle in the UI
- **Done when:** the Phase 6 e2e scenario passes on the emulated backend.

## Phase 13: Evaluation + observability + CI
- Evaluation harness (fault types × seeds × policies) → results page + charts
- Prometheus + Grafana + OpenTelemetry; GitHub Actions (lint, test, build); Playwright e2e of the demo flow
- **Done when:** `make eval` produces the results table, CI is green on `main`, and the Playwright demo test passes.

## Phase 14: Stretch
- RL routing agent (Stable-Baselines3), Neo4j topology/causal graph, 3D campus view, k3d + Helm, Ollama offline LLM

## Phase 15: Demo hardening
- Seeded demo scenarios, `make reset`, offline test (no internet), backup video, rehearsal of the 5-min script
- **Done when:** a full demo runs 5× in a row offline without a glitch.
