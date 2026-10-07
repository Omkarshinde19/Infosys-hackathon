# Verified scope and remaining limits

NetHeal is the NC-04 campus simulator prototype. It runs detection, diagnosis,
guarded planning, repair, per-flow verification and explanations. It operates on a
configured synthetic campus and optionally a separate Mininet/Open vSwitch lab.
No production network, customer downtime saving or physical cable repair has been validated.

## Detection and diagnosis

Hard reachability checks continue during relearning. Missing, stale and malformed
measurements produce data-quality evidence and block unsupported diagnoses. Ordinary
statistical alerts use a trusted healthy baseline, robust deviation, Isolation Forest
and temporal debounce. Flow service limits add explicit sustained degradation alerts.
Unknown steady-state faults can still contaminate an apparently healthy starting baseline.

RCA confidence is a heuristic ranking score. It combines resource signatures,
affected-path votes and an optional pretrained graph model. It can abstain when only
forecast, latency or bad-data symptoms exist. It identifies a leading cause with
evidence and records unexplained flows. Complete simultaneous-fault decomposition
and probability calibration remain future work.

The pretrained GNN, forecaster, LSTM autoencoder and RL weights were preserved.
Their standalone scores come from their original training artifacts. The forecast
training label uses a broader service threshold than the operational verifier.
RL training uses a one-step environment with the true fault location. Its proposal
must pass the same current twin and policy checks as deterministic candidates.
Transfer to a new topology or workload has not been established.

## Planning and recovery

Mixed route assignments now use a bounded capacity-aware search. This improves
candidate coverage without claiming the globally optimal traffic allocation.
The supported actuators are rerouting, node draining and configuration rollback.
Other contract enum values fail closed until an actuator exists.

Candidates expire and bind to controller generation, observed diagnosis and state.
Approvals and retries revalidate current predictions and policy. Every flow must
meet its loss and latency limits, and collateral service deterioration blocks success.
Execution and rollback failures have explicit outcomes. Continued deterioration
causes bounded replanning and escalation.

The simulator twin knows configured fault state and shares the plant equations.
The independent synthetic delay stress suite introduces a deliberate model mismatch.
This is useful fault testing, with limited coverage of real uncertainty.
An emulator command can time out after a switch accepts it. HTTP acknowledgement
and checked OpenFlow exit status improve error reporting, but readback reconciliation,
transactional multi-switch updates and confirmed device commits remain unimplemented.

## Platform and explanations

Native mode and the Docker engine can preserve reviewed incident history, reports
and audit entries in a SQLite checkpoint/journal. Restart starts a clean simulated
network and invalidates unfinished commands. It does not resume an unknown repair.
This is one local controller, with no distributed controller failover guarantee.
The audit hash chain is tamper-evident and needs a trusted external head to resist
a privileged rewrite of the complete chain.

Broker acknowledgements/retries run outside the simulation loop. Control events
use a durable local outbox when NETHEAL_STATE_PATH is configured. Telemetry uses
a bounded queue and can be dropped under backpressure. Browser sequence gaps
trigger a coherent snapshot. The sink commits database writes and deduplication
receipts before acknowledging consumer offsets. End-to-end Docker availability
must be checked on the machine used for the demo.

The LLM has only read-only query, document and isolated simulation tools. It does
not detect, diagnose, approve or actuate repairs. Reports bind to an evidence hash
and reject changes during generation. Citation coverage, cause/timing/numeric
checks are useful guards, with no proof of complete semantic grounding. Templates
provide a labeled fallback when credentials, model availability or checks fail.
Live Qualcomm Cloud AI or Ollama inference requires a configured available provider.

JWT bearer sessions remain in local browser storage. Local ports bind to loopback.
A shared deployment needs a production identity provider, session revocation,
HttpOnly cookies, rate limiting and separately authenticated emulator access.
Python dependency floors are not a complete reproducible cross-platform lock.
