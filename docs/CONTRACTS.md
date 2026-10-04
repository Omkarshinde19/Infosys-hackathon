# Message Contracts

Every service talks through these messages, on Redpanda topics and over the gateway WebSocket. The source of truth will be the Pydantic models in `contracts/`. This file documents them for humans.

**Conventions:** timestamps are ISO-8601 UTC strings, IDs are UUIDv4 strings, latency is in **ms**, loss in **percent (0–100)**, throughput in **Mbps**, utilization and CPU are fractions **0–1**.

## Topics

| Topic | Producer | Consumers | Message |
|---|---|---|---|
| `telemetry.raw` | collector | detector, gateway, timescale sink | `TelemetrySample` |
| `telemetry.features` | collector | detector | `FeatureVector` |
| `anomalies` | detector | rca, gateway, llm | `Anomaly` |
| `rca.hypotheses` | rca | healer, gateway, llm | `RCAHypothesis` |
| `actions.proposed` | healer | gateway (approvals), llm | `ActionCandidate` |
| `actions.applied` | healer | gateway, llm, evaluator | `ActionResult` |
| `incidents` | healer | gateway, llm, evaluator | `Incident` |
| `audit` | all | ledger | `LedgerEntry` |

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
  "params": { "avoid": ["core1-library"], "new_path": ["core1", "dist2", "library"] },
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
{ "id": "uuid", "status": "resolved",   // open | diagnosing | healing | resolved | failed
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
{ "type": "action", "data": { "kind": "proposed" | "applied" | "rebaseline" | "result" | "no_action" | "escalated",
                              "payload": [ActionCandidate, ...] | ActionCandidate | ActionResult | "reason" } }
{ "type": "incident", "data": { "incident": Incident | null, "healer_status": "idle" | "verifying" | "healed" | "rolled_back" | "no_action_needed" | "escalated",
                                "actions": [ <action event data>, ... ] } }
```
`GET /incident` returns the same incident state. In `ActionResult.before`/`after`, `latency_ms` is averaged over the affected flows (an unreachable flow counts as 1000 ms), and `after.baseline_latency_ms` is their healthy latency.

`rebaseline` carries the link/node ids that now carry rerouted traffic; the detector re-learns their normal for 10 s instead of flagging the intended change.
