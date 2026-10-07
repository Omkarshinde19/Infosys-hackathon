# Message Contracts

Every service talks through these messages, on Redpanda topics and over the gateway WebSocket. The Pydantic models in `contracts/` are the executable source of truth. This file documents them for humans.

**Conventions:** timestamps are ISO-8601 UTC strings, IDs are UUIDv4 strings, latency is in **ms**, loss in **percent (0–100)**, throughput in **Mbps**, utilization and CPU are fractions. Offered load may exceed capacity, so utilization can exceed 1. Telemetry rejects negative/nonfinite numbers and naive timestamps; null means unavailable/unreachable according to the entity and metric.

## Topics

Every message value is the full versioned WebSocket envelope JSON; topic map in `services/bus.py`. Detection, diagnosis and actuation stay inside the controller. Optional archival delivery runs separately so an unavailable broker does not stop the control loop.

| Topic | Producer | Consumers | Envelope `data` |
|---|---|---|---|
| `telemetry.raw` | engine | sink → `telemetry` hypertable, stream | `[TelemetrySample, ...]` (one tick) |
| `anomalies` | engine | sink → latest `anomalies` rows + full delta in `events`, stream | `{ raised: [Anomaly], cleared: [entity_id] }` |
| `rca.hypotheses` | engine | sink → `events`, stream | `[RCAHypothesis, ...]` |
| `actions` | engine | sink → `events`, stream | `{ kind, payload }` |
| `incidents` | engine | sink → `incidents` (upsert), stream | `{ incident, healer_status, actions }` |
| `audit` | engine | sink → `events`, stream | `LedgerEntry` (hash-chained) |
| `autonomy` | engine | sink → `events`, stream | `{ level, levels }` |

Detection, RCA and healing run inside the engine because the healer's twin needs current network state. `telemetry.features` is not emitted, and proposed/applied/result actions share the `actions` topic. Audit entries have their own `audit` topic.

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

This model remains defined for compatibility; the current runtime does not publish a feature-vector topic.
```json
{ "ts": "...", "entity_id": "core1-dist2", "window_s": 10,
  "features": { "latency_ewma": 4.1, "latency_z": 0.3, "loss_slope": 0.0, "util_p95": 0.66 } }
```

### Anomaly
```json
{ "id": "uuid", "ts": "...", "entity_id": "dist1-library", "metric": "loss_pct",
  "value": 14.2, "baseline": 0.1, "score": 0.97,
  "detectors": ["zscore", "iforest", "lstm_ae"], "severity": "critical" }
```

### RCAHypothesis
```json
{ "id": "uuid", "incident_id": "uuid",
  "cause": "gray_failure",          // link_failure | gray_failure | congestion | node_overload | misconfig | flapping
  "target": "dist1-library", "confidence": 0.94,
  "evidence": [ { "anomaly_id": "uuid", "description": "The failing Library flow traverses dist1-library", "weight": 0.6 } ],
  "method_scores": { "signature": 0.95, "voting": 1.0, "gnn": 0.875 },
  "confidence_kind": "heuristic", "supported": true }
```

### ActionCandidate
```json
{ "id": "uuid", "incident_id": "uuid",
  "type": "reroute",               // reroute | ecmp_split | rate_limit | drain_node | rollback_config | quarantine_link
  "params": { "avoid": ["dist1-library"], "routes": { "library-internet": ["library", "dist2", "core1", "internet"] },
              "planner": "rl" },  // planner only on the RL agent's proposal
  "twin_prediction": { "latency_ms": 22.0, "loss_pct": 0.2, "max_util": 0.58 },
  "opa_decision": "allow", "risk_score": 0.58 }
```

The action enum includes future capabilities. Current execution supports `reroute`, `drain_node` and `rollback_config`; `ecmp_split`, `rate_limit` and `quarantine_link` fail closed. `risk_score` is rounded peak predicted utilization, not a calibrated probability of harm. The examples are illustrative, not a captured benchmark result.

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
{ "type": "telemetry", "data": ["TelemetrySample"],
  "generation": "controller/network UUID", "sequence": 123,
  "event_id": "unique UUID", "emitted_at": "UTC wall time",
  "detector": { "ready": true, "progress": 1 } }
