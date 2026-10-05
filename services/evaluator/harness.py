"""Evaluation harness: hundreds of injected faults, four policies, one results table.

Every scenario uses a held-out seed (never seen while training a model): a warmed-up campus
network gets one random fault (type, target, severity, sudden or gradual), or none as a
healthy control, and the same scenario is replayed under each policy:

  no_heal          detect and diagnose only: what happens without automatic healing
  reactive         rules-only diagnosis; apply the first detour, no twin test, no guardrails
  twin             rules + GNN diagnosis; twin-tested candidates behind the OPA guardrails
  predictive_twin  twin + the forecaster and LSTM autoencoder (the live configuration)

Run: make eval  (writes docs/evaluation.json and docs/EVALUATION.md)
"""

import argparse
import copy
import json
from multiprocessing import Pool
from pathlib import Path
from statistics import median

import numpy as np

from contracts.models import TwinPrediction
from ml.datagen import FAULT_TO_CAUSE, random_fault, voting_only
from services.detector.detector import WARMUP_TICKS, Detector
from services.healer.healer import Healer
from services.ml import forecast, gnn, lstm_ae
from services.ml.forecast import breached
from services.netsim.engine import TICK_S, Network
from services.rca.engine import RCAEngine

POLICIES = ("no_heal", "reactive", "twin", "predictive_twin")
BASE_SEEDS = (505, 606, 707, 808)  # training uses 101-404
FIRST_SEED = 1_000_000  # training uses scenario seeds 0..N
RUN_TICKS = 120  # 60 s after the fault (gradual faults ramp for up to 30 s)
RECOVERED_TICKS = 20  # every flow within SLA for the last 10 s
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "evaluation.json"
REPORT = ROOT / "docs" / "EVALUATION.md"


class ReactiveHealer(Healer):
    """Classic rule-based remediation: the first (shortest) detour, untested and unchecked.
    It is still verified and rolled back if it fails, like every policy here."""

    def _predict(self, c, net, affected) -> None:
        c.twin_prediction = TwinPrediction(latency_ms=0, loss_pct=0, max_util=0)
        c.opa_decision = "allow"


_bases: dict[tuple[int, bool], tuple] = {}


def base(seed: int, predictive: bool):
    """Network + detector warmed up on healthy traffic (cached per process)."""
    if (seed, predictive) not in _bases:
        net = Network(seed=seed)
        det = Detector(forecaster=forecast.load(), autoencoder=lstm_ae.load()) if predictive \
            else Detector()  # fmt: skip
        for _ in range(WARMUP_TICKS):
            det.update(net.step())
        _bases[seed, predictive] = (net, det)
    return _bases[seed, predictive]


def run(seed: int, policy: str) -> dict:
    """Replay one scenario under one policy."""
    net, det = (copy.deepcopy(x) for x in base(BASE_SEEDS[seed % len(BASE_SEEDS)],
                                               policy == "predictive_twin"))  # fmt: skip
    net.rng = np.random.default_rng(seed)
    fault = random_fault(np.random.default_rng(seed), net)
    rca = RCAEngine(gnn=None if policy == "reactive" else gnn.load())
    healer = ReactiveHealer() if policy == "reactive" else Healer()
    healer.level = 0 if policy == "no_heal" else 4
    baseline = {f: float(det.median[f][0]) for f in net.flows}
    if fault:
        net.inject_fault(*fault)

    detected = diagnosis = voting = healed = None
    applied = rollbacks = escalated = 0
    ok, latencies, losses = [], [], []
    for t in range(RUN_TICKS):
        samples = net.step()
        det.update(samples)
        rca.update(samples, det.active, net, detector=det)
        if det.active and detected is None:
            detected = t
        if rca.hypotheses and diagnosis is None:
            diagnosis = [(h.cause, h.target) for h in rca.hypotheses]
            voting = voting_only(net, det.active)
        for kind, payload in healer.update(samples, rca.hypotheses, net, baseline):
            if kind == "rebaseline":
                det.relearn(payload)
            applied += kind == "applied"
            escalated += kind == "escalated"
            if kind == "result":
                rollbacks += payload.rolled_back
                if payload.verified and healed is None:
                    healed = t
        flows = [s for s in samples if s.entity_type == "flow"]
        ok.append(not any(breached(s.latency_ms, s.loss_pct, baseline[s.entity_id])
                          for s in flows))  # fmt: skip
        latencies += [1000.0 if s.latency_ms is None else s.latency_ms for s in flows]
        losses += [s.loss_pct for s in flows]

    bad_ticks = [t for t, good in enumerate(ok) if not good]
    recovered = all(ok[-RECOVERED_TICKS:])
    truth = (FAULT_TO_CAUSE[fault[0]], fault[1]) if fault else None
    seconds = lambda t: None if t is None else round((t + 1) * TICK_S, 1)  # noqa: E731
    return {
        "seed": seed,
        "policy": policy,
        "fault": fault
        and {
            "type": fault[0],
            "target": fault[1],
            "severity": round(fault[2], 2),
            "ramp_s": fault[3],
        },  # fmt: skip
        "detected": detected is not None,
        "mttd_s": seconds(detected),
        "top1": None if not (truth and diagnosis) else diagnosis[0] == truth,
        "top3": None if not (truth and diagnosis) else truth in diagnosis[:3],
        "voting_top1": None if not (truth and diagnosis) else voting == truth[1],
        "healed": healed is not None,
        "mttr_s": seconds(healed),
        "applied": applied,
        "rollbacks": rollbacks,
        "escalated": bool(escalated),
        "sla_impact": bool(bad_ticks),
        "recovered": recovered,
        "recovery_s": (seconds(bad_ticks[-1]) if bad_ticks else 0.0) if recovered else None,
        "sla_violation_s": round(sum(not g for g in ok) * TICK_S, 1),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        "mean_loss_pct": round(float(np.mean(losses)), 3),
    }


