"""Paired synthetic evaluation of detection, routing, guarded healing and relapse.

Every scenario uses a held-out seed (never seen while training a model): a warmed-up campus
network gets one random fault (type, target, severity, sudden or gradual), or none as a
healthy control, and the same scenario is replayed under each policy:

  no_heal          detect and diagnose only: what happens without automatic healing
  reactive         rules-only diagnosis; apply the first detour, no twin test, no guardrails
  guarded_reactive rules + first detour, with the same twin/policy/verification as NetHeal
  native_shortest  simplified native shortest-path reconvergence on observed reachability
  twin             rules + GNN diagnosis; twin-tested candidates behind the OPA guardrails
  predictive_twin  twin + the forecaster and LSTM autoencoder
  rl               predictive_twin + the RL routing agent's proposal as one more twin-tested
                   candidate (the live configuration)

Run: ./netheal eval  (writes docs/evaluation.json and docs/EVALUATION.md)
"""

import argparse
import copy
import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from multiprocessing import Pool
from pathlib import Path
from statistics import median

import networkx as nx
import numpy as np

from contracts.models import TwinPrediction
from ml.datagen import FAULT_TO_CAUSE, random_fault, voting_only
from services.detector.detector import WARMUP_TICKS, Detector
from services.healer.healer import HEALTHY_LOSS_PCT, LATENCY_TOLERANCE, Healer
from services.ml import forecast, gnn, lstm_ae, rl
from services.ml.forecast import breached
from services.netsim.engine import TICK_S, Network
from services.rca.engine import RCAEngine

POLICIES = (
    "no_heal",
    "reactive",
    "guarded_reactive",
    "native_shortest",
    "twin",
    "predictive_twin",
    "rl",
)
BASE_SEEDS = (505, 606, 707, 808)  # training uses 101-404
FIRST_SEED = 1_000_000  # training uses scenario seeds 0..N
RUN_TICKS = 120  # 60 s after the fault (gradual faults ramp for up to 30 s)
RECOVERED_TICKS = 20  # every flow within SLA for the last 10 s
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "evaluation.json"
REPORT = ROOT / "docs" / "EVALUATION.md"
SCHEMA_VERSION = "netheal.evaluation.v2"
BOOTSTRAP_REPEATS = 2000
STRESS_WINDOWS_S = ((3, 13), (30, 40))
STRESS_FLOWS = ("library-internet", "lab_cs-internet")
STRESS_DELAY_FACTOR = 1.18
SUITES = ("nominal", "unmodeled_delay")


class ReactiveHealer(Healer):
    """Classic rule-based remediation: the first (shortest) detour, untested and unchecked.
    It is still verified and rolled back if it fails, like every policy here."""

    def _predict(self, c, net, affected) -> None:
        c.twin_prediction = TwinPrediction(latency_ms=0, loss_pct=0, max_util=0)
        c.opa_decision = "allow"


class GuardedReactiveHealer(Healer):
    """First deterministic shortest detour, with the production safety and verification."""

    def _reroutes(self, h, net):
        candidates, affected = super()._reroutes(h, net)
        return candidates[:1], affected


class NativeShortestRouting:
    """An idealized SPF reference with a 3-observation reachability convergence delay.

    Only observed link reachability changes the topology, and static configured latency
    supplies the routing cost. It models neither routing messages nor ECMP splitting.
    It has no access to fault labels, forecast scores or the twin and cannot repair a
    forwarding misconfiguration. Protocol reconvergence is not a verified healer action.
    """

    def __init__(self):
        self.down = set()
        self.last = {}
        self.streak = {}

    def update(self, samples, net):
        changed = False
        for s in samples:
            if s.entity_type != "link":
                continue
            down = s.latency_ms is None
            self.streak[s.entity_id] = (
                self.streak.get(s.entity_id, 0) + 1 if self.last.get(s.entity_id) == down else 1
            )
            self.last[s.entity_id] = down
            if self.streak[s.entity_id] >= 3 and down != (s.entity_id in self.down):
                self.down.add(s.entity_id) if down else self.down.discard(s.entity_id)
                changed = True
        if not changed:
            return []
        graph = net.graph.copy()
        graph.remove_edges_from(net.links[e] for e in self.down)
        moved = []
        for fid, flow in net.flows.items():
            if not nx.has_path(graph, flow["src"], flow["dst"]):
                continue
            path = nx.shortest_path(graph, flow["src"], flow["dst"], weight="base_latency_ms")
            if path != net.routes[fid]:
                net.set_route(fid, path)
                moved.append(fid)
        return moved