```

Anomaly events carry what changed this tick:
```json
{ "type": "anomaly", "data": { "raised": [Anomaly, ...], "cleared": ["dist1-library", ...] } }
```
`GET /anomalies` returns `{ "ready": bool, "warmup_progress": 0..1, "active": [Anomaly, ...] }`. The detector requires 30 s of trusted healthy baseline samples after start; bad samples do not train a new normal. Initial warm-up returns no statistical alerts: the dashboard shows learning/unknown rather than healthy. Hard reachability failure remains visible during later route-change relearning. An active anomaly keeps its ID while value, severity and evidence update. Clearing uses entity IDs, as shown above.

RCA events carry the full ranked diagnosis whenever it changes (an empty list means the incident is over):
```json
{ "type": "rca", "data": [RCAHypothesis, ...] }
```
`GET /rca` returns the current ranked `[RCAHypothesis, ...]`. `method_scores` holds the implemented signature, voting and optional GNN scores. Hypotheses add `confidence_kind: "heuristic"` and `supported: bool`. Ranking scores are not calibrated probabilities. Snapshot and RCA envelopes add `diagnosis_meta` with healthy/supported/uncertain status, reason and (on events) unexplained flows. A forecast or unexplained flow symptom can produce an uncertain diagnosis without an actionable cause.

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
`GET /incident` returns the same incident state. `ActionResult.before`/`after` retain legacy affected-flow averages: an unreachable flow counts as **1000 ms, a simulation scoring sentinel rather than a measured delay**. `after.baseline_latency_ms` is their healthy latency. The authoritative `per_flow_before` and `per_flow_after` maps contain latency, loss, throughput and reachability for every flow. Verification checks each affected and unaffected flow separately, the service-link utilization bound, sample validity and freshness; a favorable average alone cannot verify recovery.

`ActionResult` also adds `rollback_attempted`, `rollback_error`, `failure_reason`, `verification_reasons` and `outcome` (`verified`, `rolled_back`, `execution_failed`, `rollback_failed`). A failed execution or rollback remains visible. `Incident` adds `first_healed_at`, `recovery_attempts` and `decision_reason`; relapse clears current MTTR/recovery status while preserving earlier attempts. Reset, backend change and controller restart close unfinished incidents as failed/interrupted rather than claiming recovery.

Verification observes six ticks. Each flow's latency and loss are averaged over that window and compared with its frozen healthy reference; every tick must still provide valid reachable evidence, and carrying-link utilization must remain at most 85% on every tick. The evaluator's sustained-recovery measure is stronger: each flow must satisfy its SLA individually on every one of the final twenty ticks.

Incident MTTD is `detected_at - opened_at`; MTTR is `healed_at - opened_at` at verified recovery. API-injected faults supply the known onset. Without a known onset the incident opens at detection, so an MTTD of zero is a convention, not measured instantaneous detection. These durations, approval expiry and change-rate windows use modeled network time. The live gateway starts its modeled clock at current UTC, while a default `Network()` and the benchmark start at January 1, 2026; each step advances that clock by 0.5 seconds. Wall observation/emission timestamps and JWT expiry use real time. Slow controller work can make a three-modeled-second verification take longer in wall time.

`rebaseline` carries the link/node IDs that now carry rerouted traffic. Their statistical reference is relearned from twenty consecutive trusted samples (ten modeled seconds); unhealthy relearning expires after sixty elapsed ticks while retaining the old reference. Service and reachability checks continue during this later relearning. Initial startup instead requires sixty trusted consecutive samples and presents learning/unknown before readiness.

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
Reports additionally carry `generation` and an evidence hash. The controller captures facts under its mutation lock, releases the lock during inference, and rejects a changed evidence version with HTTP 409. Cached reports are shown only when their evidence hash matches the incident. The latest applied repair determines which supported cause the narrative describes. Reports disclose the unreachable-latency sentinel and include per-flow evidence.

LLM settings come from `.env`: `INFERENCE_CLOUD_API_KEY`, `INFERENCE_CLOUD_ENDPOINT` (Cirrascale AI Suite, OpenAI-compatible), and optional `LLM_MODEL` (default `Llama-3.3-70B`). With `OLLAMA_URL` set, a local model (`OLLAMA_MODEL`, default `qwen2.5:7b`) can answer when the cloud is unreachable. Each provider has a 10 s deadline and zero SDK retries; the report has a 25 s overall deadline. Templates work with no provider. Numeric/identity/outcome checks and citation checks are limited grounding guards, not proofs of all prose. The LLM has no actuation tool.

## Safety and control (Phase 10)

- **Auth:** `POST /auth/login {username, password}` returns `{ token, username, role }` (JWT, 12 h). Send `Authorization: Bearer <token>`. Roles: `viewer` < `operator` < `admin`. Reads and the WebSocket are open; `POST /fault`, `POST /reset`, `POST /incidents/{id}/report` and `POST /approvals/{id}/approve|reject` need operator; `PUT /autonomy` needs admin. Demo accounts: `config/DEMO_ACCOUNTS.md`.
- **Comfort level:** `GET /autonomy` returns `{ level, levels }`; `PUT /autonomy {level: 0-4}`.
- **Approvals:** `GET /approvals` returns `{ awaiting: ActionCandidate | null, incident_id }`. New healing event kinds: `recommended`, `awaiting_approval`, `approved`, `rejected`. The incident state gains `awaiting`.
- **Policy:** `ActionCandidate.policy_reasons` lists why `config/healing.rego` denied a fix.
- **Audit:** `GET /audit?limit=200` returns the newest `LedgerEntry` first (with `payload`); `GET /audit/verify` returns `{ valid, broken_at, entries }`.

Candidates add `planned_at`, `expires_at` (30 simulated seconds), `state_fingerprint` and `planning_version`. Approval checks the proposal ID, generation, current supported diagnosis, network fingerprint, current policy, sample freshness and a fresh twin prediction. A changed/expired proposal does not act. Changing autonomy invalidates unexecuted proposals while retaining in-flight verification. L0 alerts only; L1 recommends only; L2 requires approval for every action; L3 automatically applies at most one-flow actions with risk <= 0.6 and requests approval otherwise; L4 automatically applies allowed actions. Every retry at approval levels needs its own approval.

## Network backend (Phase 12)

- `GET /backend` returns `{ kind: "sim" | "emu", emulab_url, emulab_ready }`.
- `POST /backend {kind}` (admin) swaps the network. The detector re-learns the new network's normal (30 s); the incident, diagnosis and healer state reset; audited as `backend.switched`. Returns 409 if the emulator isn't running.

**Emulab agent** (`emulab/agent.py`, port 9000, used by `services/netsim/emu.py`):

| Call | Does |
|---|---|
| `GET /health` | `{ ready, switches, hosts, links }` |
| `GET /telemetry` | `TelemetrySample` rows without `ts` (the engine stamps them) |
| `POST /reset {routes}` | validates complete route set, clears faults, replaces switch rules |
| `POST /route {flow, path}` | validates endpoints/adjacency/no repeated nodes; installs cookie-tagged rules |
| `POST /fault {type, target, severity, ramp_s}` | link down / gray loss (netem) / congestion (bandwidth cut) / flapping / node overload (extra port delay; CPU modelled) / misconfig (drop rule) |
| `POST /clear_faults`, `POST /rollback_config {flow}` | undo |

## Evaluation and self-observability (Phase 13)

- `GET /evaluation` returns `docs/evaluation.json`: `{ meta, summary: { policies, by_fault }, runs }` (404 before the first run). Policies: `no_heal`, `reactive`, `guarded_reactive`, `native_shortest`, `twin`, `predictive_twin`, `rl`. `native_shortest` is a simplified observed hard-link failover reference, not a full routing-protocol implementation. Runs retain fixed original harmed-flow cohorts, per-flow outcomes, collateral damage, relapse and diagnosis coverage. Source hashes, seeds, denominators and scenario budgets are in metadata. Model-mismatch stress results use a separate population and artifact.
- `GET /metrics` (engine, stream) and `:9464/metrics` (sink): Prometheus metrics, names in `services/observability.py`.
- Traces: OTLP to `OTEL_EXPORTER_OTLP_ENDPOINT` when set (`./netheal obs`); service names `netheal-engine`, `netheal-stream`, `netheal-sink`. The trace context travels in Kafka message headers.

## All REST endpoints (engine, http://localhost:8001)

Roles: `-` anyone, `viewer`/`operator`/`admin` need a token from `POST /auth/login` (`Authorization: Bearer …`); higher roles include lower ones. Tokens must carry `sub`, `role` and `exp`, signed with `JWT_SECRET` (the engine never signs with a missing, placeholder or short secret). Approving a fix re-tests it on the twin and the safety rules first. All ports listen on 127.0.0.1 only. Interactive docs: `/docs`.

| Method and path | Role | What |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | -, signed in | Sign in (`{token, username, role}`); who am I |
| `GET /topology` | - | Nodes, links, flows and their current routes |
| `GET /snapshot`, `GET /health` | - | Coherent versioned state; controller liveness/readiness/telemetry age |
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

`GET /snapshot` acquires the same lock as ticks and control commands. It returns generation/sequence, topology, latest telemetry, detector state, anomalies, diagnosis/meta, incident, autonomy, backend and observed/emitted wall times. The frontend buffers live messages during bootstrap, ignores duplicates/retired generations and resynchronizes after sequence gaps. Failed resynchronization and stale data disable claims of healthy/current state.

`POST /whatif` uses an isolated network and planner with the current autonomy, baseline and rate budget. `preserve_faults: false` gives an isolated fault experiment; true retains current faults for a compound experiment. It never changes forwarding in the live simulator. `POST /copilot` likewise receives an isolated snapshot and returns captured/observed times, generation, snapshot age, stale flag and boot-time documentation version with its answer.

Native Windows mode uses `.\\netheal.ps1 start` and the direct controller WebSocket. `NETHEAL_STATE_PATH` enables a SQLite WAL journal: a critical event and its history checkpoint commit atomically. Restart restores reviewed history/reports/audit/autonomy, starts a new simulator generation and invalidates unfinished actions; it never resumes a queued forwarding command. Raw telemetry uses a bounded transient archive queue. The optional sink acknowledges broker offsets after an idempotent database transaction with message receipts; this is at-least-once delivery with idempotent effects, not an exactly-once transport claim. `/study` serves the generated local offline companion when present.
