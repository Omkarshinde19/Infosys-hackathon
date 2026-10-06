# Known limitations and next steps

What NetHeal does not do yet, written down so nobody over-claims it in a demo and so the next person knows where to start. Most items come from a code audit on 7 Oct 2026; the ones that were quick and safe are already fixed (localhost-only ports, signing-secret setup, validated assistant input, alert-only incidents, re-checked approvals, latest healing history).

## Healing decisions

- **Verification averages the affected flows.** One flow can stay above 1% loss while the group average passes. Next: check every affected flow on its own, and check that unaffected flows did not get slower (the safety policy checks their loss, not their latency).
- **Candidates move all affected flows to the same path rank.** A mix (flow A on its first detour, flow B on its second) is never tried. Next: bounded search over mixed assignments, compared against an exact optimiser on this small campus.
- **Route search uses base latency, then filters.** Demand and spare capacity only enter through the twin's verdict. Next: capacity-aware path generation, service priorities, cooldowns against route churn.
- **A rollback restores the routes it changed; it does not re-read the switches.** On the emulator, a command that times out after the switch accepted it is not reconciled.

## Detection and diagnosis

- **Reachability is not checked for an entity while its baseline is being re-learned** (up to 10 s after a reroute). Downstream flows still alert.
- **Diagnosis confidence is a weighted score, not a calibrated probability.** One cause at a time; simultaneous faults are not separated.
- **Telemetry gaps are not their own alert.** Missing data is not flagged as a data-quality problem.

## Machine learning

- **The RL agent is trained on the true fault location**, one decision per episode (`gamma = 0`), and compared with the rules on 600 held-out decisions. Next: train on the diagnosis it will really get, and compare with a constrained optimiser and a contextual bandit.
- **Everything is trained and evaluated on one campus topology.** Generalisation to other networks is untested.

## Evaluation

- **One fault per scenario, 60 s episodes, 26 healthy controls.** No overlapping faults, telemetry outages or controller restarts. The "reactive" baseline ignores the safety rules; there is no OSPF/ECMP-style baseline.
- **The twin knows the injected fault** (it copies it). A real deployment would have to infer it.

## Platform

- **State lives in the engine process.** Incidents, approvals and the audit chain survive in TimescaleDB as a record, but a restart starts a fresh controller.
- **Events are published without waiting for broker acknowledgement**, and the sink is not idempotent on replay.
- **Sessions use a bearer token in browser storage**, fine on one laptop. A shared deployment would need HttpOnly cookies, revocation and a separately secured emulator API.
- **The launcher is a bash script for macOS and Linux**; Windows needs WSL2. Python dependencies are lower-bound, not locked.