def _job(args):
    return run(*args)


def evaluate(scenarios: int, processes: int = 8) -> list[dict]:
    jobs = [(FIRST_SEED + i, p) for i in range(scenarios) for p in POLICIES]
    with Pool(processes) as pool:
        return pool.map(_job, jobs, chunksize=4)


# ---- summary ---------------------------------------------------------------


def _rate(rows, key) -> float | None:
    values = [r[key] for r in rows if r[key] is not None]
    return round(sum(values) / len(values), 4) if values else None


def _median(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(median(values), 1) if values else None


def policy_summary(rows: list[dict], hurt: set[int]) -> dict:
    """hurt: seeds whose fault broke the SLA without healing. Every policy is judged on that
    same set, so a fix that lands before the SLA breaks counts as a recovery."""
    faults = [r for r in rows if r["fault"]]
    healthy = [r for r in rows if not r["fault"]]
    impact = [r for r in faults if r["seed"] in hurt]
    tp = sum(r["detected"] for r in faults)
    fp = sum(r["detected"] for r in healthy)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / len(faults) if faults else 0.0
    acted = [r for r in faults if r["applied"]]
    return {
        "scenarios": len(rows),
        "faults": len(faults),
        "healthy": len(healthy),
        "detection": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(2 * precision * recall / (precision + recall), 3) if tp else 0.0,
            "false_positive_rate": round(fp / len(healthy), 3) if healthy else None,
            "median_mttd_s": _median(r["mttd_s"] for r in faults),
            "median_mttd_gradual_s": _median(r["mttd_s"] for r in faults if r["fault"]["ramp_s"]),
        },
        "rca": {
            "top1": _rate(faults, "top1"),
            "top3": _rate(faults, "top3"),
            "voting_007_top1": _rate(faults, "voting_top1"),
        },
        "healing": {
            "sla_impacting_faults": len(impact),
            "recovered_rate": _rate(impact, "recovered"),
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
            "p95_latency_ms": _median(r["p95_latency_ms"] for r in impact),
            "mean_loss_pct": round(float(np.mean([r["mean_loss_pct"] for r in impact])), 3)
            if impact
            else None,  # fmt: skip
        },
    }


def summarize(runs: list[dict]) -> dict:
    by_policy = {p: [r for r in runs if r["policy"] == p] for p in POLICIES}
    types = sorted({r["fault"]["type"] for r in runs if r["fault"]})
    hurt = {r["seed"] for r in by_policy["no_heal"] if r["sla_impact"]}
    return {
        "policies": {p: policy_summary(rows, hurt) for p, rows in by_policy.items()},
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
        f"Generated by `make eval` ({meta['scenarios']} held-out scenarios × {len(POLICIES)} "
        f"policies, {meta['run_s']:.0f} s of simulated time each). Raw runs and the summary: "
        "`docs/evaluation.json`; charts on the dashboard's Evaluation page.",
        "",
        "Policies: `no_heal` detects and diagnoses only. `reactive` diagnoses with rules and "
        "applies the first detour, with no twin test and no guardrails. `twin` is NetHeal: "
        "rules + GNN diagnosis, twin-tested candidates behind the OPA guardrails. "
        "`predictive_twin` adds the forecaster and LSTM autoencoder (the live configuration).",
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
        row("SLA violation, total (s)", lambda x: f"{x['sla']['violation_s_total']:.0f}"),
        row("p95 flow latency during a fault", lambda x: f"{x['sla']['p95_latency_ms']} ms"),
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
        row("Root cause, top-1", lambda x: _pct(x["rca"]["top1"])),
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
        "judged on those same faults. A flow breaks its SLA when loss is above 2% or latency "
        "is more than double its healthy value.",
        "",
        "## Reading these numbers",
        "",
        "- `reactive` can recover a few more faults than `twin`: it ignores the blast-radius "
        "guardrail (at most 5 flows moved automatically), e.g. it moves every flow off a "
        "flapping internet uplink at once. NetHeal hands those to a human on purpose.",
        "- An overloaded access switch has no detour (the traffic starts there), so every "
        "policy escalates it.",
        "- No fix is rolled back: in the simulator every detour around the fault works, so "
        "testing on the twin first can't beat a plain detour on recovery here. Its value is "
        "safety (the guardrails see predicted load), and on real packets reality can differ.",
        "- The forecaster's value is earlier detection of gradual faults. Diagnosing earlier "
        "occasionally names the wrong cause first; it is corrected before anything is applied.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=300)
    parser.add_argument("--processes", type=int, default=8)
    args = parser.parse_args()
    runs = evaluate(args.scenarios, args.processes)
    results = {
        "meta": {"scenarios": args.scenarios, "policies": POLICIES, "run_s": RUN_TICKS * TICK_S},
        "summary": summarize(runs),
        "runs": runs,
    }
    RESULTS.write_text(json.dumps(results, indent=1))
    REPORT.write_text(markdown(results))
    print(REPORT.read_text())


if __name__ == "__main__":
    main()
