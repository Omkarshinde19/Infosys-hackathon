"""Root cause analysis: signature rules + 007-style flow voting.

For every anomalous link or node we ask two questions:
  1. Signature: what kind of fault does its telemetry look like?
     (down -> link_failure, busy -> congestion, lossy while up -> gray_failure,
      up/down repeatedly -> flapping, CPU spike -> node_overload)
  2. Voting (007, Arzani et al. NSDI'18): of all the flows that are suffering,
     what fraction pass through this element?
A flow that is unreachable although every element on its path looks healthy points
at its own forwarding rules (misconfig).

confidence = 0.6 * signature strength + 0.4 * vote share. This is a heuristic
ranking score, not a calibrated probability of the cause being correct.

With a trained root-cause GNN (services/ml/gnn.py) the ranking becomes an ensemble:
confidence = 0.45 * signature + 0.25 * vote + 0.30 * GNN probability.
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
    def __init__(self, gnn=None):
        self.gnn = gnn  # optional RootCauseGNN
        self.link_down: dict[str, deque[bool]] = defaultdict(lambda: deque(maxlen=FLAP_WINDOW))
        self.incident_id: str | None = None
        self.hypotheses: list[RCAHypothesis] = []
        self.diagnosis_status = "healthy"
        self.uncertainty_reason: str | None = None
        self.unexplained_flows: list[str] = []

    def clear(self) -> None:
        self.link_down.clear()
        self.incident_id = None
        self.hypotheses = []
        self.diagnosis_status = "healthy"
        self.uncertainty_reason = None
        self.unexplained_flows = []

    def update(
        self, samples: list[TelemetrySample], active: dict[str, Anomaly], net: Network,
        detector=None,
    ) -> bool:  # fmt: skip
        """Publish refreshed scores/evidence while preserving incident and hypothesis IDs.

        Forecasts and bad telemetry describe risk/uncertainty, not an actionable cause.
        A model-only hypothesis is explicitly unsupported until observed rules agree.
        """
        latest = {s.entity_id: s for s in samples}
        quality = getattr(detector, "quality_issues", {})
        for lid in net.links:
            if lid in latest and lid not in quality:
                self.link_down[lid].append(latest[lid].latency_ms is None)

        before = self._publication()
        previous = {(h.cause, h.target): h.id for h in self.hypotheses}
        if not active:
            self.incident_id, self.hypotheses = None, []
            self.diagnosis_status, self.uncertainty_reason = "healthy", None
            self.unexplained_flows = []
        else:
            self.incident_id = self.incident_id or new_id()
            observed = {
                e: a
                for e, a in active.items()
                if e in latest
                and e not in quality
                and a.ts == latest[e].ts
                and a.detectors not in (["forecast"], ["telemetry_quality"])
            }
            self.hypotheses = self._diagnose(latest, observed, net)
            if self.hypotheses and self.gnn is not None and detector is not None and not quality:
                self.hypotheses = self._with_gnn(self.hypotheses, latest, net, detector)
            for h in self.hypotheses:
                h.id = previous.get((h.cause, h.target), h.id)
                if quality:
                    h.supported = False
                    h.evidence.append(
                        Evidence(
                            description="Invalid telemetry prevents safe cause confirmation",
                            weight=0.0,
                        )
                    )
            self.unexplained_flows = [
                f
                for f in net.flows
                if f in observed
                and not any(
                    h.supported
                    and (
                        h.target == f
                        if h.cause == "misconfig"
                        else h.target in net.routes[f] or h.target in net.path_links(net.routes[f])
                    )
                    for h in self.hypotheses
                )
            ]
            if self.unexplained_flows:
                for h in self.hypotheses:
                    h.supported = False
                    h.evidence.append(
                        Evidence(
                            description=(
                                "This cause does not fully explain current service symptoms"
                            ),
                            weight=0.0,
                        )
                    )
            supported = bool(self.hypotheses and self.hypotheses[0].supported)
            self.diagnosis_status = "supported" if supported else "uncertain"
            self.uncertainty_reason = (
                None
                if supported
                else (
                    "Telemetry is missing, stale or invalid; a cause cannot be established."
                    if quality
                    else "Current degraded flows have no supported cause on their paths."
                    if self.unexplained_flows
                    else "Forecast risk or anomalous symptoms do not identify a cause."
                )
            )
        return before != self._publication()

    def _publication(self):
        return (
            self.diagnosis_status,
            self.uncertainty_reason,
            self.unexplained_flows,
            [
                (
                    h.cause,
                    h.target,
                    h.confidence,
                    h.supported,
                    h.method_scores,
                    [(e.anomaly_id, e.description, e.weight) for e in h.evidence],
                )
                for h in self.hypotheses
            ],
        )

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
            h = self._hypothesis(cause, entity, strength, share, why, anomaly, vote_evidence)
            if (
                entity in net.links
                and anomaly.metric == "latency_ms"
                and (
                    (latest[entity].loss_pct or 0) < LOSSY_PCT
                    and (latest[entity].util or 0) < CONGESTED_UTIL
                )
            ):
                h.supported = False  # latency alone cannot distinguish congestion from device delay
                h.evidence[0].description += "; latency alone does not establish congestion"
            hypotheses.append(h)

        # Unreachable flow with a healthy path: its own forwarding rules are wrong.
        for f in bad_flows:
            on_path = path_links[f] | path_nodes[f]
            path_observed_healthy = all(
                e in latest
                and (latest[e].entity_type == "node" or latest[e].latency_ms is not None)
                for e in on_path
            )
            if (
                active[f].metric == "reachability"
                and path_observed_healthy
                and not on_path & active.keys()
            ):
                why = "Unreachable although every link and device on its path is healthy"
                evidence = Evidence(description="Only this flow is affected", weight=VOTE_WEIGHT)
                hypotheses.append(
                    self._hypothesis("misconfig", f, 0.9, 1.0, why, active[f], evidence)
                )

        return sorted(hypotheses, key=lambda h: h.confidence, reverse=True)

    def _with_gnn(self, hypotheses, latest, net: Network, detector) -> list[RCAHypothesis]:
        from services.ml.gnn import W_GNN, ensemble, probabilities
        from services.ml.graph import EntityGraph, features, link_flips

        graph = EntityGraph(net)
        x = features(graph, latest, detector, link_flips(self))
        probs = probabilities(self.gnn, x, graph.edge_index, graph.kinds)
        rules = [(h.cause, h.target, h.method_scores["signature"], h.method_scores["voting"])
                 for h in hypotheses]  # fmt: skip
        by_key = {(h.cause, h.target): h for h in hypotheses}
        ranked = []
        for cause, target, confidence, p in ensemble(rules, probs, graph.ids):
            h = by_key.get((cause, target)) or RCAHypothesis(
                incident_id=self.incident_id, cause=cause, target=target, confidence=0,
                evidence=[], method_scores={"signature": 0.0, "voting": 0.5}, supported=False,
            )  # fmt: skip
            h.confidence = round(confidence, 3)
            h.method_scores["gnn"] = round(p, 3)
            h.evidence.append(
                Evidence(
                    description=f"Graph neural network uncalibrated score: {p:.0%}", weight=W_GNN
                )
            )
            ranked.append(h)
        return ranked

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
            util = f"{s.util:.0%}" if s.util is not None else "unavailable"
            why = f"Packet loss {s.loss_pct:.1f}% while utilisation is {util}"
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
