# Research and Learning Guide

What already exists, which papers matter, and what each of us should learn.

## 1. Key concepts (everyone must know)

- **MAPE-K loop:** Monitor → Analyze → Plan → Execute over shared Knowledge. It's the textbook name for our detect→diagnose→decide→heal loop. Use the term in the pitch.
- **Closed-loop automation / intent-based networking / autonomous network levels (TM Forum, ETSI ZSM):** the industry framing.
- **Network metrics:** latency, packet loss, throughput, utilization (ρ), jitter, p95.
  - Queueing delay grows roughly as `base / (1 − ρ)`, so latency explodes near 100% load. This formula drives our simulator.
- **Routing:** shortest path (Dijkstra / OSPF), ECMP (equal-cost multipath), and what a "reroute" is in SDN (controller installs new flow rules).
- **Campus topology:** core, distribution and access layers, with redundant links so an alternate path always exists.
- **Fault signatures:**
  - Link failure: throughput → 0 on the link, and every flow on it loses packets.
  - Gray failure: the link is "up" but lossy. **OSPF won't fix this, but we will.**
  - Congestion: util > 85%, latency rising, loss rising late.
  - Node overload: one node's CPU/queue is high, and all of its links degrade together.
- **Ops metrics:** MTTD (mean time to detect), MTTR (mean time to repair), precision/recall, false-positive rate.

## 2. Papers

### Must read
- **007: Democratically Finding the Cause of Packet Drops** (NSDI '18). Failing flows "vote" for the links on their path, and the most-voted link is the culprit. This is our baseline RCA. https://www.usenix.org/system/files/conference/nsdi18/nsdi18-arzani.pdf
- **Intent-driven Closed Loops for Autonomous Networks:** MAPE-K applied to networks. https://journals.riverpublishers.com/index.php/JICTS/article/view/5829

### Fault localization (RCA background)
- Sherlock: inference of multi-level dependencies (SIGCOMM '07). https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/sherlock_sigcomm_07.pdf
- NetMedic: detailed diagnosis in enterprise networks (SIGCOMM '09). https://www.sysnet.ucsd.edu/sysnet/miscpapers/netmedic-sigcomm09.pdf
- NetBouncer: active device and link failure localization (NSDI '19). https://www.usenix.org/system/files/nsdi19-tan.pdf
- Flock: accurate network fault localization at scale. https://arxiv.org/pdf/2305.03348

### AI / ML for networks
- RouteNet-Fermi: network modeling with GNNs (the basis of digital twins). https://arxiv.org/pdf/2212.12070
- RCA of anomalies in 5G RAN using GNN + Transformer. https://arxiv.org/pdf/2406.15638
- Towards Self-Healing Networks: AI-based log analytics and automated remediation (thesis). https://openrepository.aut.ac.nz/server/api/core/bitstreams/4ecc44cd-b413-4e98-bcdd-841bba636d9f/content
- Aether: network validation using agentic AI and digital twin. https://arxiv.org/pdf/2604.18233

### LLMs for incidents / RCA (backs up our LLM layer)
- Towards LLM-Based Failure Localization in Production-Scale Networks (SIGCOMM '25). https://dl.acm.org/doi/10.1145/3718958.3750505
- LLMs for Telecom RCA: evidence-grounded diagnosis. https://arxiv.org/pdf/2609.02805
- Exploring LLM-based Agents for Root Cause Analysis. https://arxiv.org/abs/2403.04123
- From Network Automation to Trustworthy Autonomous Networking in the LLM Era. https://arxiv.org/html/2608.01538
- A Survey on Intent-Based Networking. https://www.cse.wustl.edu/~jain/cse5700-25/ftp/ibn.pdf

## 3. Existing projects (know them, beat them)

| Project | What it does | What we borrow / how we differ |
|---|---|---|
| [ResiliNet](https://github.com/anushka06onu/ResiliNet) | Mininet + OVS + Ryu, LightGBM congestion forecast, SHAP, policy rerouting, FastAPI + React/Cytoscape | Borrow: **static vs reactive vs predictive** policy comparison. We add RCA across many fault types, twin dry-runs and an LLM layer |
| [Aexyron](https://github.com/Vasu-Nandan20/Aexyron---Self-Healing-AI-Network) | Containerlab/FRR, IsolationForest, causal + Bayesian RCA, OPA guardrails, L0–L4 autonomy, hash-chained audit, LLM narratives | Borrow: **autonomy levels + hash-chained ledger**. We add a full dashboard, a GNN trained on twin data, and a dual backend |
| Juniper Mist **Marvis** | Commercial "self-driving network": AI root cause, auto-remediation or "driver assist" | Cite it as proof the problem is real |
| Cisco Catalyst Center **Assurance** | KPI correlation, Machine Reasoning Engine for RCA + remediation | Cite it as proof the problem is real |
| FortiAIOps, HPE Networking AIOps | Vendor AIOps for networks | Market context |

**Our edge:** a safe, reproducible twin plus a real emulated network, the whole loop visible end-to-end, twin-validated actions, measured before/after results, and an LLM that explains but never acts.

## 4. Qualcomm Cloud AI Playground
- OpenAI-compatible HTTPS API: use the `openai` Python SDK with their base URL + API key.
- Hosts 80+ models (LLMs, embeddings, …) on Cloud AI 100 Ultra.
- Docs: https://deepwiki.com/quic/cloud-ai-sdk/2.1-cloud-ai-playground · SDK: https://github.com/quic/cloud-ai-sdk

## 5. What each of us should learn

### Omkar (frontend + LLM)
- Next.js App Router, TypeScript, Tailwind + shadcn/ui
- **React Flow** custom nodes/edges and animated edges; **ECharts** streaming line charts with markers
- Zustand + a WebSocket hook with reconnect; TanStack Query
- LLM prompting with structured JSON evidence, function/tool calling, RAG basics (embeddings + pgvector), streaming responses (SSE)

### Abeer (data + ML)
- EWMA, robust z-score (MAD), IsolationForest (scikit-learn)
- LSTM autoencoder in PyTorch; forecasting with LightGBM / Darts
- PyTorch Geometric: GraphSAGE/GAT for node/edge classification
- SHAP, GNNExplainer; MLflow tracking
- Evaluation: precision/recall/F1, confusion matrix, top-k accuracy
- **Read the 007 paper**

### Parth (network + control)
- networkx (graphs, shortest paths, edge removal); discrete-time simulation
- Mininet Python API, Open vSwitch, OpenFlow 1.3 basics, os-ken/Ryu apps (port stats, flow mods)
- `tc netem`, iperf3, `ip link`
- FastAPI + WebSockets, Pydantic v2, aiokafka
- OPA / Rego basics; Docker Compose profiles

### Roadmap-only (know enough to answer judges)
gNMI/OpenConfig, SNMP, NetFlow/sFlow, Containerlab + FRRouting, ONOS/OpenDaylight, NETCONF, Kubernetes scaling, RL for traffic engineering.
