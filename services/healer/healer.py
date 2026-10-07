"""Decide -> heal -> verify, with digital-twin dry runs and automatic rollback.

1. Plan: turn the top diagnosis into candidate actions
   (link fault -> reroute around it, overloaded node -> drain it, misconfig -> roll back).
2. Twin: try every candidate on a snapshot of the network for TWIN_TICKS and record
   the predicted latency / loss / peak utilisation of the links it will use.
3. Guardrails: the OPA Rego policy (config/healing.rego) must allow the candidate:
   it restores the traffic, keeps links under 85%, hurts no other flow, limits the
   blast radius and the rate of automatic changes.
4. Apply the best allowed candidate, watch the real network for VERIFY_TICKS and
   keep it if affected traffic is back to normal, otherwise roll back and try the next.
   After that, keep watching: if the fixed traffic breaks again for VERIFY_TICKS while the
   incident is still open (e.g. a worsening fault outgrew a mitigation), plan once more.
5. Comfort (autonomy) level decides who pulls the trigger, see LEVELS.

With a trained RL routing agent (services/ml/rl.py), its proposal joins the candidates in
step 1 and goes through the same twin dry run and guardrails.
"""

import copy
import hashlib
import json
import math
from datetime import timedelta
from itertools import islice
from statistics import fmean

import networkx as nx

from contracts.models import ActionCandidate, ActionResult, RCAHypothesis, TwinPrediction
from services.netsim.engine import TICK_S, Network
from services.policy import Policy

MIN_CONFIDENCE = 0.7
MAX_CANDIDATES = 3
JOINT_BEAM_WIDTH = 32
MAX_JOINT_CANDIDATES = 3
TWIN_TICKS = 6  # 3 s of simulated time
VERIFY_TICKS = 6
HEALTHY_LOSS_PCT = 1.0
MAX_SERVICE_LINK_UTIL = 0.85
LATENCY_TOLERANCE = 1.1  # within 10% of the healthy baseline
UNREACHABLE_MS = 1000.0  # how an unreachable flow counts in latency averages
APPROVAL_TTL_S = 30.0
MAX_SAMPLE_AGE_S = 2 * TICK_S
SUPPORTED_ACTIONS = {"reroute", "drain_node", "rollback_config"}

Event = tuple[str, object]  # (kind, payload) streamed to the UI

LEVELS = {
    0: "Alert only: detect and diagnose, no fix planned",
    1: "Recommend: plan and test fixes, a human applies them",
    2: "Ask approval: apply a fix only after a human approves it",
    3: "Auto for small fixes: one flow at low risk is automatic, bigger fixes need approval",
    4: "Fully automatic",
}
SMALL_FIX_FLOWS = 1
SMALL_FIX_RISK = 0.6


