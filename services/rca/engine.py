"""Root cause analysis: signature rules + 007-style flow voting.

For every anomalous link or node we ask two questions:
  1. Signature: what kind of fault does its telemetry look like?
     (down -> link_failure, busy -> congestion, lossy while up -> gray_failure,
      up/down repeatedly -> flapping, CPU spike -> node_overload)
  2. Voting (007, Arzani et al. NSDI'18): of all the flows that are suffering,
     what fraction pass through this element?
A flow that is unreachable although every element on its path looks healthy points
at its own forwarding rules (misconfig).

confidence = 0.6 * signature strength + 0.4 * vote share
"""

from collections import defaultdict, deque

from contracts.models import Anomaly, Evidence, RCAHypothesis, TelemetrySample, new_id
from services.netsim.engine import Network

FLAP_WINDOW = 20  # ticks of link up/down history (10 s)
FLAP_TRANSITIONS = 2
CONGESTED_UTIL = 0.8
LOSSY_PCT = 1.0
SIGNATURE_WEIGHT, VOTE_WEIGHT = 0.6, 0.4


class RCAEngine:
    def __init__(self):
        self.link_down: dict[str, deque[bool]] = defaultdict(lambda: deque(maxlen=FLAP_WINDOW))
        self.incident_id: str | None = None
        self.hypotheses: list[RCAHypothesis] = []

    def clear(self) -> None:
        self.link_down.clear()
        self.incident_id = None
        self.hypotheses = []

    def update(
        self, samples: list[TelemetrySample], active: dict[str, Anomaly], net: Network
    ) -> bool:
        """Feed one tick. Returns True when the ranked diagnosis changed."""
        latest = {s.entity_id: s for s in samples}
        for lid in net.links:
            self.link_down[lid].append(latest[lid].latency_ms is None)

        before = [(h.cause, h.target) for h in self.hypotheses]
        if not active:
            self.incident_id, self.hypotheses = None, []
        else:
            self.incident_id = self.incident_id or new_id()
            self.hypotheses = self._diagnose(latest, active, net)
        return before != [(h.cause, h.target) for h in self.hypotheses]

    # ---- diagnosis ---------------------------------------------------------

    def _diagnose(
        self, latest: dict[str, TelemetrySample], active: dict[str, Anomaly], net: Network
    ) -> list[RCAHypothesis]:
        bad_flows = [f for f in net.flows if f in active]
        path_links = {f: set(net.path_links(net.routes[f])) for f in net.flows}
        path_nodes = {f: set(net.routes[f]) for f in net.flows}

        def vote(on_path: dict[str, set[str]], element: str) -> tuple[float, Evidence]:
            if not bad_flows:  # e.g. an idle standby link: voting can't tell us anything
                text = "No user traffic is affected yet (idle or standby path)"
                return 0.5, Evidence(description=text, weight=VOTE_WEIGHT)
            hits = sum(element in on_path[f] for f in bad_flows)
            text = f"{hits} of {len(bad_flows)} affected flows pass through it"
            return hits / len(bad_flows), Evidence(description=text, weight=VOTE_WEIGHT)

        hypotheses = []
        for entity, anomaly in active.items():
            if entity in net.links:
                cause, strength, why = self._link_signature(entity, latest[entity], anomaly)
                share, vote_evidence = vote(path_links, entity)
            elif entity in net.graph.nodes:
                cause, strength = "node_overload", anomaly.score
                why = f"CPU at {latest[entity].cpu:.0%} (normal {anomaly.baseline:.0%})"
                share, vote_evidence = vote(path_nodes, entity)
            else:
                continue  # flows are symptoms; handled below
            hypotheses.append(
                self._hypothesis(cause, entity, strength, share, why, anomaly, vote_evidence)
            )

        # Unreachable flow with a healthy path: its own forwarding rules are wrong.
        for f in bad_flows:
            on_path = path_links[f] | path_nodes[f]
            if active[f].metric == "reachability" and not on_path & active.keys():
                why = "Unreachable although every link and device on its path is healthy"
                evidence = Evidence(description="Only this flow is affected", weight=VOTE_WEIGHT)
                hypotheses.append(
                    self._hypothesis("misconfig", f, 0.9, 1.0, why, active[f], evidence)
                )

        return sorted(hypotheses, key=lambda h: h.confidence, reverse=True)

    def _link_signature(self, lid: str, s: TelemetrySample, a: Anomaly) -> tuple[str, float, str]:
        history = list(self.link_down[lid])
        flips = sum(x != y for x, y in zip(history, history[1:], strict=False))
        if flips >= FLAP_TRANSITIONS:
            return "flapping", 1.0, f"Went up/down {flips} times in the last {FLAP_WINDOW // 2} s"
        if s.latency_ms is None:
            return "link_failure", 1.0, "Link is down: no traffic gets through"
        if s.util is not None and s.util >= CONGESTED_UTIL:
            return "congestion", a.score, f"Utilisation at {s.util:.0%} of capacity"
        if s.loss_pct is not None and s.loss_pct >= LOSSY_PCT:
            why = f"Packet loss {s.loss_pct:.1f}% while utilisation is only {s.util:.0%}"
            return "gray_failure", a.score, why
        return "congestion", a.score, f"Latency {s.latency_ms:.1f} ms (normal {a.baseline:.1f} ms)"

    def _hypothesis(self, cause, target, strength, share, why, anomaly, vote_evidence):
        return RCAHypothesis(
            incident_id=self.incident_id,
            cause=cause,
            target=target,
            confidence=round(SIGNATURE_WEIGHT * strength + VOTE_WEIGHT * share, 3),
            evidence=[
                Evidence(anomaly_id=anomaly.id, description=why, weight=SIGNATURE_WEIGHT),
                vote_evidence,
            ],
            method_scores={"signature": round(strength, 3), "voting": round(share, 3)},
        )
