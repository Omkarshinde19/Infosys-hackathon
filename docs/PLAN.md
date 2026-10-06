# Syntax Cartel: NC-04 Self-Healing Network Simulator
## Full Build Plan (v2, maximised stack)

**Event:** Infosys ENG NEXT 2026 Hack-AI-Thon, Pune (Phase 2, Hinjewadi), **Wed 7 Oct 2026**
**Team:** Omkar (lead), Abeer, Parth | DIT Pimpri | Lane: Networks & Connectivity
**Format:** 10:00–1:00 build, then **5 min demo + 5 min Q&A**. Scoring: prototype 30%, AI 20%, architecture 15%, problem 15%, roadmap 10%, storytelling 10%.

> Still ask the Pune DC coordinator (Manoj Kumar, +91 7507909977) whether pre-built code is allowed. Pre-pull every Docker image and model before event day; venue Wi-Fi is never guaranteed.

---

## 0. Product vision (one line for the pitch)

**"NetHeal: an AI-native, digital-twin-driven autonomous network operations platform."** It closes the MAPE-K loop (Monitor → Analyze → Plan → Execute) on an emulated campus network. Healing actions are **validated on a twin before they touch the network**, and every decision is **explained by an LLM and recorded in a tamper-evident audit ledger**.

### What makes it stand out from existing work (ResiliNet, Aexyron, Juniper Marvis)
1. **Two network backends behind one interface:** a fast Python digital twin, *and* a real emulated network (Mininet + Open vSwitch + SDN controller) with real packets, real pings and real iperf.
2. **Counterfactual "what-if" healing:** candidate actions are dry-run on a cloned twin, ranked by predicted recovery, and only the best safe action is applied.
3. **Layered AI:** a statistical + IsolationForest + LSTM-autoencoder detector ensemble, **GNN root cause analysis trained on labelled faults our own simulator generates**, an RL routing agent (stretch), and an LLM copilot grounded with RAG.
4. **Safety by design:** OPA policy guardrails, autonomy levels L0–L4 (from "recommend only" to "fully autonomous"), verify-then-rollback, and a human-approval mode.
5. **Measured, not claimed:** an evaluation harness that runs 100s of fault scenarios and reports MTTD, MTTR, RCA accuracy and heal success rate against a no-heal baseline.

---

## 1. Architecture

```
                         ┌───────────────────────── Frontend (Next.js) ─────────────────────────┐
                         │ Live NOC · Incidents · Chaos Lab · What-If Twin · Copilot · Audit · ML │
                         └──────────────▲───────────────────────────────▲───────────────────────┘
                                        │ WebSocket (live)              │ REST / JWT
                         ┌──────────────┴───────────────────────────────┴──────────────┐
                         │                 API Gateway (FastAPI)                         │
                         └──▲──────────▲─────────────▲────────────▲───────────▲──────────┘
                            │          │             │            │           │
   ┌────────────────────────┴──┐       │             │            │           │
   │  NETWORK LAYER             │       │             │            │           │
   │  NetworkBackend interface  │       │             │            │           │
   │   ├─ SimBackend (Python    │       │             │            │           │
   │   │   twin, networkx+numpy)│       │             │            │           │
   │   └─ EmuBackend (Mininet + │       │             │            │           │
   │       OVS + os-ken/Ryu SDN │       │             │            │           │
   │       controller, OpenFlow)│       │             │            │           │
   │  Chaos/fault injector      │       │             │            │           │
   └──────┬─────────────▲───────┘       │             │            │           │
          │ telemetry   │ flow rules    │             │            │           │
          ▼             │               │             │            │           │
   ┌────────────┐       │        ╔══════╧═════════════╧════════════╧═══════════╧═════╗
   │ Collector  │──────────────► ║          Redpanda (Kafka API) event bus            ║
   └────────────┘       │        ║ telemetry.raw · telemetry.features · anomalies ·   ║
                        │        ║ rca.hypotheses · actions.proposed · actions.applied║
                        │        ║ · incidents · audit                                ║
                        │        ╚══╤═════════╤══════════╤═══════════╤═══════════╤═══╝
                        │           ▼         ▼          ▼           ▼           ▼
                        │     ┌─────────┐ ┌───────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
                        │     │Detector │ │  RCA  │ │ Decision │ │  LLM   │ │  Audit   │
                        │     │ensemble │ │engine │ │ / Healer │ │Explainer│ │  Ledger  │
                        │     └─────────┘ └───────┘ └────┬─────┘ │+ RAG   │ │(hash     │
                        │                                │       │+Copilot│ │ chain)   │
                        │              ┌─────────────────┤       └────────┘ └──────────┘
                        │              ▼                 ▼
                        │       ┌────────────┐    ┌────────────┐
                        └───────│ What-If    │    │ OPA policy │
                                │ Twin (dry- │    │ guardrails │
                                │ run clone) │    └────────────┘
                                └────────────┘

 Storage:   TimescaleDB (metrics hypertables) + pgvector (RAG) · Neo4j (topology & causal graph) · Redis (live state, pub/sub, cache)
 ML Ops:    MLflow (experiments + model registry)  · PyTorch / PyG / scikit-learn / LightGBM / Stable-Baselines3
 Platform:  Prometheus + Grafana + OpenTelemetry (monitoring the platform itself) · Docker Compose · GitHub Actions
```