class Healer:
    def __init__(self, policy: Policy | None = None, rl=None):
        self.policy = policy or Policy()
        self.rl = rl  # optional RLPlanner
        self.level = 4
        self.awaiting: ActionCandidate | None = None  # waiting for a human (levels 2-3)
        self.awaiting_affected: list[str] = []
        self.applied_at: list = []  # sim timestamps of applied actions (rate limit)
        # A diagnosis is planned for once. An incident whose fix was applied or handed to a
        # human is never re-planned, but after an escalation a *corrected* diagnosis can be.
        self.tried: set[tuple[str, str, str]] = set()  # (incident, cause, target)
        self.acted: set[str] = set()  # incident ids
        self.pending: list[ActionCandidate] = []
        self.holding: dict | None = None  # a verified fix being watched: incident, flows, bad
        self.relapsed: set[str] = set()  # incidents re-planned once already
        self.current: dict | None = None  # the action being verified
        self.status = "idle"
        self.baseline: dict[str, float] = {}
        self.generation: str | None = None
        self.no_action_state: dict[str, str] = {}
        self.awaiting_diagnosis: tuple[str, str, str] | None = None
        self.awaiting_reason: str | None = None
        self.latest_diagnosis: tuple[str, str, str] | None = None
        self.latest_supported: bool | None = None

    def set_level(self, level: int) -> None:
        """Changing autonomy invalidates unexecuted decisions, preserving verification."""
        if isinstance(level, bool) or not isinstance(level, int) or level not in LEVELS:
            raise ValueError("Comfort level must be an integer from 0 to 4")
        if level == self.level:
            return
        self.level = level
        self.awaiting, self.awaiting_diagnosis, self.awaiting_reason = None, None, None
        self.pending = []
        if self.current is None and self.holding is None:
            self.acted.clear()
            self.tried.clear()
            self.no_action_state.clear()
            self.status = "idle"

    def clear(self) -> None:
        level = self.level
        generation = self.generation
        self.__init__(self.policy, self.rl)
        self.level = level  # a network reset keeps the chosen comfort level
        self.generation = generation

    def update(
        self, samples, hypotheses: list[RCAHypothesis], net: Network, baseline: dict[str, float]
    ) -> list[Event]:
        """Feed one tick (after detection + RCA). Returns events for the UI."""
        latest = {s.entity_id: s for s in samples}
        self.baseline = dict(baseline)
        # A repaired component can remain faulty and highly ranked while its
        # traffic uses a safe detour. Prefer a supported diagnosis that explains
        # a currently unhealthy routed service over that maintenance-only fault.
        top = next(
            (
                h
                for h in hypotheses
                if h.supported
                and h.confidence >= MIN_CONFIDENCE
                and (flows := _affected(h, net))
                and not _healthy(latest, flows, baseline)
            ),
            hypotheses[0] if hypotheses else None,
        )
        self.latest_diagnosis = (top.incident_id, top.cause, top.target) if top else None
        self.latest_supported = bool(top and top.supported and top.confidence >= MIN_CONFIDENCE)
        if self.current:
            return self._verify(latest, net, baseline)
        if self.holding and (relapse := self._watch(latest, [top] if top else [], baseline)):
            return relapse
        if self.awaiting and (
            not hypotheses or hypotheses[0].incident_id != self.awaiting.incident_id
        ):
            self.awaiting, self.pending, self.status = None, [], "idle"

        if self.awaiting:
            if not top.supported or top.confidence < MIN_CONFIDENCE:
                self.awaiting_reason = (
                    "The current diagnosis no longer has sufficient observed support."
                )
            elif (
                self.awaiting_diagnosis is not None
                and self.latest_diagnosis != self.awaiting_diagnosis
            ):
                self.awaiting_reason = "The supported diagnosis changed while this fix waited."
        if (
            not top
            or not top.supported
            or top.confidence < MIN_CONFIDENCE
            or top.incident_id in self.acted
        ):
            return []
        valid_target = (
            top.target in net.flows
            if top.cause == "misconfig"
            else top.target in net.graph.nodes
            if top.cause == "node_overload"
            else top.target in net.links
        )
        if not valid_target:
            self.status = "escalated"
            return [("escalated", "The diagnosis names an invalid target; no action was applied.")]
        key = (top.incident_id, top.cause, top.target)
        if top.incident_id in self.no_action_state and self.no_action_state[
            top.incident_id
        ] != self._fingerprint(net):
            self.tried = {k for k in self.tried if k[0] != top.incident_id}
            del self.no_action_state[top.incident_id]
        if key in self.tried:
            return []
        self.tried.add(key)
        if self.level == 0:
            self.acted.add(top.incident_id)
            self.status = "alert_only"
            return [("alert_only", "Comfort level 0 (alert only): no fix was planned.")]

        candidates, affected = self.plan(top, net, latest)
        if not affected:
            if not _healthy(latest, list(net.flows), baseline):
                self.status = "escalated"
                return [
                    (
                        "escalated",
                        "The named component carries no traffic, but service recovery is "
                        "unverified; a supported diagnosis is required.",
                    )
                ]
            self.no_action_state[top.incident_id] = self._fingerprint(net)
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
        best = self.pending[0]
        if self.level == 1:
            self.acted.add(top.incident_id)  # a human decides from here
            self.status = "recommended"
            return [("proposed", candidates), ("recommended", best)]
        small = (
            len(best.params.get("routes", {})) <= SMALL_FIX_FLOWS
            and best.risk_score <= SMALL_FIX_RISK
        )
        if self.level == 2 or (self.level == 3 and not small):
            self.acted.add(top.incident_id)
            self.awaiting, self.awaiting_affected = best, affected
            self.awaiting_diagnosis, self.awaiting_reason = key, None
            self.status = "awaiting_approval"
            return [("proposed", candidates), ("awaiting_approval", best)]
        return [("proposed", candidates), *self._apply_next(latest, net, affected)]

    def approve(self, action_id: str, latest, net: Network, baseline=None) -> list[Event]:
        """A human approved the waiting fix: test it again on the twin and the safety rules
        (the network may have changed while it waited), then apply it and start verifying."""
        if not self.awaiting or self.awaiting.id != action_id:
            raise KeyError(action_id)
        c, affected = self.awaiting, self.awaiting_affected
        self.awaiting = None
        self.pending.remove(c)
        if baseline is not None:
            self.baseline = dict(baseline)
        stale = self._stale_reason(c, latest, net)
        if stale:
            return self._replan(c, stale)
        self._predict(c, net, affected)
        if c.opa_decision != "allow":  # stale: plan again from the network as it is now
            why = "; ".join(c.policy_reasons)
            reason = f"The network changed while this fix waited and it now fails: {why}."
            return self._replan(c, reason)
        return [("approved", c.id), *self.apply(c, latest, net, affected)]

    def _replan(self, c, reason: str) -> list[Event]:
        self.acted.discard(c.incident_id)
        self.tried = {k for k in self.tried if k[0] != c.incident_id}
        self.pending = []
        self.awaiting_diagnosis, self.awaiting_reason = None, None
        self.status = "replanning"
        return [("replanning", f"{reason} Planning again; no action was applied.")]

    def _stale_reason(self, c, latest, net) -> str | None:
        if self.awaiting_reason:
            return self.awaiting_reason
        if c.expires_at is not None and net.now >= c.expires_at:
            return "The approval expired."
        if c.planning_version != self.generation:
            return "The network generation changed."
        if c.state_fingerprint is not None and c.state_fingerprint != self._fingerprint(net):
            return "The routes, faults, topology or policy changed while this fix waited."
        return _sample_error(latest, list(net.flows), net.now)

    def _fingerprint(self, net) -> str:
        state = {
            "generation": self.generation,
            "level": self.level,
            "routes": net.routes,
            "faults": {key: vars(fault) for key, fault in net.faults.items()},
            "links": sorted(
                (d["id"], d["capacity_mbps"], d["base_latency_ms"])
                for _, _, d in net.graph.edges(data=True)
            ),
            "flows": net.flows,
            "policy": getattr(self.policy, "source", type(self.policy).__name__),
        }
        return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()

    def reject(self, action_id: str) -> list[Event]:
        if not self.awaiting or self.awaiting.id != action_id:
            raise KeyError(action_id)
        self.awaiting, self.pending, self.status = None, [], "rejected"
        self.awaiting_diagnosis, self.awaiting_reason = None, None
        return [("rejected", action_id)]

    # ---- planning ----------------------------------------------------------

    def plan(
        self, h: RCAHypothesis, net: Network, latest: dict | None = None
    ) -> tuple[list[ActionCandidate], list[str]]:
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
            if (
                self.rl
                and latest
                and affected
                and (routes := self.rl.propose(net, latest, h.target))
            ):
                kind = "reroute" if h.target in net.links else "drain_node"
                params = {"avoid": [h.target], "routes": routes, "planner": "rl"}
                candidates.append(
                    ActionCandidate(incident_id=h.incident_id, type=kind, params=params)
                )
        for c in candidates:
            self._predict(c, net, affected)
            c.planned_at = net.now
            c.expires_at = net.now + timedelta(seconds=APPROVAL_TTL_S)
            c.state_fingerprint = self._fingerprint(net)
            c.planning_version = self.generation
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
        # Independent kth-shortest paths miss useful combinations: two services may
        # each fit on either detour, but overload it when they both choose the same one.
        # Keep those simple alternatives, then add a bounded joint beam search. Its
        # load estimate ranks proposals only; the twin and policy remain authoritative.
        for routes in self._joint_routes(options, affected, net):
            if not any(c.params["routes"] == routes for c in candidates):
                candidates.append(
                    ActionCandidate(
                        incident_id=h.incident_id,
                        type=kind,
                        params={"avoid": avoid, "routes": routes, "planner": "capacity"},
                    )
                )
        return candidates, affected

    @staticmethod
    def _joint_routes(options, affected, net):
        down, _, extra_load, _, blackholed = net._fault_state()
        base_load = dict.fromkeys(net.links, 0.0)
        base_load.update(extra_load)
        for fid, path in net.routes.items():
            if (
                fid not in affected
                and fid not in blackholed
                and not down.intersection(net.path_links(path))
            ):
                for lid in net.path_links(path):
                    base_load[lid] += net.flows[fid]["demand_mbps"]
        capacities = {
            lid: net.graph.edges[a, b]["capacity_mbps"] for lid, (a, b) in net.links.items()
        }
        beam = [({}, base_load, 0.0)]
        # Largest demands first reduce the chance that the bounded beam prunes the
        # only viable placement for a large service after filling a small detour.
        ordered = sorted(affected, key=lambda fid: (-net.flows[fid]["demand_mbps"], fid))
        for fid in ordered:
            expanded = []
            for routes, load, distance in beam:
                for path in options[fid]:
                    next_load = dict(load)
                    for lid in net.path_links(path):
                        next_load[lid] += net.flows[fid]["demand_mbps"]
                    path_distance = sum(
                        net.graph.edges[a, b]["base_latency_ms"]
                        for a, b in zip(path, path[1:], strict=False)
                    )
                    expanded.append(({**routes, fid: path}, next_load, distance + path_distance))

            def score(state):
                routes, load, distance = state
                util = [load[lid] / capacities[lid] for lid in net.links]
                return (
                    sum(max(0.0, value - 0.85) for value in util),
                    max(util),
                    sum(value * value for value in util),
                    distance,
                    tuple((f, tuple(routes[f])) for f in sorted(routes)),
                )

            beam = sorted(expanded, key=score)[:JOINT_BEAM_WIDTH]
        return [routes for routes, _, _ in beam[:MAX_JOINT_CANDIDATES]]

    def _predict(self, c: ActionCandidate, net: Network, affected: list[str]) -> None:
        try:
            self._validate_action(c, net)
            if not affected or any(f not in net.flows for f in affected):
                raise ValueError("The action has no valid affected services")
            reference = self.baseline or _reference_baseline(net)
            twin = net.snapshot()
            self._execute(c, twin)
            ticks = [{s.entity_id: s for s in twin.step()} for _ in range(TWIN_TICKS)]
            per_flow = _flow_window(ticks, list(net.flows))
            others = [f for f in net.flows if f not in affected]
            latency = fmean(per_flow[f]["latency_ms"] for f in affected)
            loss = fmean(per_flow[f]["loss_pct"] for f in affected)
            max_loss = max(per_flow[f]["loss_pct"] for f in affected)
            other_loss = max((per_flow[f]["loss_pct"] for f in others), default=0.0)
            other_latency = max(
                (
                    per_flow[f]["latency_ms"] / reference[f]
                    for f in others
                    if reference.get(f, 0) > 0
                ),
                default=0.0,
            )
            used = {lid for f in net.flows for lid in twin.path_links(twin.routes[f])}
            max_util = max((t[lid].util or 0 for t in ticks for lid in used), default=0.0)
            c.twin_prediction = TwinPrediction(
                latency_ms=latency,
                loss_pct=loss,
                max_util=max_util,
                max_loss_pct=max_loss,
                other_latency_ratio=other_latency,
                per_flow=per_flow,
            )
            c.risk_score = round(max_util, 3)
            avoid = c.params.get("avoid") or [None]
            target = avoid[0]
            c.policy_reasons = self.policy.evaluate(
                {
                    "action": {
                        "type": c.type,
                        "target_layer": net.graph.nodes[target]["layer"]
                        if target in net.graph
                        else None,
                        "flows_moved": list(c.params.get("routes", {})) or [c.params.get("flow")],
                    },
                    "prediction": {
                        "loss_pct": loss,
                        "max_loss_pct": max_loss,
                        "max_util": max_util,
                        "other_loss_pct": other_loss,
                        "other_latency_ratio": other_latency,
                    },
                    "actions_last_minute": sum(
                        0 <= (net.now - t).total_seconds() < 60 for t in self.applied_at
                    ),
                }
            )
            c.policy_reasons += _flow_reasons(per_flow, affected, reference)
            c.policy_reasons += _flow_reasons(per_flow, others, reference, collateral=True)
            c.policy_reasons = sorted(set(c.policy_reasons))
        except Exception as error:
            # Invalid or failed model execution is evidence against applying the proposal.
            c.twin_prediction = TwinPrediction(latency_ms=UNREACHABLE_MS, loss_pct=100, max_util=1)
            c.policy_reasons = [f"Preflight failed: {type(error).__name__}: {error}"]
        c.opa_decision = "deny" if c.policy_reasons else "allow"

    # ---- executing ---------------------------------------------------------

    @staticmethod
    def _validate_action(c: ActionCandidate, net: Network) -> None:
        if c.type not in SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action capability: {c.type}")
        if c.type == "rollback_config":
            if c.params.get("flow") not in net.flows:
                raise ValueError("Configuration rollback must name a known flow")
            return
        routes = c.params.get("routes")
        if not isinstance(routes, dict) or not routes:
            raise ValueError("Rerouting requires a nonempty flow-to-path mapping")
        for fid, path in routes.items():
            if fid not in net.flows or not isinstance(path, list) or len(path) < 2:
                raise ValueError(f"Invalid route for {fid}")
            f = net.flows[fid]
            if (
                path[0] != f["src"]
                or path[-1] != f["dst"]
                or len(set(path)) != len(path)
                or not nx.is_path(net.graph, path)
            ):
                raise ValueError(f"Invalid simple path for {fid}: {path}")

    @staticmethod
    def _execute(c: ActionCandidate, net: Network) -> dict[str, list[str]]:
        """Apply an action; returns the routes needed to undo it."""
        Healer._validate_action(c, net)  # validate every route before changing any of them
        if c.type == "rollback_config":
            net.rollback_config(c.params["flow"])
            return {}
        previous = {f: list(net.routes[f]) for f in c.params["routes"]}
        for f, path in c.params["routes"].items():
            net.set_route(f, path)
        return previous

    def apply(self, c: ActionCandidate, latest, net: Network, affected: list[str]) -> list[Event]:
        """Apply one action now and start verifying it."""
        before = _averages(latest, affected)
        per_flow_before = _flow_window([latest], list(net.flows))
        undo = {"routes": {}, "faults": None}
        execution_started = False
        try:
            self._validate_action(c, net)
            if error := _sample_error(latest, list(net.flows), net.now):
                raise ValueError(error)
            undo["routes"] = {f: list(net.routes[f]) for f in c.params.get("routes", {})}
            if c.type == "rollback_config":
                undo["faults"] = copy.deepcopy(
                    {
                        key: fault
                        for key, fault in net.faults.items()
                        if (fault.type, fault.target) == ("misconfig", c.params["flow"])
                    }
                )
            self.applied_at.append(net.now)
            self.acted.add(c.incident_id)
            execution_started = True
            self._execute(c, net)
        except Exception as error:
            restored, rollback_error = self._restore(undo, net)
            reason = f"Action execution failed: {type(error).__name__}: {error}"
            result = ActionResult(
                action_id=c.id,
                applied_at=net.now,
                verified=False,
                rolled_back=execution_started and restored,
                before=before,
                after={},
                per_flow_before=per_flow_before,
                rollback_attempted=execution_started,
                rollback_error=rollback_error,
                failure_reason=reason,
                outcome="execution_failed" if restored else "rollback_failed",
            )
            self.current, self.pending, self.status = None, [], "escalated"
            return [("result", result), ("escalated", reason)]
        self.current = {
            "candidate": c,
            "affected": affected,
            "undo": undo,
            "before": before,
            "per_flow_before": per_flow_before,
            "baseline": dict(self.baseline),
            "applied_at": net.now,
            "window": [],
            "sample_errors": [],
        }
        self.status = "verifying"
        changed = _changed(undo["routes"], net)
        return [("applied", c), *([("rebaseline", changed)] if changed else [])]

    @staticmethod
    def _restore(undo, net) -> tuple[bool, str | None]:
        errors = []
        for fid, path in undo["routes"].items():
            try:
                net.set_route(fid, list(path))
            except Exception as error:
                errors.append(f"{fid}: {type(error).__name__}: {error}")
        if undo["faults"] is not None:
            if hasattr(net, "request"):
                errors.append("Configuration undo is not supported by the emulated backend")
            else:
                # Restore only faults removed by this action. Replacing the entire
                # fault dictionary would erase a new independent fault observed
                # while verification was running.
                net.faults.update(copy.deepcopy(undo["faults"]))
        return not errors, "; ".join(errors) or None

    def _watch(self, latest, hypotheses, baseline: dict[str, float]) -> list[Event]:
        """After a verified fix: re-plan (once) if the fixed traffic breaks again."""
        h = self.holding
        if not hypotheses or hypotheses[0].incident_id != h["incident"]:
            self.holding = None  # the incident ended (or a new one began)
            return []
        h["bad"] = 0 if _healthy(latest, h["services"], h["baseline"] or baseline) else h["bad"] + 1
        if h["bad"] < VERIFY_TICKS:
            return []
        self.holding = None
        events = [
            (
                "relapsed",
                "The verified service state stopped holding; "
                "service recovery is no longer confirmed.",
            )
        ]
        if h["incident"] in self.relapsed:
            self.status = "escalated"
            return [
                *events,
                (
                    "escalated",
                    "The incident relapsed again after its recovery retry; "
                    "a human needs to step in.",
                ),
            ]
        self.relapsed.add(h["incident"])
        if not hypotheses[0].supported or hypotheses[0].confidence < MIN_CONFIDENCE:
            self.status = "escalated"
            return [*events, ("escalated", "The new cause isn't clear; a human needs to step in.")]
        self.acted.discard(h["incident"])  # plan again from the current diagnosis
        self.tried = {k for k in self.tried if k[0] != h["incident"]}
        self.status = "relapsed"
        return events

    def _apply_next(self, latest, net: Network, affected: list[str]) -> list[Event]:
        if self.latest_supported is False:
            self.pending, self.status = [], "escalated"
            return [
                (
                    "escalated",
                    "The current diagnosis has insufficient observed support for another repair.",
                )
            ]
        rejected = []
        while self.pending:
            candidate = self.pending.pop(0)
            # A failed earlier attempt or new fault can invalidate old queued predictions.
            self._predict(candidate, net, affected)
            if candidate.opa_decision == "allow":
                candidate.planned_at = net.now
                candidate.expires_at = net.now + timedelta(seconds=APPROVAL_TTL_S)
                candidate.state_fingerprint = self._fingerprint(net)
                candidate.planning_version = self.generation
                if self.level == 0:
                    self.pending, self.status = [], "alert_only"
                    return [("alert_only", "Comfort level 0: the alternative was not applied.")]
                if self.level == 1:
                    self.pending, self.status = [], "recommended"
                    return [("recommended", candidate)]
                small = (
                    len(candidate.params.get("routes", {})) <= SMALL_FIX_FLOWS
                    and candidate.risk_score <= SMALL_FIX_RISK
                )
                if self.level == 2 or (self.level == 3 and not small):
                    # Approval authorizes one candidate, not every alternative in
                    # its batch. A failed approved attempt needs fresh consent.
                    self.awaiting, self.awaiting_affected = candidate, affected
                    self.awaiting_diagnosis, self.awaiting_reason = self.latest_diagnosis, None
                    self.pending.insert(0, candidate)
                    self.status = "awaiting_approval"
                    return [("awaiting_approval", candidate)]
                return self.apply(candidate, latest, net, affected)
            rejected.append("; ".join(candidate.policy_reasons))
        self.status = "escalated"
        reason = (
            "Every candidate failed current safety checks or verification; "
            "a human needs to step in."
        )
        if rejected:
            reason += " " + " | ".join(rejected)
        return [("escalated", reason)]

    def _verify(self, latest, net: Network, baseline: dict[str, float]) -> list[Event]:
        cur = self.current
        cur["window"].append(latest)
        if error := _sample_error(latest, list(net.flows), net.now):
            cur["sample_errors"].append(error)
        if error := _util_error(latest, net):
            cur["sample_errors"].append(error)
        if len(cur["window"]) < VERIFY_TICKS:
            return []

        affected = cur["affected"]
        per_flow_after = _flow_window(cur["window"], list(net.flows))
        after = {
            k: fmean(per_flow_after[f][k] for f in affected) for k in ("latency_ms", "loss_pct")
        }
        reference = cur["baseline"] or baseline
        healthy_latency = fmean(reference.get(f, 0.0) for f in affected)
        reasons = [*cur["sample_errors"], *_flow_reasons(per_flow_after, affected, reference)]
        others = [f for f in net.flows if f not in affected]
        reasons += _flow_reasons(per_flow_after, others, reference, collateral=True)
        verified = not reasons
        events = []
        restored, rollback_error = False, None
        if not verified:
            new_routes = {f: list(net.routes[f]) for f in cur["undo"]["routes"]}
            restored, rollback_error = self._restore(cur["undo"], net)
            if changed := _changed(new_routes, net):
                events.append(("rebaseline", changed))
        result = ActionResult(
            action_id=cur["candidate"].id,
            applied_at=cur["applied_at"],
            verified=verified,
            rolled_back=not verified and restored,
            before=cur["before"],
            after={**after, "baseline_latency_ms": healthy_latency},
            per_flow_before=cur["per_flow_before"],
            per_flow_after=per_flow_after,
            rollback_attempted=not verified,
            rollback_error=rollback_error,
            failure_reason="; ".join(sorted(set(reasons))) or None,
            verification_reasons=sorted(set(reasons)),
            outcome="verified" if verified else "rolled_back" if restored else "rollback_failed",
        )
        self.current = None
        if verified:
            self.status = "healed"
            self.holding = {
                "incident": cur["candidate"].incident_id,
                "affected": affected,
                "services": list(net.flows),
                "baseline": dict(reference),
                "bad": 0,
            }
            return [("result", result)]
        if rollback_error:
            self.pending, self.status = [], "escalated"
            return [
                ("result", result),
                *events,
                ("escalated", f"Rollback failed: {rollback_error}"),
            ]
        self.status = "rolled_back"
        return [("result", result), *events, *self._apply_next(latest, net, affected)]


