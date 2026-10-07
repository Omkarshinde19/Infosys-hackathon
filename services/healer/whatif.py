"""What-if planner: "what happens if X breaks?", answered on a digital twin.

The live network is never touched: a snapshot gets the hypothetical fault, we measure who
suffers, then ask the healer (same twin dry-runs and Rego guardrails as production) what
it would do about it.
"""

from statistics import fmean

from contracts.models import RCAHypothesis, new_id
from services.healer.healer import (
    SMALL_FIX_FLOWS,
    SMALL_FIX_RISK,
    Healer,
    _latency,
    _reference_baseline,
)
from services.netsim.engine import Network

FAULT_TO_CAUSE = {
    "link_down": "link_failure", "gray_failure": "gray_failure", "congestion": "congestion",
    "flapping": "flapping", "node_overload": "node_overload", "misconfig": "misconfig",
}  # fmt: skip
BEFORE_TICKS, DURING_TICKS = 4, 6
HURT_LOSS_PCT, HURT_LATENCY_RATIO = 1.0, 1.5


def what_if(
    net: Network,
    healer: Healer,
    fault: str,
    target: str,
    severity: float = 1.0,
    *,
    preserve_faults: bool = False,
) -> dict:
    twin = net.snapshot()
    if not preserve_faults:
        twin.clear_faults()
    reference = dict(healer.baseline) or _reference_baseline(twin)
    before = [{s.entity_id: s for s in twin.step()} for _ in range(BEFORE_TICKS)]
    twin.inject_fault(fault, target, severity)  # raises ValueError for unknown faults/targets
    during = [{s.entity_id: s for s in twin.step()} for _ in range(DURING_TICKS)]

    impact = []
    for f in twin.flows:
        lat0 = fmean(_latency(t[f]) for t in before)
        lat1 = fmean(_latency(t[f]) for t in during)
        loss1 = fmean(t[f].loss_pct for t in during)
        if loss1 >= HURT_LOSS_PCT or lat1 >= HURT_LATENCY_RATIO * lat0:
            impact.append({
                "flow": f,
                "latency_before_ms": round(lat0, 2),
                "latency_during_ms": round(lat1, 2),
                "loss_before_pct": round(fmean(t[f].loss_pct for t in before), 2),
                "loss_during_pct": round(loss1, 2),
                "throughput_before_mbps": round(fmean(t[f].throughput_mbps for t in before), 2),
                "throughput_during_mbps": round(fmean(t[f].throughput_mbps for t in during), 2),
            })  # fmt: skip

    hypothesis = RCAHypothesis(
        incident_id=f"what-if-{new_id()[:8]}", cause=FAULT_TO_CAUSE[fault], target=target,
        confidence=1.0, evidence=[],
    )  # fmt: skip
    planner = Healer(healer.policy, healer.rl)
    planner.level, planner.generation = healer.level, healer.generation
    planner.applied_at, planner.baseline = list(healer.applied_at), reference
    if planner.level == 0:
        candidates = []  # alert-only mode never creates a repair proposal
        if hypothesis.cause == "misconfig":
            affected = [target]
        elif target in twin.links:
            affected = [f for f, path in twin.routes.items() if target in twin.path_links(path)]
        else:
            affected = [f for f, path in twin.routes.items() if target in path]
    else:
        candidates, affected = planner.plan(hypothesis, twin, during[-1])
    best = next((c for c in candidates if c.opa_decision == "allow"), None)
    small = bool(
        best
        and len(best.params.get("routes", {})) <= SMALL_FIX_FLOWS
        and best.risk_score <= SMALL_FIX_RISK
    )
    approval_required = bool(best and (planner.level == 2 or (planner.level == 3 and not small)))
    if not impact:
        verdict = "No user traffic would be affected; NetHeal would flag it for maintenance."
    elif planner.level == 0:
        verdict = "NetHeal would alert a human; comfort level 0 does not plan or apply repairs."
    elif best:
        if planner.level == 1:
            verdict = "NetHeal would recommend the first fix below for a human to apply."
        elif approval_required:
            verdict = "NetHeal would request human approval for the first fix below."
        else:
            verdict = (
                "NetHeal would apply the first fix below automatically, then verify every service."
            )
    else:
        verdict = "No safe automatic fix: NetHeal would escalate to a human."
    return {"impact": impact, "affected_flows": affected, "candidates": candidates,
            "best": best, "verdict": verdict, "autonomy": planner.level,
            "approval_required": approval_required,
            "mode": "compound" if preserve_faults else "isolated"}  # fmt: skip