class DelayStressNetwork(Network):
    """Transparent synthetic measurement mismatch, deliberately absent from the twin.

    Two named flows receive 18% extra observed latency during fixed epochs after warm-up.
    The perturbation is independent of the injected fault/diagnosis/action. This tests
    verification and relapse under a bounded unmodeled delay; it is not emulator evidence.
    """

    def step(self):
        samples = super().step()
        elapsed = (self.tick - WARMUP_TICKS) * TICK_S
        if any(start <= elapsed < end for start, end in STRESS_WINDOWS_S):
            return [
                s.model_copy(update={"latency_ms": s.latency_ms * STRESS_DELAY_FACTOR})
                if s.entity_id in STRESS_FLOWS and s.latency_ms is not None
                else s
                for s in samples
            ]
        return samples

    def snapshot(self):
        twin = copy.deepcopy(self)
        twin.__class__ = Network  # twin retains the queueing model, excluding observation drift
        return twin


def service_breached(sample, baseline_ms):
    """Match the healer's loss/latency thresholds; invalid observations fail closed.

    The healer averages a six-tick verification window. This function scores each
    individual telemetry tick, so recovery also establishes sustained service quality.
    """
    return (
        sample is None
        or sample.latency_ms is None
        or sample.loss_pct is None
        or not np.isfinite([sample.latency_ms, sample.loss_pct, baseline_ms]).all()
        or sample.latency_ms < 0
        or not 0 <= sample.loss_pct <= 100
        or baseline_ms <= 0
        or sample.loss_pct >= HEALTHY_LOSS_PCT
        or sample.latency_ms > LATENCY_TOLERANCE * baseline_ms
    )


def affected_flows(net, fault):
    """Freeze the injected fault's exposure cohort on the original routes."""
    if not fault:
        return set()
    kind, target = fault[:2]
    return {
        f
        for f, path in net.routes.items()
        if (
            target == f
            if kind == "misconfig"
            else target in path
            if kind == "node_overload"
            else target in net.path_links(path)
        )
    }


_bases: dict[tuple[int, bool, str], tuple] = {}


def base(seed: int, predictive: bool, suite: str = "nominal"):
    """Network + detector warmed up on healthy traffic (cached per process)."""
    if (seed, predictive, suite) not in _bases:
        net = DelayStressNetwork(seed=seed) if suite == "unmodeled_delay" else Network(seed=seed)
        det = Detector(forecaster=forecast.load(), autoencoder=lstm_ae.load()) if predictive \
            else Detector()  # fmt: skip
        for _ in range(WARMUP_TICKS):
            det.update(net.step())
        _bases[seed, predictive, suite] = (net, det)
    return _bases[seed, predictive, suite]