def _healthy(latest, flows: list[str], baseline: dict[str, float]) -> bool:
    return not _flow_reasons(_flow_window([latest], flows), flows, baseline)


def _affected(h, net) -> list[str]:
    if h.cause == "misconfig":
        return [h.target] if h.target in net.flows else []
    if h.cause == "node_overload":
        return [fid for fid, path in net.routes.items() if h.target in path]
    if h.target in net.links:
        return [fid for fid, path in net.routes.items() if h.target in net.path_links(path)]
    return []


def _sample_error(latest, flows, now) -> str | None:
    for fid in flows:
        sample = latest.get(fid)
        if sample is None or sample.loss_pct is None or sample.throughput_mbps is None:
            return f"Missing service telemetry for {fid}"
        try:
            age = (now - sample.ts).total_seconds()
        except (AttributeError, TypeError, ValueError):
            return f"Invalid service timestamp for {fid}"
        if age < 0 or age > MAX_SAMPLE_AGE_S:
            return f"Service telemetry for {fid} is stale or belongs to another clock"
        values = (sample.loss_pct, sample.throughput_mbps)
        if sample.latency_ms is not None:
            values += (sample.latency_ms,)
        if any(_finite_metric(value) is None for value in values):
            return f"Invalid service telemetry for {fid}"
    return None