### Loop timing target
Telemetry every **500 ms**. Detection within **≤ 3 s** of fault onset. Root cause within **≤ 2 s** after that. Twin dry-run plus apply within **≤ 3 s**. Verified recovery within **≤ 10 s**. **End-to-end MTTR under 15 s.**

---

## 2. Full tech stack

### 2.1 Network layer
| Component | Tech | Purpose |
|---|---|---|
| Digital twin (SimBackend) | Python, **networkx**, **numpy**, **SimPy** (optional, discrete events) | Fast, deterministic campus model: queueing latency `d = base/(1-ρ)`, loss curve, CPU/queue per node. Used for demo safety, ML data generation and what-if |
| Emulated network (EmuBackend) | **Mininet** + **Open vSwitch** (OpenFlow 1.3) | Real Linux network namespaces, real packets, `tc netem` for delay/loss injection |
| SDN controller | **os-ken** (maintained Ryu fork) or **Ryu**; optional **ONOS** for the roadmap | Pulls port/flow stats; installs reroute flow rules; this is what "applies the heal" |
| Traffic generation | **iperf3**, **ping**, **D-ITG** (optional) | Real throughput/latency/loss flows between campus hosts |
| Chaos injector | Python + `tc netem`, `ip link set down`, `stress-ng` | Faults: link down, flapping, gray failure (partial loss), congestion surge, node CPU overload, misconfig (wrong route) |
| Topology-as-code | YAML topology file → both backends | One campus definition (core ×2, distribution ×4, access ×8, ~24 hosts across Library/Hostel/Labs/Admin/Wi-Fi) |
| Future plug-ins (roadmap only) | Containerlab + FRRouting (OSPF/BGP), gNMI/OpenConfig, SNMP, sFlow/NetFlow | "Plug in a real network" story |

**Rule:** every backend implements the same `NetworkBackend` interface (`get_topology()`, `poll_telemetry()`, `inject_fault()`, `apply_action()`, `snapshot()`, `restore()`). The rest of the platform never knows which one is running.

> **Mininet note:** it needs a Linux kernel. On macOS, run it inside an Ubuntu VM (OrbStack / Multipass / UTM) or a privileged Linux container. Set this up on day 1 and test it on the actual demo laptop. SimBackend is the guaranteed-to-work fallback.

