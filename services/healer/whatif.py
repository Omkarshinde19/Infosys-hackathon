"""What-if planner: "what happens if X breaks?", answered on a digital twin.

The live network is never touched: a snapshot gets the hypothetical fault, we measure who
suffers, then ask the healer (same twin dry-runs and Rego guardrails as production) what
it would do about it.
"""

from statistics import fmean

from contracts.models import RCAHypothesis, new_id
from services.healer.healer import Healer, _latency
from services.netsim.engine import Network

FAULT_TO_CAUSE = {
    "link_down": "link_failure", "gray_failure": "gray_failure", "congestion": "congestion",
    "flapping": "flapping", "node_overload": "node_overload", "misconfig": "misconfig",
}  # fmt: skip
BEFORE_TICKS, DURING_TICKS = 4, 6
HURT_LOSS_PCT, HURT_LATENCY_RATIO = 1.0, 1.5


def what_if(net: Network, healer: Healer, fault: str, target: str, severity: float = 1.0) -> dict:
    twin = net.snapshot()
    twin.clear_faults()
    before = [{s.entity_id: s for s in twin.step()} for _ in range(BEFORE_TICKS)]
    twin.inject_fault(fault, target, severity)  # raises ValueError for unknown faults/targets
    during = [{s.entity_id: s for s in twin.step()} for _ in range(DURING_TICKS)]

    impact = []
    for f in twin.flows:
        lat0 = fmean(t[f].latency_ms for t in before)
        lat1 = fmean(_latency(t[f]) for t in during)
        loss1 = fmean(t[f].loss_pct for t in during)
        if loss1 >= HURT_LOSS_PCT or lat1 >= HURT_LATENCY_RATIO * lat0:
            impact.append({
                "flow": f,
                "latency_before_ms": round(lat0, 2),
                "latency_during_ms": round(lat1, 2),
                "loss_during_pct": round(loss1, 2),
            })  # fmt: skip

    hypothesis = RCAHypothesis(
        incident_id=f"what-if-{new_id()[:8]}", cause=FAULT_TO_CAUSE[fault], target=target,
        confidence=1.0, evidence=[],
    )  # fmt: skip
    planner = Healer(healer.policy)
    candidates, affected = planner.plan(hypothesis, twin)
    best = next((c for c in candidates if c.opa_decision == "allow"), None)
    if not impact:
        verdict = "No user traffic would be affected; NetHeal would flag it for maintenance."
    elif best:
        verdict = "NetHeal would heal this automatically with the first fix below."
    else:
        verdict = "No safe automatic fix: NetHeal would escalate to a human."
    return {"impact": impact, "affected_flows": affected, "candidates": candidates,
            "best": best, "verdict": verdict}  # fmt: skip