def _util_error(latest, net) -> str | None:
    used = {lid for fid in net.flows for lid in net.path_links(net.routes[fid])}
    for lid in sorted(used):
        sample = latest.get(lid)
        if sample is None or _finite_metric(sample.util) is None:
            return f"Missing or invalid service-link utilisation telemetry for {lid}"
        try:
            age = (net.now - sample.ts).total_seconds()
        except (AttributeError, TypeError, ValueError):
            return f"Invalid service-link timestamp for {lid}"
        if age < 0 or age > MAX_SAMPLE_AGE_S:
            return f"Service-link telemetry for {lid} is stale or belongs to another clock"
        if sample.util > MAX_SERVICE_LINK_UTIL:
            return f"Service link {lid} utilisation exceeds the 85% safety limit"
    return None


def _flow_window(ticks, flows) -> dict[str, dict[str, float | bool]]:
    per_flow = {}
    for fid in flows:
        rows = [tick.get(fid) for tick in ticks]
        reachable = bool(rows) and all(
            s is not None
            and _finite_metric(s.latency_ms) is not None
            and _finite_metric(s.loss_pct) is not None
            for s in rows
        )
        per_flow[fid] = {
            "latency_ms": fmean(
                _finite_metric(s.latency_ms, UNREACHABLE_MS) if s is not None else UNREACHABLE_MS
                for s in rows
            ),
            "loss_pct": fmean(
                _finite_metric(s.loss_pct, 100.0) if s is not None else 100.0 for s in rows
            ),
            "throughput_mbps": fmean(
                _finite_metric(s.throughput_mbps, 0.0) if s is not None else 0.0 for s in rows
            ),
            "reachable": reachable,
        }
    return per_flow


