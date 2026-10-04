# NetHeal: Self-Healing Network Simulator

> **Team Syntax Cartel** · Infosys ENG NEXT 2026 Hack-AI-Thon · Pune, 7 Oct 2026
> Problem statement **NC-04: Self-Healing Network Simulator** (Lane: Networks & Connectivity)

An AI-native, digital-twin-driven platform that runs the full **detect → diagnose → decide → heal → verify** loop on a simulated or emulated campus network. Nothing touches live production infrastructure.

---

## The problem (in one paragraph)

A campus network (core, distribution and access switches; Library, Hostel, Labs, Admin) constantly emits telemetry: latency, packet loss, throughput, and link/device load. When something breaks (a link fails, a switch is overloaded, a path congests), humans usually spend 30–60 minutes finding and fixing it. We build a system that does this **automatically and safely**:

1. **Detect** degradation at the earliest stage (anomaly detection on streaming telemetry)
2. **Diagnose** the most likely root cause with evidence (link failure / congestion / node overload / …)
3. **Decide** on a safe corrective action (e.g. reroute around the fault), first validated on a digital twin
4. **Heal** by applying it to the network, then **verify** that latency and loss recover (or roll back)
5. **Explain** everything in plain language with an LLM (Qualcomm Cloud AI Playground): incident report + audit trail

> **Golden rule:** the LLM **never makes decisions**. Detection, diagnosis and healing are done by the simulator and the ML pipeline. The LLM only explains.

## Deliverable for the demo

A web dashboard that shows: healthy network → injected fault → automatic detection → diagnosis → self-healing reroute → visible recovery → generated incident report, with **measurable before/after latency and packet-loss metrics**.

## How we're judged

| Weight | Criterion |
|---|---|
| 30% | Working prototype (live demo) |
| 20% | AI usage & innovation |
| 15% | Problem clarity & relevance |
| 15% | Architecture & technical design |
| 10% | Future enhancements & scalability |
| 10% | Presentation & storytelling |

Format: **5 min demo + 5 min judge Q&A**.

---

## Architecture at a glance

```
 Network (Python twin  OR  Mininet + Open vSwitch + SDN controller)
        │ telemetry                                   ▲ flow rules / actions
        ▼                                             │
 Collector ──► Redpanda (Kafka) ──► Detector ──► RCA ──► Healer ──► What-If Twin + OPA guardrails
                     │                                   │
                     ├──► TimescaleDB / Neo4j / Redis     └──► Audit ledger (hash chain)
                     └──► LLM explainer + Copilot (Qualcomm Cloud AI, RAG)
                                   │
                     FastAPI gateway (REST + WebSocket)
                                   │
                     Next.js dashboard (Live NOC, Chaos Lab, Incidents, Copilot, …)
```

## Tech stack

| Layer | Tech |
|---|---|
| Network | networkx, numpy, SimPy · Mininet, Open vSwitch, os-ken/Ryu (OpenFlow 1.3) · tc netem, iperf3, stress-ng |
| Streaming & storage | Redpanda (Kafka API) · TimescaleDB + pgvector · Neo4j · Redis |
| ML / AI | scikit-learn (IsolationForest), PyTorch (LSTM autoencoder), LightGBM/Darts (forecasting), PyTorch Geometric (GNN RCA), SHAP, Stable-Baselines3 (RL, stretch), MLflow |
| Safety | Open Policy Agent (Rego) guardrails, autonomy levels L0–L4, verify-then-rollback |
| LLM | Qualcomm Cloud AI Playground (OpenAI-compatible) · RAG over runbooks · Ollama/template fallback |
| Backend | Python 3.12, FastAPI, Pydantic v2, aiokafka, pytest |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind + shadcn/ui, React Flow, ECharts, Zustand, TanStack Query, Framer Motion |
| Platform | Docker Compose (`demo` / `full` profiles), GitHub Actions, Prometheus + Grafana + OpenTelemetry |

## Team and ownership

| Member | Owns |
|---|---|
| **Omkar** (lead) | Frontend (Next.js dashboard, all pages), LLM explainer + reports + Copilot, repo/CI, integration, slides |
| **Abeer** | Data + ML: collector/features, anomaly detection ensemble, root-cause engine (voting + Bayes + GNN), synthetic data generator, evaluation harness |
| **Parth** | Network + control: campus topology, Python twin, Mininet/SDN backend, chaos/fault injector, healer + what-if twin, OPA policies, FastAPI gateway, Docker Compose |

## Docs (read in this order)

0. **[docs/PRODUCT_OVERVIEW.md](docs/PRODUCT_OVERVIEW.md)**: NetHeal explained for non-tech readers: every feature, page and deliverable, with flowcharts
1. **[PLAN.md](PLAN.md)**: the full build plan: architecture, stack, fault catalogue, message contracts, priorities, demo script, Q&A prep
2. **[docs/RESEARCH.md](docs/RESEARCH.md)**: papers, existing apps and what each of us should learn
3. **[docs/CONTRACTS.md](docs/CONTRACTS.md)**: the message formats every service must follow
4. **[CONTRIBUTING.md](CONTRIBUTING.md)**: branching, commits and PR workflow

## Repository layout (target)

```
contracts/      shared Pydantic models
topology/       campus.yaml (topology-as-code)
services/       gateway, netsim, netemu, chaos, collector, detector, rca, healer, llm, ledger, evaluator
ml/             datagen, training, models
policies/       OPA Rego
frontend/       Next.js app
infra/          docker-compose, grafana, prometheus, helm
docs/           research, contracts, runbooks (RAG corpus)
```

## Running it

```bash
make install   # create .venv and install backend deps
make test      # run all tests
make dev       # start the gateway on http://localhost:8000 (API docs at /docs)
```

Frontend (Node 24+):

```bash
cd frontend && npm install
npm run dev    # http://localhost:3000 (homepage) and /dashboard (Control Room)
```

The frontend proxies `/api/*` to the gateway (`GATEWAY_URL`, default `http://localhost:8000`) and opens the WebSocket at `NEXT_PUBLIC_GATEWAY_WS` (default `ws://localhost:8000/ws/live`).

Live telemetry: `ws://localhost:8000/ws/live`. Inject a fault with:
`curl -X POST localhost:8000/fault -H 'content-type: application/json' -d '{"type":"link_down","target":"dist1-library"}'`

Fault types: `link_down`, `gray_failure`, `congestion`, `flapping` (target a link id like `dist1-library`), `node_overload` (target a node like `dist1`), `misconfig` (target a flow like `admin-internet`). Optional: `severity` (0–1), `ramp_s` (gradual onset).