### 2.2 Data and streaming
| Component | Tech | Purpose |
|---|---|---|
| Event bus | **Redpanda** (Kafka-API compatible, single binary, no ZooKeeper) | Decouples every pipeline stage. Gives replay of any incident |
| Client | **aiokafka** / **confluent-kafka** | Async producers and consumers |
| Schemas | **Pydantic v2** models → JSON Schema (shared `contracts` package) | One source of truth for every message |
| Time-series DB | **TimescaleDB** (Postgres) | Metric history, continuous aggregates (1s/10s/1m), incident queries |
| Vector store | **pgvector** (same Postgres) | RAG over runbooks + past incident reports |
| Graph DB | **Neo4j** | Topology + dependency/causal graph. Cypher queries like "which flows traverse link X" |
| Cache / live state | **Redis** | Current network state, WebSocket fan-out pub/sub, pre-computed alternate paths |
| Stream features | Python (pandas / **river** for online stats) | Rolling mean/std, EWMA, rate of change, cross-link correlation features |

### 2.3 AI / ML layer (the 20% criterion)
| Stage | Models | Tech |
|---|---|---|
| **Detect** (ensemble, voting) | ① EWMA + robust z-score (MAD) for instant, explainable alerts ② **IsolationForest** (multivariate per link/node) ③ **LSTM Autoencoder** (temporal reconstruction error) ④ **Forecaster** (LightGBM or N-BEATS/TFT via **Darts**) for *predictive* alerts before SLA breach | scikit-learn, **PyTorch**, LightGBM, Darts, **river** (online learning) |
| **Diagnose** (RCA) | ① **007-style flow voting** (failing flows vote for links on their path) ② **Bayesian/causal scoring** of hypotheses (link failure / gray failure / congestion / node overload / misconfig) ③ **GNN classifier** (GraphSAGE/GAT) over the topology graph with node and edge features, trained on simulator-generated labelled faults | **PyTorch Geometric**, networkx, Neo4j, **DoWhy** (optional causal) |
| **Explain the ML** | SHAP values for detector/forecaster, GNN attention/GNNExplainer for RCA | **SHAP**, PyG explain module |
| **Decide** | ① Rule-based action catalogue mapped to the root cause ② **What-if twin** dry-runs each candidate and ranks them by predicted latency/loss/utilization ③ **RL agent** (PPO) trained in the twin for traffic-engineering weights (stretch, gated by OPA) | **Stable-Baselines3**, **Gymnasium** env over SimBackend |
| **Guardrails** | Max blast radius, never isolate a building, projected util < 70%, rate-limit actions, require approval above autonomy level | **Open Policy Agent (OPA)** with Rego policies |
| **LLM layer** | Qualcomm Cloud AI Playground (OpenAI-compatible): ① per-stage live explanations ② incident report ③ **NOC Copilot chat** ("why did Library latency spike at 10:42?") using **read-only tools** (query metrics, get incident, get topology) + **RAG** over runbooks and past incidents ④ structured JSON output validated with Pydantic ⑤ groundedness check (every claim must cite an evidence ID) | `openai` SDK, **LangGraph** or plain function-calling, **sentence-transformers** for embeddings, pgvector |
| **LLM fallback** | Jinja2 templated report + local small model via **Ollama** (e.g. Llama 3.2 3B / Qwen) when offline | Ollama |
| **MLOps** | Experiment tracking, model registry, dataset versioning | **MLflow**, DVC (optional) |
| **Synthetic data generator** | Runs thousands of randomized fault scenarios in SimBackend and writes labelled telemetry windows | Python + multiprocessing → Parquet |

**Key line for the pitch:** "The LLM never touches the network. Decisions are made by deterministic and ML components under OPA guardrails. The LLM explains them and answers questions using read-only tools, citing evidence IDs."

