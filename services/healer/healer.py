"""Decide -> heal -> verify, with digital-twin dry runs and automatic rollback.

1. Plan: turn the top diagnosis into candidate actions
   (link fault -> reroute around it, overloaded node -> drain it, misconfig -> roll back).
2. Twin: try every candidate on a snapshot of the network for TWIN_TICKS and record
   the predicted latency / loss / peak utilisation of the links it will use.
3. Guardrails: a candidate is allowed only if it restores the affected traffic,
   keeps the links it uses under MAX_UTIL and doesn't hurt any other flow.
4. Apply the best allowed candidate, watch the real network for VERIFY_TICKS and
   keep it if affected traffic is back to normal, otherwise roll back and try the next.
"""

from itertools import islice
from statistics import fmean

import networkx as nx

from contracts.models import ActionCandidate, ActionResult, RCAHypothesis, TwinPrediction
from services.netsim.engine import Network

MIN_CONFIDENCE = 0.7
MAX_CANDIDATES = 3
TWIN_TICKS = 6  # 3 s of simulated time
VERIFY_TICKS = 6
MAX_UTIL = 0.85
HEALTHY_LOSS_PCT = 1.0
LATENCY_TOLERANCE = 1.1  # within 10% of the healthy baseline
UNREACHABLE_MS = 1000.0  # how an unreachable flow counts in latency averages

Event = tuple[str, object]  # (kind, payload) streamed to the UI


