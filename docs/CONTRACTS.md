# Message Contracts

Every service talks through these messages, on Redpanda topics and over the gateway WebSocket. The source of truth will be the Pydantic models in `contracts/`. This file documents them for humans.

**Conventions:** timestamps are ISO-8601 UTC strings, IDs are UUIDv4 strings, latency is in **ms**, loss in **percent (0–100)**, throughput in **Mbps**, utilization and CPU are fractions **0–1**.

## Topics

Implemented (Phase 8). Every message value is the full WebSocket envelope JSON `{ "type", "data" }`; topic map in `services/bus.py`.

| Topic | Producer | Consumers | Envelope `data` |
|---|---|---|---|
| `telemetry.raw` | engine | sink → `telemetry` hypertable, stream | `[TelemetrySample, ...]` (one tick) |
| `anomalies` | engine | sink → `anomalies`, stream | `{ raised: [Anomaly], cleared: [id] }` |
| `rca.hypotheses` | engine | sink → `events`, stream | `[RCAHypothesis, ...]` |
| `actions` | engine | sink → `events`, stream | `{ kind, payload }` |
| `incidents` | engine | sink → `incidents` (upsert), stream | `{ incident, healer_status, actions }` |
| `audit` | engine | sink → `events`, stream | `LedgerEntry` (hash-chained) |