### 2.4 Backend services (Python 3.12, all async)
| Service | Tech | Responsibility |
|---|---|---|
| `api-gateway` | **FastAPI**, Uvicorn, WebSockets, **JWT auth** (fastapi-users or Authlib), RBAC (viewer/operator/admin) | REST + live WebSocket fan-out, auth, OpenAPI docs |
| `netsim` / `netemu` | Python (+ Mininet API, os-ken app) | Network backends + chaos injector |
| `collector` | Python | Polls the backend → `telemetry.raw` → Timescale |
| `detector` | Python, PyTorch, sklearn | `telemetry.features` → `anomalies` |
| `rca` | Python, PyG, Neo4j driver | `anomalies` → `rca.hypotheses` |
| `healer` | Python, OPA client | Hypothesis → candidates → twin dry-run → OPA → apply → verify → rollback |
| `twin` | Python (SimBackend clone) | What-if API: "simulate action A for 30 s" |
| `llm` | Python, openai SDK, LangGraph | Explanations, reports, copilot, RAG indexing |
| `ledger` | Python, SHA-256 hash chain in Postgres | Immutable audit of every observation → decision → action |
| `evaluator` | Python, pytest-style harness | Batch scenario runs → metrics tables + charts |

Shared: `contracts/` (Pydantic models), `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `hypothesis` (property tests for routing safety).

### 2.5 Frontend
| Concern | Tech |
|---|---|
| Framework | **Next.js 15 (App Router) + React 19 + TypeScript** |
| UI | **Tailwind CSS** + **shadcn/ui** + **lucide-react** icons, dark NOC theme |
| Topology | **React Flow (@xyflow/react)** with custom animated edges (traffic particles, reroute highlight). Optional **react-three-fiber** 3D campus view as a wow layer |
| Charts | **Apache ECharts** (handles high-frequency streaming well) or Recharts |
| State / data | **Zustand** (live state), **TanStack Query** (REST), native WebSocket hook with reconnect |
| Animation | **Framer Motion** (pipeline stepper, incident cards) |
| Copilot | Streaming chat UI (SSE), markdown via `react-markdown` with evidence-ID chips that jump to charts |
| Reports | Markdown → PDF export (`@react-pdf/renderer` or server-side WeasyPrint) |
| Testing | **Playwright** (e2e demo flow), Vitest |

**Pages:**
1. **Live NOC:** topology map, KPI tiles (health score, MTTD, MTTR, active incidents), live latency/loss/throughput charts with fault/detect/heal markers, MAPE-K pipeline stepper.
2. **Chaos Lab:** pick a fault type, target, severity and ramp; scenario playlists; auto-heal toggle; autonomy-level selector (L0–L4).
3. **Incident view:** timeline, anomaly evidence, RCA hypotheses with confidence bars, GNN/SHAP explanation, candidate actions with twin predictions, the chosen action, before/after comparison, LLM report (download PDF).
4. **What-If Twin:** "What if link Core1–Dist2 fails during exam-results traffic?" Run it on the twin and see the predicted impact and the best pre-planned action.
5. **Copilot:** chat with the network, grounded in evidence.
6. **Audit Ledger:** hash-chained log with a "verify chain integrity" button.
7. **Model Insights:** detector scores, confusion matrix, RCA accuracy, evaluation results vs baseline.
8. **Approvals:** pending actions when autonomy is L2/L3 (human-in-the-loop).

### 2.6 Platform / DevOps
| Concern | Tech |
|---|---|
| Containers | **Docker Compose** with profiles: `demo` (sim + core services, laptop-safe), `full` (adds Mininet, Neo4j, MLflow, Grafana) |
| Orchestration (roadmap/optional) | **k3d/kind + Helm chart**: shows a scalability story |
| Self-observability | **Prometheus** (service metrics), **Grafana** (platform dashboard), **OpenTelemetry** traces across services, **Loki** (optional logs) |
| CI | **GitHub Actions**: ruff, mypy, pytest, eslint, build images, Playwright smoke test |
| Quality | pre-commit hooks, conventional commits, PR reviews between teammates |
| Config / secrets | `.env` + pydantic-settings. Never commit the Qualcomm API key |
| One-command run | `make demo` / `make full` / `make eval` / `make reset` |

---

## 3. Fault and healing catalogue

| Fault | Injection | Signature (what detector/RCA sees) | Healing actions (ranked by twin) |
|---|---|---|---|
| Link down | `ip link down` / remove edge | Throughput → 0 on the link, all flows through it lose packets, votes concentrate on one link | Reroute via alternate path; recompute ECMP |
| Gray failure (partial loss) | `tc netem loss 5–20%` | Loss up on one link, latency normal, link "up" | Reroute + quarantine link + raise its cost |
| Flapping link | Toggle up/down every few seconds | Oscillating throughput, many short anomalies | Dampen: pin traffic to a stable path, hold-down timer |
| Congestion | iperf surge on one link | Util > 85%, queueing latency rising, loss rising late | ECMP split / move elephant flows / rate-limit low-priority class (QoS) |
| Node overload | `stress-ng` / sim CPU spike | All links of node N degrade together, CPU/queue high | Drain traffic off N, shift to redundant switch |
| Misconfiguration | Install a bad flow rule (blackhole/loop) | Specific src→dst pairs fail, others fine | Roll back the last config change (config diff from ledger) |
| Gradual degradation | Slow ramp of any of the above | Forecaster crosses threshold *before* SLA breach | Pre-emptive reroute (predictive healing) |

Every action has: **pre-checks → twin dry-run → OPA allow → apply → verify window (N ticks) → commit or rollback**, all written to the ledger.

---

## 4. Message contracts (freeze these first)

```
TelemetrySample  {ts, entity_type: link|node|flow, entity_id, latency_ms, loss_pct, throughput_mbps, util, cpu, queue_len}
FeatureVector    {ts, entity_id, features: {...}, window_s}
Anomaly          {id, ts, entity_id, metric, value, baseline, score, detectors: [zscore, iforest, lstm_ae, forecast], severity}
RCAHypothesis    {id, incident_id, cause: link_failure|gray_failure|congestion|node_overload|misconfig|flapping,
                  target, confidence, evidence: [{anomaly_id, description, weight}], method_scores: {voting, bayes, gnn}}