def run(seed: int, policy: str, suite: str = "nominal") -> dict:
    """Replay one scenario under one policy."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown evaluation policy: {policy}")
    if suite not in SUITES:
        raise ValueError(f"Unknown evaluation suite: {suite}")
    prepared = base(BASE_SEEDS[seed % len(BASE_SEEDS)], policy in ("predictive_twin", "rl"), suite)
    net, det = (copy.deepcopy(x) for x in prepared)
    net.rng = np.random.default_rng(seed)
    fault = random_fault(np.random.default_rng(seed), net)
    rca = RCAEngine(
        gnn=None if policy in ("reactive", "guarded_reactive", "native_shortest") else gnn.load()
    )
    healer = (
        ReactiveHealer()
        if policy == "reactive"
        else GuardedReactiveHealer()
        if policy == "guarded_reactive"
        else Healer(rl=rl.load() if policy == "rl" else None)
    )
    native = NativeShortestRouting() if policy == "native_shortest" else None
    healer.level = 0 if policy == "no_heal" else 4
    baseline = {f: float(det.median[f][0]) for f in net.flows}
    exposed = affected_flows(net, fault)
    original_routes = copy.deepcopy(net.routes)
    if fault:
        net.inject_fault(*fault)

    detected = diagnosis = voting = healed = None
    first_applied = None
    applied = rollbacks = escalated = relapses = collateral_ticks = 0
    ok, forecast_ok, latencies, losses, actions = [], [], [], [], []
    flow_samples = {f: [] for f in net.flows}
    flow_good = {f: [] for f in net.flows}
    before_action = None
    diagnosis_statuses = set()
    for t in range(RUN_TICKS):
        samples = net.step()
        det.update(samples)
        rca.update(samples, det.active, net, detector=det)
        diagnosis_statuses.add(rca.diagnosis_status)
        if det.active and detected is None:
            detected = t
        if rca.hypotheses and diagnosis is None:
            diagnosis = [(h.cause, h.target) for h in rca.hypotheses]
            voting = voting_only(net, det.active)
        latest = {s.entity_id: s for s in samples}
        moved = native.update(samples, net) if native is not None else []
        if moved:
            applied += 1
            if first_applied is None:
                first_applied, before_action = (
                    t,
                    {f: latest[f].model_dump(mode="json") for f in net.flows},
                )
            det.relearn(moved)
        events = [] if native is not None else healer.update(samples, rca.hypotheses, net, baseline)
        for kind, payload in events:
            if kind == "rebaseline":
                det.relearn(payload)
            if kind == "applied" and first_applied is None:
                first_applied, before_action = (
                    t,
                    {f: latest[f].model_dump(mode="json") for f in net.flows},
                )
            applied += kind == "applied"
            escalated += kind == "escalated"
            relapses += kind == "relapsed"
            if kind == "result":
                rollbacks += payload.rolled_back
                actions.append(payload.model_dump(mode="json"))
                if payload.verified and healed is None:
                    healed = t
        tick_good = {f: not service_breached(latest.get(f), baseline[f]) for f in net.flows}
        ok.append(all(tick_good.values()))
        forecast_ok.append(
            all(
                not breached(latest[f].latency_ms, latest[f].loss_pct, baseline[f])
                for f in net.flows
            )
        )
        if first_applied is not None and t > first_applied:
            collateral_ticks += any(not good for f, good in tick_good.items() if f not in exposed)
        for fid in net.flows:
            sample = latest[fid]
            flow_samples[fid].append(sample)
            flow_good[fid].append(tick_good[fid])
            latencies.append(1000.0 if sample.latency_ms is None else sample.latency_ms)
            losses.append(100.0 if sample.loss_pct is None else sample.loss_pct)

    bad_ticks = [t for t, good in enumerate(ok) if not good]
    recovered = len(ok) >= RECOVERED_TICKS and all(ok[-RECOVERED_TICKS:])
    truth = (FAULT_TO_CAUSE[fault[0]], fault[1]) if fault else None
    seconds = lambda t: None if t is None else round((t + 1) * TICK_S, 1)  # noqa: E731
    per_flow = {}
    for fid, series in flow_samples.items():
        delay = [1000.0 if s.latency_ms is None else s.latency_ms for s in series]
        loss = [100.0 if s.loss_pct is None else s.loss_pct for s in series]
        end = series[-RECOVERED_TICKS:]
        per_flow[fid] = {
            "exposed_to_fault": fid in exposed,
            "healthy_baseline_ms": baseline[fid],
            "sla_violation_s": sum(not g for g in flow_good[fid]) * TICK_S,
            "recovered": all(flow_good[fid][-RECOVERED_TICKS:]),
            "p95_latency_ms": round(float(np.percentile(delay, 95)), 2),
            "mean_loss_pct": round(float(np.mean(loss)), 3),
            "unreachable_s": sum(s.latency_ms is None for s in series) * TICK_S,
            "end_latency_ms": round(
                float(np.mean([1000.0 if s.latency_ms is None else s.latency_ms for s in end])), 2
            ),
            "end_loss_pct": round(
                float(np.mean([100.0 if s.loss_pct is None else s.loss_pct for s in end])), 3
            ),
            "end_throughput_mbps": round(float(np.mean([s.throughput_mbps or 0 for s in end])), 2),
        }
    return {
        "seed": seed,
        "policy": policy,
        "suite": suite,
        "fault": fault
        and {
            "type": fault[0],
            "target": fault[1],
            "severity": round(fault[2], 2),
            "ramp_s": fault[3],
        },  # fmt: skip
        "detected": detected is not None,
        "mttd_s": seconds(detected),
        "diagnosed": diagnosis is not None,
        "diagnosis_statuses": sorted(diagnosis_statuses),
        "top1": None if not truth else bool(diagnosis and diagnosis[0] == truth),
        "top3": None if not truth else bool(diagnosis and truth in diagnosis[:3]),
        "voting_top1": None if not (truth and diagnosis) else voting == truth[1],
        "healed": healed is not None,
        "mttr_s": seconds(healed),
        "applied": applied,
        "rollbacks": rollbacks,
        "relapses": relapses,
        "escalated": bool(escalated),
        "sla_impact": bool(bad_ticks),
        "forecast_sla_impact": not all(forecast_ok),
        "recovered": recovered,
        "recovery_s": (seconds(bad_ticks[-1]) if bad_ticks else 0.0) if recovered else None,
        "sla_violation_s": round(sum(not g for g in ok) * TICK_S, 1),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        "mean_loss_pct": round(float(np.mean(losses)), 3),
        "flow_violation_s": sum(r["sla_violation_s"] for r in per_flow.values()),
        "collateral_breach": bool(collateral_ticks),
        "collateral_violation_s_after_action": collateral_ticks * TICK_S,
        "original_exposed_flows": sorted(exposed),
        "original_routes": original_routes,
        "final_routes": net.routes,
        "per_flow": per_flow,
        "per_flow_before_first_action": before_action,
        "actions": actions,
    }


def _job(args):
    return run(*args)


def _worker_init():
    """Avoid model/BLAS thread oversubscription in the independent benchmark process."""
    import torch
    from threadpoolctl import threadpool_limits

    global _thread_limit
    torch.set_num_threads(1)
    _thread_limit = threadpool_limits(limits=1)


def evaluate(scenarios: int, processes: int = 8, suite: str = "nominal") -> list[dict]:
    if scenarios < 1 or processes < 1:
        raise ValueError("Evaluation needs positive scenario and process counts")
    jobs = [(FIRST_SEED + i, p, suite) for i in range(scenarios) for p in POLICIES]
    with Pool(processes, initializer=_worker_init) as pool:
        return pool.map(_job, jobs, chunksize=4)


# ---- summary ---------------------------------------------------------------


def _rate(rows, key) -> float | None:
    values = [r[key] for r in rows if r[key] is not None]
    return round(sum(values) / len(values), 4) if values else None


def _median(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(median(values), 1) if values else None


def rate_ci95(values):
    """Wilson interval for a binary rate; denominator is the number of scenarios."""
    values = list(values)
    if not values:
        return None
    n, p, z = len(values), sum(values) / len(values), 1.959963984540054
    scale = 1 + z * z / n
    center = (p + z * z / (2 * n)) / scale
    radius = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / scale
    return [round(max(0.0, center - radius), 4), round(min(1.0, center + radius), 4)]


def paired_interval(differences):
    """Resample whole incident pairs, never their correlated flow/tick observations."""
    values = np.asarray(differences, dtype=float)
    if not values.size:
        return {"mean": None, "ci95": None, "paired_scenarios": 0}
    interval = None
    if len(values) >= 2:
        rng = np.random.default_rng(917)
        means = values[rng.integers(0, len(values), (BOOTSTRAP_REPEATS, len(values)))].mean(axis=1)
        interval = np.percentile(means, [2.5, 97.5]).round(4).tolist()
    return {
        "mean": round(float(values.mean()), 4),
        "ci95": interval,
        "paired_scenarios": len(values),
    }


def policy_summary(rows: list[dict], hurt: set[int]) -> dict:
    """hurt: seeds whose fault broke the SLA without healing. Every policy is judged on that
    same set, so a fix that lands before the SLA breaks counts as a recovery."""
    faults = [r for r in rows if r["fault"]]
    healthy = [r for r in rows if not r["fault"] and r.get("suite", "nominal") == "nominal"]
    disturbed = [r for r in rows if not r["fault"] and r.get("suite") == "unmodeled_delay"]
    impact = [r for r in faults if r["seed"] in hurt]
    tp = sum(r["detected"] for r in faults)
    fp = sum(r["detected"] for r in healthy)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / len(faults) if faults else 0.0
    acted = [r for r in faults if r["applied"]]
    diagnosed = [r for r in faults if r.get("diagnosed", r["top1"] is not None)]
    p95 = _median(r["p95_latency_ms"] for r in impact)
    return {
        "scenarios": len(rows),
        "faults": len(faults),
        "healthy": len(healthy),
        "disturbance_controls": len(disturbed),
        "detection": {
            "precision": round(precision, 3) if healthy else None,
            "recall": round(recall, 3),
            "f1": (round(2 * precision * recall / (precision + recall), 3) if tp else 0.0)
            if healthy
            else None,
            "false_positive_rate": round(fp / len(healthy), 3) if healthy else None,
            "disturbance_control_detection_rate": _rate(disturbed, "detected"),
            "median_mttd_s": _median(r["mttd_s"] for r in faults),
            "median_mttd_gradual_s": _median(r["mttd_s"] for r in faults if r["fault"]["ramp_s"]),
        },
        "rca": {
            "top1": _rate(faults, "top1"),
            "top3": _rate(faults, "top3"),
            "voting_007_top1": _rate(faults, "voting_top1"),
            "diagnosed_faults": len(diagnosed),
            "coverage": round(len(diagnosed) / len(faults), 4) if faults else None,
            "top1_over_all_faults": round(sum(bool(r["top1"]) for r in faults) / len(faults), 4)
            if faults
            else None,
            "top1_given_diagnosis": _rate(diagnosed, "top1"),
        },
        "healing": {
            "sla_impacting_faults": len(impact),
            "recovered_rate": _rate(impact, "recovered"),
            "recovered_rate_ci95": rate_ci95(r["recovered"] for r in impact),
            "recovered_faults": sum(r["recovered"] for r in impact),
            "applied_faults": len(acted),
            "verified_faults": sum(r["healed"] for r in impact),
            "relapsed_faults": sum(r.get("relapses", 0) > 0 for r in impact),
            "collateral_breach_faults": sum(r.get("collateral_breach", False) for r in acted),
            "median_recovery_s": _median(r["recovery_s"] for r in impact),
            "healed_rate": _rate(impact, "healed"),
            "median_mttr_s": _median(r["mttr_s"] for r in impact),
            "rollback_rate": round(sum(r["rollbacks"] > 0 for r in acted) / len(acted), 3)
            if acted
            else None,  # fmt: skip
            "escalated_rate": _rate(impact, "escalated"),
        },
        "sla": {
            "violation_s_total": round(sum(r["sla_violation_s"] for r in faults), 1),
            "median_violation_s": _median(r["sla_violation_s"] for r in impact),
            "p95_latency_ms": p95,  # compatibility: explicitly a median of run-level p95s
            "median_run_p95_latency_ms": p95,
            "flow_violation_s_total": round(sum(r.get("flow_violation_s", 0) for r in faults), 1),
            "collateral_violation_s_after_action": round(
                sum(r.get("collateral_violation_s_after_action", 0) for r in acted), 1
            ),
            "mean_loss_pct": round(float(np.mean([r["mean_loss_pct"] for r in impact])), 3)
            if impact
            else None,  # fmt: skip
        },
    }


def summarize(runs: list[dict]) -> dict:
    by_policy = {p: [r for r in runs if r["policy"] == p] for p in POLICIES}
    types = sorted({r["fault"]["type"] for r in runs if r["fault"]})
    hurt = {r["seed"] for r in by_policy["no_heal"] if r["sla_impact"]}
    control = {r["seed"]: r for r in by_policy["no_heal"] if r["fault"]}
    paired = {}
    for policy, rows in by_policy.items():
        common = [(r, control[r["seed"]]) for r in rows if r["fault"] and r["seed"] in control]
        impact = [(r, c) for r, c in common if r["seed"] in hurt]
        paired[policy] = {
            "recovered_rate_delta": paired_interval(
                [int(r["recovered"]) - int(c["recovered"]) for r, c in impact]
            ),
            "violation_s_delta": paired_interval(
                [r["sla_violation_s"] - c["sla_violation_s"] for r, c in common]
            ),
            "flow_violation_s_delta": paired_interval(
                [r.get("flow_violation_s", 0) - c.get("flow_violation_s", 0) for r, c in common]
            ),
        }
    return {
        "policies": {p: policy_summary(rows, hurt) for p, rows in by_policy.items()},
        "paired_vs_no_heal": paired,
        "by_fault": {
            t: {
                p: policy_summary([r for r in rows if r["fault"] and r["fault"]["type"] == t], hurt)
                for p, rows in by_policy.items()
            }
            for t in types
        },  # fmt: skip
    }


def _pct(x) -> str:
    return "–" if x is None else f"{x:.0%}"


def _s(x) -> str:
    return "–" if x is None else f"{x:.1f} s"


def markdown(results: dict) -> str:
    s, meta = results["summary"]["policies"], results["meta"]
    head = "| | " + " | ".join(f"`{p}`" for p in POLICIES) + " |\n|---|" + "---|" * len(POLICIES)
    row = lambda label, f: f"| {label} | " + " | ".join(f(s[p]) for p in POLICIES) + " |"  # noqa: E731
    lines = [
        "# Evaluation results",
        "",
        f"Generated by the harness ({meta['scenarios']} paired scenarios × {len(POLICIES)} "
        f"policies, {meta['run_s']:.0f} s of simulated time each). Raw runs and the summary: "
        "`docs/evaluation.json`; charts on the dashboard's Evaluation page.",
        "",
        "Policies: `no_heal` detects and diagnoses only. `reactive` diagnoses with rules and "
        "applies the first detour, with no twin test and no guardrails (an unsafe ablation). "
        "`guarded_reactive` uses rules and the first detour with the production safety checks. "
        "`native_shortest` reconverges shortest paths after three observed reachability ticks; "
        "it is a simplified routing reference, not a full OSPF or ECMP implementation. "
        "`twin` is NetHeal: "
        "rules + GNN diagnosis, twin-tested candidates behind the OPA guardrails. "
        "`predictive_twin` adds the forecaster and LSTM autoencoder. `rl` also adds the RL "
        "routing agent's proposal as one more candidate, tested like the rest (the live "
        "configuration).",
        "",
        "## Headline",
        "",
        head,
        row(
            "Faults that hurt users without healing",
            lambda x: str(x["healing"]["sla_impacting_faults"]),
        ),
        row("Recovered (SLA met, last 10 s)", lambda x: _pct(x["healing"]["recovered_rate"])),
        row("Median time to recover", lambda x: _s(x["healing"]["median_recovery_s"])),
        row("Healed by a verified fix", lambda x: _pct(x["healing"]["healed_rate"])),
        row("Median MTTR (fault to verified fix)", lambda x: _s(x["healing"]["median_mttr_s"])),
        row("Rollback rate (of applied fixes)", lambda x: _pct(x["healing"]["rollback_rate"])),
        row("Escalated to a human", lambda x: _pct(x["healing"]["escalated_rate"])),
        row("SLA violation, total (s)", lambda x: str(int(x["sla"]["violation_s_total"] + 0.5))),
        row("Median of run-level p95 flow latency", lambda x: f"{x['sla']['p95_latency_ms']} ms"),
        row("Relapsed after verification", lambda x: str(x["healing"]["relapsed_faults"])),
        row(
            "Applied runs with collateral breach",
            lambda x: str(x["healing"]["collateral_breach_faults"]),
        ),
        "",
        "## Detection and diagnosis",
        "",
        head,
        row("Detection recall", lambda x: _pct(x["detection"]["recall"])),
        row("Detection precision", lambda x: _pct(x["detection"]["precision"])),
        row("Detection F1", lambda x: _pct(x["detection"]["f1"])),
        row("False alarms on healthy runs", lambda x: _pct(x["detection"]["false_positive_rate"])),
        row("Median MTTD", lambda x: _s(x["detection"]["median_mttd_s"])),
        row("Median MTTD, gradual faults", lambda x: _s(x["detection"]["median_mttd_gradual_s"])),
        row("Diagnosis coverage (all faults)", lambda x: _pct(x["rca"]["coverage"])),
        row("Root cause, top-1 (all faults)", lambda x: _pct(x["rca"]["top1_over_all_faults"])),
        row(
            "Root cause, top-1 (diagnosed faults)", lambda x: _pct(x["rca"]["top1_given_diagnosis"])
        ),
        row("Root cause, top-3", lambda x: _pct(x["rca"]["top3"])),
        row("007 voting alone, top-1", lambda x: _pct(x["rca"]["voting_007_top1"])),
        "",
        "## Recovered rate by fault type",
        "",
        head,
    ]
    for t, per in results["summary"]["by_fault"].items():
        lines.append(f"| {t} | " + " | ".join(
            f"{_pct(per[p]['healing']['recovered_rate'])} "
            f"({per[p]['healing']['sla_impacting_faults']})" for p in POLICIES) + " |")  # fmt: skip
    lines += [
        "",
        "In brackets: faults of that type that broke the SLA without healing. Every policy is "
        "judged on those same faults. Service scoring matches healing thresholds: every flow "
        "must be reachable, loss below 1%, latency at most 1.1 times its frozen healthy "
        "baseline. Recovery requires ten consecutive seconds of healthy per-flow ticks. "
        "Action verification uses six-tick means for every flow; the forecast's separate "
        "2% / double-latency warning definition is also recorded in raw runs.",
        "",
        "## Reading these numbers",
        "",
        "- The plant, twin, training generator and evaluation share the same queueing simulator "
        "and campus topology. These finite synthetic results establish no real-network accuracy "
        "or robustness to unseen topology, multiple faults or model mismatch.",
        "- Pretrained model files were preserved. Their hashes identify what was loaded; their "
        "original training lineage was not reverified. Isolated oracle-target PPO scores are "
        "not substituted for operational results using the actual diagnosis.",
        "- MTTD/MTTR medians include successes only; detection, diagnosis coverage, recovery "
        "counts and denominators expose failures. Native reconvergence can recover without a "
        "verified healer action and therefore has no healer MTTR.",
        "- Collateral breach records service on flows outside the frozen original fault cohort "
        "after an action. This is observed association, not proof that the action caused it. "
        "Paired comparisons use the same incident seeds and fault specifications; random-number "
        "consumption may change when different routes change reachability.",
        "- Recovery confidence intervals use Wilson binary-rate intervals. Paired deltas "
        "resample whole incidents, not correlated ticks/flows, with 2,000 deterministic "
        "bootstrap replicates. Intervals describe this scenario distribution and do not "
        "cover simulator bias. A single pair has no estimated bootstrap interval.",
        "",
    ]
    if meta.get("schema_version"):
        lines += [
            "## Provenance",
            "",
            f"Schema: `{meta['schema_version']}`. Generated: `{meta['generated_at']}`. "
            f"Git revision: `{meta['git_revision']}` (working source hashes identify edits).",
            "",
            "Source, model, data and package hashes/versions, frozen baseline and "
            "per-flow action evidence are recorded in `docs/evaluation.json`.",
            "",
        ]
    lines += [
        "## Paired comparison to no healing",
        "",
        "Negative violation-time deltas favor the policy; positive recovery deltas favor it.",
        "",
        "| Policy | Recovery rate delta [95% CI] | Violation seconds delta [95% CI] |",
        "|---|---|---|",
    ]
    for policy, pairs in results["summary"]["paired_vs_no_heal"].items():
        cells = []
        for key in ("recovered_rate_delta", "violation_s_delta"):
            entry = pairs[key]
            cells.append(
                "–"
                if entry["mean"] is None
                else f"{entry['mean']:.4f} {entry['ci95'] or '[not estimated]'} "
                f"(n={entry['paired_scenarios']})"
            )
        lines.append(f"| `{policy}` | " + " | ".join(cells) + " |")
    if results.get("stress"):
        stress = results["stress"]
        lines += [
            "",
            "## Controlled unmodeled-delay stress",
            "",
            f"An independent synthetic observation perturbation adds 18% delay to "
            f"`library-internet` and `lab_cs-internet` at 3–13 s and 30–40 s. The twin "
            f"does not include this perturbation. {stress['meta']['scenarios']} paired "
            "scenarios use the same fault seeds. Controls without an injected fault "
            "still receive the delay and are labeled disturbance controls, not healthy "
            "negatives; their alarms do not inflate a false-positive estimate. "
            "This bounded test exercises verification, rollback and relapse, and "
            "provides no evidence about emulator or real-network generalization.",
            "",
            "| Policy | Recovered / impacted | Verified fixes | Rollback runs | Relapses |",
            "|---|---|---|---|---|",
        ]
        for policy, item in stress["summary"]["policies"].items():
            h = item["healing"]
            lines.append(
                f"| `{policy}` | {h['recovered_faults']}/{h['sla_impacting_faults']} "
                f"| {h['verified_faults']} | {_pct(h['rollback_rate'])} "
                f"| {h['relapsed_faults']} |"
            )
    return "\n".join(lines)


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_hashes():
    """Hash the executable evaluation dependency graph, including uncommitted changes."""
    paths = []
    for folder in (
        "services/detector",
        "services/rca",
        "services/ml",
        "services/healer",
        "services/netsim",
        "services/evaluator",
        "ml",
        "contracts",
    ):
        paths += list((ROOT / folder).glob("*.py"))
    paths += [ROOT / "services/policy.py"]
    paths += list((ROOT / "config").glob("*.yaml")) + list((ROOT / "config").glob("*.rego"))
    return {p.relative_to(ROOT).as_posix(): _hash(p) for p in sorted(set(paths)) if p.is_file()}


def metadata(scenarios, suite="nominal"):
    packages = {}
    for name in (
        "numpy",
        "scikit-learn",
        "torch",
        "torch-geometric",
        "stable-baselines3",
        "regopy",
    ):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    models = [gnn.MODEL_PATH, forecast.MODEL_PATH, lstm_ae.MODEL_PATH, rl.MODEL_PATH]
    datasets = [ROOT / "data/scenarios.pt"]
    return {
        "schema_version": SCHEMA_VERSION,
        "suite": suite,
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": revision,
        "source_sha256": source_hashes(),
        "model_sha256": {
            p.relative_to(ROOT).as_posix(): _hash(p) if p.exists() else None for p in models
        },
        "dataset_sha256": {
            p.relative_to(ROOT).as_posix(): _hash(p) if p.exists() else None for p in datasets
        },
        "python_version": platform.python_version(),
        "packages": packages,
        "seed_range": [FIRST_SEED, FIRST_SEED + scenarios - 1],
        "base_seeds": BASE_SEEDS,
        "scenarios": scenarios,
        "policies": POLICIES,
        "run_s": RUN_TICKS * TICK_S,
        "evaluation_scope": "Single-fault/healthy synthetic fixed campus, same model as twin",
        "same_simulator": True,
        "single_fault_per_scenario": True,
        "plant_perturbation": None
        if suite == "nominal"
        else {
            "kind": "unmodeled_observation_delay",
            "latency_factor": STRESS_DELAY_FACTOR,
            "flows": STRESS_FLOWS,
            "windows_after_warmup_s": STRESS_WINDOWS_S,
            "included_in_twin": False,
            "scope": "Controlled synthetic mismatch; no emulator or real-network evidence",
        },
        "training_provenance": (
            "Pretrained weights preserved; original training lineage not reverified"
        ),
        "service_definition": {
            "loss_pct_lt": HEALTHY_LOSS_PCT,
            "latency_ratio_lte": LATENCY_TOLERANCE,
            "recovery_window_s": RECOVERED_TICKS * TICK_S,
            "verification_window_s": 3.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=300)
    parser.add_argument("--processes", type=int, default=8)
    parser.add_argument(
        "--stress-scenarios",
        type=int,
        default=0,
        help="Also replay this many seeds under bounded plant-only delay mismatch",
    )
    args = parser.parse_args()
    meta = metadata(args.scenarios)
    runs = evaluate(args.scenarios, args.processes)
    stress = None
    if args.stress_scenarios:
        stress_meta = metadata(args.stress_scenarios, "unmodeled_delay")
        stress_runs = evaluate(args.stress_scenarios, args.processes, "unmodeled_delay")
        stress_meta["generated_at"] = datetime.now(UTC).isoformat()
        stress = {"meta": stress_meta, "summary": summarize(stress_runs), "runs": stress_runs}
    if meta["source_sha256"] != source_hashes():
        raise RuntimeError("Evaluation code changed during the run; report was not published")
    meta["generated_at"] = datetime.now(UTC).isoformat()
    results = {
        "meta": meta,
        "summary": summarize(runs),
        "runs": runs,
        "stress": stress,
    }
    serialized = json.dumps(results, indent=1, allow_nan=False)
    report = markdown(results)
    archive = ROOT / "services/evaluator/results" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive.mkdir(parents=True, exist_ok=False)
    (archive / "evaluation.json").write_text(serialized, encoding="utf-8")
    (archive / "EVALUATION.md").write_text(report, encoding="utf-8")
    RESULTS.write_text(serialized, encoding="utf-8")
    REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