Detection, RCA and healing run inside the engine (the healer's digital twin needs the live network state), so the per-stage topics originally planned (`telemetry.features`, `actions.proposed/applied`, `audit`) are not separate streams.

## Messages

### TelemetrySample
```json
{
  "ts": "2026-10-07T10:42:01.500Z",
  "entity_type": "link",            // link | node | flow
  "entity_id": "core1-dist2",
  "latency_ms": 4.2,
  "loss_pct": 0.1,
  "throughput_mbps": 612.0,
  "util": 0.61,
  "cpu": null,                      // nodes only
  "queue_len": 12
}
```

### FeatureVector
```json
{ "ts": "...", "entity_id": "core1-dist2", "window_s": 10,
  "features": { "latency_ewma": 4.1, "latency_z": 0.3, "loss_slope": 0.0, "util_p95": 0.66 } }
```

### Anomaly
```json
{ "id": "uuid", "ts": "...", "entity_id": "core1-library", "metric": "loss_pct",
  "value": 14.2, "baseline": 0.1, "score": 0.97,
  "detectors": ["zscore", "iforest", "lstm_ae"], "severity": "critical" }
```

### RCAHypothesis
```json
{ "id": "uuid", "incident_id": "uuid",
  "cause": "gray_failure",          // link_failure | gray_failure | congestion | node_overload | misconfig | flapping
  "target": "core1-library", "confidence": 0.94,
  "evidence": [ { "anomaly_id": "uuid", "description": "11/12 failing flows traverse core1-library", "weight": 0.6 } ],
  "method_scores": { "voting": 0.92, "bayes": 0.95, "gnn": 0.94 } }
```

### ActionCandidate
```json
{ "id": "uuid", "incident_id": "uuid",
  "type": "reroute",               // reroute | ecmp_split | rate_limit | drain_node | rollback_config | quarantine_link
  "params": { "avoid": ["core1-library"], "routes": { "library-internet": ["library", "dist2", "core1", "internet"] },
              "planner": "rl" },  // planner only on the RL agent's proposal
  "twin_prediction": { "latency_ms": 22.0, "loss_pct": 0.2, "max_util": 0.58 },
  "opa_decision": "allow", "risk_score": 0.12 }
```

### ActionResult
```json
{ "action_id": "uuid", "applied_at": "...", "verified": true, "rolled_back": false,
  "before": { "latency_ms": 180.0, "loss_pct": 14.0 }, "after": { "latency_ms": 22.0, "loss_pct": 0.2 } }
```

### Incident
```json
{ "id": "uuid", "status": "resolved",   // open | diagnosing | healing | resolved | alerted (level 0: a human was told, nothing fixed) | failed
  "opened_at": "...", "detected_at": "...", "diagnosed_at": "...", "healed_at": "...", "closed_at": "...",
  "mttd_s": 2.5, "mttr_s": 9.4, "timeline": [ { "ts": "...", "stage": "detect", "ref_id": "uuid" } ] }
```

### LedgerEntry
```json
{ "seq": 42, "ts": "...", "actor": "system", "event_type": "action.applied",
  "payload_hash": "sha256…", "prev_hash": "sha256…", "hash": "sha256…" }
```

## WebSocket (gateway → frontend)

`ws://<gateway>/ws/live` pushes envelopes:
```json
{ "type": "telemetry" | "anomaly" | "rca" | "action" | "incident" | "kpi", "data": { ... } }
```

Anomaly events carry what changed this tick:
```json
{ "type": "anomaly", "data": { "raised": [Anomaly, ...], "cleared": ["dist1-library", ...] } }
```
`GET /anomalies` returns `{ "ready": bool, "warmup_progress": 0..1, "active": [Anomaly, ...] }`. The detector learns a baseline for the first 30 s after start.

RCA events carry the full ranked diagnosis whenever it changes (an empty list means the incident is over):
```json
{ "type": "rca", "data": [RCAHypothesis, ...] }
```
`GET /rca` returns the current ranked `[RCAHypothesis, ...]`. `method_scores` holds `signature` (how strongly the telemetry matches the fault type) and `voting` (the share of affected flows whose path crosses the target).

Healing events (one per step) and the incident state after every change:
```json
{ "type": "action", "data": { "kind": "proposed" | "applied" | "rebaseline" | "result" | "no_action" | "alert_only" | "escalated"
                                   | "recommended" | "awaiting_approval" | "approved" | "rejected" | "relapsed"
                                   | "replanning",   // an approved fix failed its re-check: planning again
                              "payload": [ActionCandidate, ...] | ActionCandidate | ActionResult | "reason" } }
{ "type": "incident", "data": { "incident": Incident | null, "healer_status": "idle" | "verifying" | "healed" | "rolled_back" | "no_action_needed" | "escalated"
                                | "alert_only" | "recommended" | "awaiting_approval" | "rejected" | "relapsed"
                                | "replanning",
                                "actions": [ <action event data>, ... ] } }
```
`GET /incident` returns the same incident state. In `ActionResult.before`/`after`, `latency_ms` is averaged over the affected flows (an unreachable flow counts as 1000 ms), and `after.baseline_latency_ms` is their healthy latency.

`rebaseline` carries the link/node ids that now carry rerouted traffic; the detector re-learns their normal for 10 s instead of flagging the intended change.

## Incident history and reports (REST)

- `GET /incidents`: newest first, `[{ "incident": Incident, "root_cause": RCAHypothesis | null }]`
- `GET /incidents/{id}`: `{ "incident", "anomalies": [Anomaly], "diagnosis": [RCAHypothesis], "actions": [action event data], "report": Report | null }`
- `POST /incidents/{id}/report?refresh=false`: generates (or returns the cached) report:
  ```json
  { "markdown": "## Summary ...", "source": "llm:Llama-3.3-70B" | "llm:qwen2.5:7b" | "template",
    "provider": "Qualcomm Cloud AI (Cirrascale)" | "Ollama on this laptop" | null,
    "fallback_reason": null | "No AI credentials configured" | "AI draft failed the grounding check" | "AI unavailable (...)",
    "generated_at": "2026-10-07T10:43:12+00:00" }
  ```
LLM settings come from `.env`: `INFERENCE_CLOUD_API_KEY`, `INFERENCE_CLOUD_ENDPOINT` (Cirrascale AI Suite, OpenAI-compatible), and optional `LLM_MODEL` (default `Llama-3.3-70B`). With `OLLAMA_URL` set (Docker sets it), a local model (`OLLAMA_MODEL`, default `qwen2.5:7b`) answers when the cloud is unreachable; `POST /copilot` answers carry the same `source` and `provider` fields.

## Safety and control (Phase 10)

- **Auth:** `POST /auth/login {username, password}` returns `{ token, username, role }` (JWT, 12 h). Send `Authorization: Bearer <token>`. Roles: `viewer` < `operator` < `admin`. Reads and the WebSocket are open; `POST /fault`, `POST /reset`, `POST /incidents/{id}/report` and `POST /approvals/{id}/approve|reject` need operator; `PUT /autonomy` needs admin. Demo accounts: `config/DEMO_ACCOUNTS.md`.
- **Comfort level:** `GET /autonomy` returns `{ level, levels }`; `PUT /autonomy {level: 0-4}`.
- **Approvals:** `GET /approvals` returns `{ awaiting: ActionCandidate | null, incident_id }`. New healing event kinds: `recommended`, `awaiting_approval`, `approved`, `rejected`. The incident state gains `awaiting`.
- **Policy:** `ActionCandidate.policy_reasons` lists why `config/healing.rego` denied a fix.
- **Audit:** `GET /audit?limit=200` returns the newest `LedgerEntry` first (with `payload`); `GET /audit/verify` returns `{ valid, broken_at, entries }`.

## Network backend (Phase 12)

- `GET /backend` returns `{ kind: "sim" | "emu", emulab_url, emulab_ready }`.
- `POST /backend {kind}` (admin) swaps the network. The detector re-learns the new network's normal (30 s); the incident, diagnosis and healer state reset; audited as `backend.switched`. Returns 409 if the emulator isn't running.

**Emulab agent** (`emulab/agent.py`, port 9000, used by `services/netsim/emu.py`):

| Call | Does |
|---|---|
| `GET /health` | `{ ready, switches, hosts, links }` |
| `GET /telemetry` | `TelemetrySample` rows without `ts` (the engine stamps them) |
| `POST /reset {routes}` | clears faults; replaces every switch's OpenFlow table (~0.5 s) |
| `POST /route {flow, path}` | reroutes one flow (cookie-tagged rules, ~0.15 s) |
| `POST /fault {type, target, severity, ramp_s}` | link down / gray loss (netem) / congestion (bandwidth cut) / flapping / node overload (extra port delay; CPU modelled) / misconfig (drop rule) |
| `POST /clear_faults`, `POST /rollback_config {flow}` | undo |

## Evaluation and self-observability (Phase 13)

- `GET /evaluation` returns `docs/evaluation.json` from `./netheal eval`: `{ meta, summary: { policies, by_fault }, runs }` (404 before the first run). Policies: `no_heal`, `reactive`, `twin`, `predictive_twin`, `rl`.
- `GET /metrics` (engine, stream) and `:9464/metrics` (sink): Prometheus metrics, names in `services/observability.py`.
- Traces: OTLP to `OTEL_EXPORTER_OTLP_ENDPOINT` when set (`./netheal obs`); service names `netheal-engine`, `netheal-stream`, `netheal-sink`. The trace context travels in Kafka message headers.

## All REST endpoints (engine, http://localhost:8001)

Roles: `-` anyone, `viewer`/`operator`/`admin` need a token from `POST /auth/login` (`Authorization: Bearer …`); higher roles include lower ones. Tokens must carry `sub`, `role` and `exp`, signed with `JWT_SECRET` (the engine never signs with a missing, placeholder or short secret). Approving a fix re-tests it on the twin and the safety rules first. All ports listen on 127.0.0.1 only. Interactive docs: `/docs`.

| Method and path | Role | What |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | -, signed in | Sign in (`{token, username, role}`); who am I |
| `GET /topology` | - | Nodes, links, flows and their current routes |
| `POST /fault`, `POST /reset` | operator | Inject a fault; back to a healthy network |
| `GET /anomalies`, `GET /rca`, `GET /incident` | - | Active alerts + detector warm-up, current diagnosis, current incident + healer status |
| `GET /incidents`, `GET /incidents/{id}` | - | Incident history; one incident's full context |
| `POST /incidents/{id}/report` | operator | Generate (or return the cached) incident report |
| `GET /autonomy`, `PUT /autonomy` | -, admin | Comfort level L0–L4 |
| `GET /approvals`, `POST /approvals/{action_id}/{approve\|reject}` | -, operator | The fix waiting for a human |
| `GET /audit`, `GET /audit/verify` | - | Latest 200 ledger entries (newest first); hash-chain check |
| `POST /whatif` | - | Simulate a fault on a twin copy: impact + the plan NetHeal would follow |
| `POST /copilot` | viewer | Ask NetHeal (read-only tools, cited evidence, 75 s budget). Body: `question` (1–2000 chars), `history` of `{role: "user" \| "assistant", content}` (other roles are rejected) |
| `GET /insights`, `GET /insights/shap.png` | - | Model evaluation results (RCA, forecaster, autoencoder, RL) + session stats; SHAP plot |
| `GET /evaluation` | - | `docs/evaluation.json` |
| `GET /settings` | - | Detector settings, models loaded, LLM providers, safety policy, users |
| `GET /backend`, `POST /backend` | -, admin | Simulated or emulated network |
| `GET /metrics` | - | Prometheus metrics |
| `WS /ws/live` | - | Live events (the stream service on :8002 serves the same over Redpanda) |