ActionCandidate  {id, type: reroute|ecmp_split|rate_limit|drain_node|rollback_config|quarantine_link, params,
                  twin_prediction: {latency_ms, loss_pct, max_util}, opa_decision, risk_score}
ActionResult     {action_id, applied_at, verified: bool, rolled_back: bool, before: {...}, after: {...}}
Incident         {id, status, opened_at, detected_at, diagnosed_at, healed_at, closed_at, mttd_s, mttr_s, timeline: [...]}
LedgerEntry      {seq, ts, actor: system|user, event_type, payload_hash, prev_hash, hash}
```

---

## 5. Evaluation harness (proof, not claims)

- A scenario library of **7 fault types × random targets × severities × seeds**, run hundreds of times on SimBackend.
- Policies compared: **No-heal**, **Reactive rules**, **Twin-ranked (ours)**, **Predictive + twin**, **RL** (stretch).
- Metrics:
  - Detection: precision, recall, F1, false-positive rate, MTTD
  - RCA: top-1 / top-3 accuracy, for each method (voting vs Bayes vs GNN vs ensemble)
  - Healing: success rate, MTTR, rollback rate
  - SLA: SLA-violation seconds avoided, p95 latency and loss before vs after
- Output: an auto-generated results page in the dashboard plus a slide-ready chart. Example claim: "Across 500 injected faults: 97% detected, 91% top-1 RCA, median MTTR 9.4 s vs never recovering without healing." (The real numbers come from our runs.)

---

## 6. Team ownership

| Person | Owns | Deliverables |
|---|---|---|
| **Omkar (lead, frontend + LLM)** | Frontend, LLM, integration | Next.js app (all 8 pages), WebSocket client + live state, LLM explainer + incident reports + Copilot + RAG, ledger UI, PDF export, repo/CI, integration, slides + demo video |
| **Abeer (data + ML)** | Detection, RCA, evaluation | Collector + features, detector ensemble (z/IForest/LSTM-AE/forecaster), synthetic dataset generator, GNN RCA + voting + Bayes ensemble, SHAP/GNNExplainer, MLflow, evaluation harness, RL agent (stretch) |
| **Parth (network + control)** | Network layer, healing, API | Topology-as-code, SimBackend, EmuBackend (Mininet + OVS + os-ken), chaos injector, healer service, what-if twin, OPA policies, API gateway + auth + WebSocket server, Docker Compose |

**Shared:** the contracts package (everyone reviews it), the demo script, and Q&A rehearsal.
**Integration rhythm:** merge to `main` at least twice a day, with CI green before merging.

---

## 7. Build order (priority tiers keep the demo working at every point)

| Tier | Scope | "Done" means |
|---|---|---|
| **P0: Core loop** | Contracts, SimBackend, Redpanda, collector, z-score + IForest detector, voting RCA, reroute healer with verify/rollback, FastAPI WS, Live NOC page, template report | Inject a link failure, see it detected, diagnosed and healed, and watch the charts recover |
| **P1: AI depth** | LSTM-AE + forecaster, synthetic data generator, GNN RCA, Bayes ensemble, what-if twin ranking, OPA guardrails, autonomy levels, Qualcomm LLM explanations + reports, Timescale + ledger, Incident & Chaos Lab pages | All 7 faults handled. Twin predictions shown. LLM report generated |
| **P2: Real network** | EmuBackend on Mininet + OVS + os-ken, tc-netem faults, iperf/ping telemetry, flow-rule reroute | The same demo runs on real emulated packets with a backend toggle in the UI |
| **P3: Platform polish** | Copilot + RAG, Neo4j, MLflow, Prometheus/Grafana/OTel, Model Insights + evaluation page, Approvals page, PDF export, Playwright | Full product feel |
| **P4: Stretch** | RL traffic-engineering agent, 3D campus view, k3d + Helm, Ollama offline LLM | Wow factor |

**Suggested schedule:**
- **Sun 4 Oct:** P0
- **Mon 5 Oct:** P1
- **Tue 6 Oct morning:** P2 + P3
- **Tue 6 Oct evening:** freeze, rehearse, record a backup video
- **Wed 7 Oct (10–1):** P4 / polish

Never start a new tier while the tier below it is broken.

---

## 8. Repository layout

```
netheal/
├── contracts/                 # shared Pydantic models + JSON schemas
├── topology/campus.yaml       # topology-as-code
├── services/
│   ├── gateway/               # FastAPI, auth, WS
│   ├── netsim/                # SimBackend + twin
│   ├── netemu/                # Mininet topo, os-ken controller app, tc/iperf drivers
│   ├── chaos/                 # fault injector + scenario playlists
│   ├── collector/
│   ├── detector/              # zscore, iforest, lstm_ae, forecaster, ensemble
│   ├── rca/                   # voting, bayes, gnn, ensemble
│   ├── healer/                # action catalogue, planner, verifier, rollback
│   ├── llm/                   # explainer, reports, copilot, rag, prompts/
│   ├── ledger/
│   └── evaluator/
├── ml/
│   ├── datagen/               # synthetic labelled scenarios → parquet
│   ├── training/              # notebooks + scripts, logged to MLflow
│   └── models/                # exported weights (git-lfs or MLflow)
├── policies/                  # OPA Rego
├── frontend/                  # Next.js app
├── infra/
│   ├── docker-compose.yml     # profiles: demo, full
│   ├── grafana/ prometheus/ otel/
│   └── helm/                  # roadmap
├── docs/                      # architecture diagram, runbooks (also RAG corpus), slides
├── .github/workflows/ci.yml
└── Makefile                   # make demo | full | eval | reset | train
```

---

## 9. Demo script (5 minutes)

1. **0:00–0:40, the problem:** campus outages, manual troubleshooting takes 30–60 min, and nobody can safely test fixes on production. Our answer: an AI-native, self-healing platform validated on a digital twin.
2. **0:40–1:20, architecture slide:** the MAPE-K loop, layered AI, "LLM explains, never acts", and OPA guardrails.
3. **1:20–4:00, live demo:**
   - Healthy campus network: green map, traffic particles flowing.
   - Chaos Lab: inject a **gray failure** on Core1–Library (5% → 20% loss ramp). The forecaster raises an early warning before the SLA breach.
   - RCA panel: "Gray failure on Core1–Library, 94%", with the voting, Bayes and GNN scores side by side and SHAP evidence.
   - Twin ranks 3 candidate actions. OPA approves the best. The reroute animates on the map.
   - Charts recover. KPI cards show latency 180→22 ms, loss 14%→0.2%, and MTTR 9 s.
   - Click "Generate report" to show the LLM incident report. Ask the Copilot: "Why didn't you drain Dist2 instead?" It answers using the twin evidence.
   - Flip the backend toggle to show the same loop on the **Mininet real-packet network**. (Optional if time allows: run the auto-heal-off contrast.)
4. **4:00–4:30, proof:** an evaluation chart showing hundreds of faults, detection/RCA accuracy, and MTTR vs no-heal.
5. **4:30–5:00, roadmap:** gNMI/SNMP telemetry from real devices, ONOS/OpenDaylight and NETCONF actuation, Kubernetes scale-out, federated multi-campus twins, and an RL policy in production behind the guardrails.

---

## 10. Judge Q&A prep

| Question | Answer direction |
|---|---|
| Why not let the LLM decide? | Hallucination risk, no determinism, latency, auditability. The LLM gets read-only tools and must cite evidence IDs |
| How do you avoid false positives and flapping? | Ensemble voting, debounce, hysteresis, a confidence threshold, verify-then-rollback |
| What if the heal makes it worse? | Twin dry-run first, OPA blast-radius rules, a verify window, automatic rollback, all in the ledger |
| Doesn't OSPF already reroute on link failure? | Yes, for hard failures. But it **doesn't** handle gray failures, congestion or overload: links that are "up" but sick. That's our main value. In SDN mode, the controller is the routing brain |
| Where does GNN training data come from? | Our simulator generates labelled fault scenarios, which is a key advantage of having a twin |
| How does this go to production? | Swap the backend adapter (gNMI/SNMP in, NETCONF/SDN out). The pipeline stays unchanged. Start at L1 (recommend only) and graduate autonomy levels |
| Scale to 10k devices? | Kafka partitions per site, per-segment detectors, graph partitioning for RCA, horizontal pods via Helm |
| Why Qualcomm Cloud AI? | Efficient hosted inference for the explanation layer, through an OpenAI-compatible API so it's swappable. On-prem/edge Qualcomm hardware is a roadmap item for data privacy |

---

## 11. Risk register

| Risk | Mitigation |
|---|---|
| Mininet fails on the demo laptop | SimBackend is the default; EmuBackend is a toggle. Test the VM on the actual laptop by Monday |
| Venue internet down | Pre-pull all images, bundle models, Ollama/template LLM fallback, no CDN assets |
| Too many containers for the laptop's RAM | `demo` profile runs only the essentials; `full` is shown on the beefier laptop |
| Integration breaks late | Frozen contracts, CI on every PR, `make demo` smoke test, feature freeze Tue evening |
| Live demo glitch | Seeded scenarios, `make reset`, a recorded backup video, a second laptop with a clone |
| Running out of time on the 5-min demo | Script rehearsed 5+ times with a timer. Omkar drives the UI, Parth narrates the network story, Abeer handles ML questions |

## 12. Event-day checklist
- [ ] College ID, Aadhaar, 2+ laptops, chargers, mouse, HDMI/USB-C adapter, confirmation email
- [ ] Laptop make/model/serial sent to the coordinator
- [ ] All Docker images pulled; `make demo` tested offline
- [ ] `.env` with the Qualcomm key on both laptops; API tested
- [ ] Backup demo video on both laptops + phone
- [ ] Slides exported as PDF