class Healer:
    def __init__(self):
        self.handled: set[str] = set()  # incident ids already acted on
        self.pending: list[ActionCandidate] = []
        self.current: dict | None = None  # the action being verified
        self.status = "idle"

    def clear(self) -> None:
        self.__init__()

    def update(
        self, samples, hypotheses: list[RCAHypothesis], net: Network, baseline: dict[str, float]
    ) -> list[Event]:
        """Feed one tick (after detection + RCA). Returns events for the UI."""
        latest = {s.entity_id: s for s in samples}
        if self.current:
            return self._verify(latest, net, baseline)

        top = hypotheses[0] if hypotheses else None
        if not top or top.incident_id in self.handled or top.confidence < MIN_CONFIDENCE:
            return []
        self.handled.add(top.incident_id)

        candidates, affected = self.plan(top, net)
        if not affected:
            self.status = "no_action_needed"
            return [("no_action", "No user traffic is affected; flagged for maintenance.")]
        if not candidates:
            self.status = "escalated"
            return [("escalated", "No safe alternative exists; a human needs to step in.")]
        self.pending = [c for c in candidates if c.opa_decision == "allow"]
        if not self.pending:
            self.status = "escalated"
            reason = "No candidate passed the safety checks; a human needs to step in."
            return [("proposed", candidates), ("escalated", reason)]
        return [("proposed", candidates), *self._apply_next(latest, net, affected)]

    # ---- planning ----------------------------------------------------------

    def plan(self, h: RCAHypothesis, net: Network) -> tuple[list[ActionCandidate], list[str]]:
        """Candidate actions ranked by twin prediction, and the flows they are meant to fix."""
        if h.cause == "misconfig":
            candidates = [
                ActionCandidate(
                    incident_id=h.incident_id, type="rollback_config", params={"flow": h.target}
                )
            ]
            affected = [h.target]
        else:
            candidates, affected = self._reroutes(h, net)
        for c in candidates:
            self._predict(c, net, affected)
        candidates.sort(key=lambda c: (c.opa_decision != "allow", c.twin_prediction.loss_pct,
                                       c.twin_prediction.latency_ms))  # fmt: skip
        return candidates, affected

    def _reroutes(self, h: RCAHypothesis, net: Network):
        g = net.graph.copy()
        if h.target in net.links:
            g.remove_edge(*net.links[h.target])
            affected = [f for f, p in net.routes.items() if h.target in net.path_links(p)]
            kind, avoid = "reroute", [h.target]
        else:
            g.remove_node(h.target)
            affected = [f for f, p in net.routes.items() if h.target in p]
            kind, avoid = "drain_node", [h.target]
        if not affected:
            return [], []

        options = {}
        for f in affected:
            src, dst = net.flows[f]["src"], net.flows[f]["dst"]
            if src not in g or dst not in g or not nx.has_path(g, src, dst):
                return [], affected  # this flow can't be moved: escalate
            paths = nx.shortest_simple_paths(g, src, dst, weight="base_latency_ms")
            options[f] = list(islice(paths, MAX_CANDIDATES))

        candidates = []
        for k in range(MAX_CANDIDATES):
            routes = {f: opts[min(k, len(opts) - 1)] for f, opts in options.items()}
            if any(c.params["routes"] == routes for c in candidates):
                continue
            candidates.append(
                ActionCandidate(
                    incident_id=h.incident_id, type=kind, params={"avoid": avoid, "routes": routes}
                )
            )
        return candidates, affected

    def _predict(self, c: ActionCandidate, net: Network, affected: list[str]) -> None:
        twin = net.snapshot()
        self._execute(c, twin)
        ticks = [{s.entity_id: s for s in twin.step()} for _ in range(TWIN_TICKS)]
        others = [f for f in net.flows if f not in affected]
        latency = fmean(_latency(t[f]) for t in ticks for f in affected)
        loss = fmean(t[f].loss_pct for t in ticks for f in affected)
        other_loss = max(fmean(t[f].loss_pct for t in ticks) for f in others) if others else 0
        used = {lid for f in affected for lid in twin.path_links(twin.routes[f])}
        max_util = max(t[lid].util or 0 for t in ticks for lid in used)
        c.twin_prediction = TwinPrediction(latency_ms=latency, loss_pct=loss, max_util=max_util)
        c.risk_score = round(max_util, 3)
        safe = loss < HEALTHY_LOSS_PCT and max_util <= MAX_UTIL and other_loss < HEALTHY_LOSS_PCT
        c.opa_decision = "allow" if safe else "deny"

    # ---- executing ---------------------------------------------------------

    @staticmethod
    def _execute(c: ActionCandidate, net: Network) -> dict[str, list[str]]:
        """Apply an action; returns the routes needed to undo it."""
        if c.type == "rollback_config":
            net.rollback_config(c.params["flow"])
            return {}
        previous = {f: net.routes[f] for f in c.params["routes"]}
        for f, path in c.params["routes"].items():
            net.set_route(f, path)
        return previous

    def apply(self, c: ActionCandidate, latest, net: Network, affected: list[str]) -> list[Event]:
        """Apply one action now and start verifying it."""
        self.current = {
            "candidate": c,
            "affected": affected,
            "undo": self._execute(c, net),
            "before": _averages(latest, affected),
            "applied_at": net.now,
            "window": [],
        }
        self.status = "verifying"
        changed = _changed(self.current["undo"], net)
        return [("applied", c), *([("rebaseline", changed)] if changed else [])]

    def _apply_next(self, latest, net: Network, affected: list[str]) -> list[Event]:
        if not self.pending:
            self.status = "escalated"
            return [("escalated", "Every candidate failed verification; a human needs to step in.")]
        return self.apply(self.pending.pop(0), latest, net, affected)

    def _verify(self, latest, net: Network, baseline: dict[str, float]) -> list[Event]:
        cur = self.current
        cur["window"].append(latest)
        if len(cur["window"]) < VERIFY_TICKS:
            return []

        affected = cur["affected"]
        after = {
            k: fmean(_averages(t, affected)[k] for t in cur["window"])
            for k in ("latency_ms", "loss_pct")
        }
        healthy_latency = fmean(baseline[f] for f in affected)
        verified = (
            after["loss_pct"] < HEALTHY_LOSS_PCT
            and after["latency_ms"] <= LATENCY_TOLERANCE * healthy_latency
        )
        events = []
        if not verified:
            new_routes = {f: net.routes[f] for f in cur["undo"]}
            for f, path in cur["undo"].items():
                net.set_route(f, path)
            if changed := _changed(new_routes, net):
                events.append(("rebaseline", changed))
        result = ActionResult(
            action_id=cur["candidate"].id,
            applied_at=cur["applied_at"],
            verified=verified,
            rolled_back=not verified,
            before=cur["before"],
            after={**after, "baseline_latency_ms": healthy_latency},
        )
        self.current = None
        if verified:
            self.status = "healed"
            return [("result", result)]
        self.status = "rolled_back"
        return [("result", result), *events, *self._apply_next(latest, net, affected)]


def _changed(old_routes: dict[str, list[str]], net: Network) -> list[str]:
    """Links and nodes that now carry traffic they didn't before (their normal changed)."""
    old = {x for p in old_routes.values() for x in [*p, *net.path_links(p)]}
    new = {x for f in old_routes for x in [*net.routes[f], *net.path_links(net.routes[f])]}
    return sorted(new - old)


def _latency(s) -> float:
    return UNREACHABLE_MS if s.latency_ms is None else s.latency_ms


def _averages(latest, flows: list[str]) -> dict[str, float]:
    return {
        "latency_ms": fmean(_latency(latest[f]) for f in flows),
        "loss_pct": fmean(latest[f].loss_pct for f in flows),
    }