def _finite_metric(value, missing=None):
    return (
        value
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
        else missing
    )


def _flow_reasons(per_flow, flows, baseline, collateral=False) -> list[str]:
    reasons = []
    prefix = "Collateral service" if collateral else "Affected service"
    for fid in flows:
        row = per_flow[fid]
        if not row["reachable"]:
            reasons.append(f"{prefix} {fid} is unreachable or missing telemetry")
        if row["loss_pct"] >= HEALTHY_LOSS_PCT:
            reasons.append(f"{prefix} {fid} loss {row['loss_pct']:.2f}% exceeds the <1% SLA")
        reference = baseline.get(fid)
        if _finite_metric(reference) is None or reference <= 0:
            reasons.append(f"{prefix} {fid} has no valid healthy latency baseline")
        elif row["latency_ms"] > LATENCY_TOLERANCE * reference:
            reasons.append(f"{prefix} {fid} latency exceeds 110% of its healthy baseline")
    return reasons


def _reference_baseline(net) -> dict[str, float]:
    """Direct planning callers without a detector use an explicitly fault-free twin reference."""
    reference = net.snapshot()
    reference.clear_faults()
    ticks = [{s.entity_id: s for s in reference.step()} for _ in range(TWIN_TICKS)]
    return {f: fmean(_latency(t[f]) for t in ticks) for f in net.flows}


def _changed(old_routes: dict[str, list[str]], net: Network) -> list[str]:
    """Links and nodes that now carry traffic they didn't before (their normal changed)."""
    old = {x for p in old_routes.values() for x in [*p, *net.path_links(p)]}
    new = {x for f in old_routes for x in [*net.routes[f], *net.path_links(net.routes[f])]}
    return sorted(new - old)


def _latency(s) -> float:
    return UNREACHABLE_MS if s.latency_ms is None else s.latency_ms


def _averages(latest, flows: list[str]) -> dict[str, float]:
    if not flows:
        return {"latency_ms": UNREACHABLE_MS, "loss_pct": 100.0}
    values = _flow_window([latest], flows)
    return {
        "latency_ms": fmean(values[f]["latency_ms"] for f in flows),
        "loss_pct": fmean(values[f]["loss_pct"] for f in flows),
    }
