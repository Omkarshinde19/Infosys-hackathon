import pytest

from contracts.models import ActionCandidate
from services.detector.detector import WARMUP_TICKS, Detector
from services.healer.healer import Healer
from services.healer.incidents import IncidentTracker
from services.netsim.engine import TICK_S, Network
from services.rca.engine import RCAEngine


class Pipeline:
    """The full detect -> diagnose -> decide -> heal loop, as the gateway runs it."""

    def __init__(self, seed: int = 3):
        self.net, self.det, self.rca = Network(seed=seed), Detector(), RCAEngine()
        self.healer, self.incidents = Healer(), IncidentTracker()
        self.events: list = []
        for _ in range(WARMUP_TICKS):
            self.tick()

    def baseline(self):
        return {f: self.det.median[f][0] for f in self.net.flows} if self.det.ready else {}

    def tick(self):
        samples = self.net.step()
        self.det.update(samples)
        self.rca.update(samples, self.det.active, self.net, detector=self.det)
        events = []
        if self.det.ready:
            events = self.healer.update(samples, self.rca.hypotheses, self.net, self.baseline())
        self.relearn(events)
        self.incidents.update(self.net.now, self.det.active, self.rca.hypotheses, events)
        self.events += events
        self.latest = {s.entity_id: s for s in samples}

    def relearn(self, events):
        for kind, payload in events:
            if kind == "rebaseline":
                self.det.relearn(payload)

    def inject(self, *args, **kwargs):
        self.net.inject_fault(*args, **kwargs)
        self.incidents.note_fault(self.net.now)

    def run_until(self, status: str, max_ticks: int) -> int:
        for t in range(1, max_ticks + 1):
            self.tick()
            if self.healer.status == status:
                return t
        raise AssertionError(f"healer stuck at {self.healer.status!r} after {max_ticks} ticks")


@pytest.mark.parametrize(
    ("fault", "target", "severity", "flows"),
    [
        ("link_down", "dist1-library", 1.0, ["library-internet"]),
        ("gray_failure", "dist1-library", 0.5, ["library-internet"]),
        ("congestion", "dist3-lab_cs", 1.0, ["lab_cs-internet", "lab_cs-admin"]),
        ("node_overload", "dist1", 0.6, ["library-internet", "hostel_a-internet"]),
        ("misconfig", "admin-internet", 1.0, ["admin-internet"]),
        ("flapping", "dist1-hostel_a", 1.0, ["hostel_a-internet"]),
    ],
)
def test_every_fault_is_healed_within_15_seconds(fault, target, severity, flows):
    p = Pipeline()
    baseline = p.baseline()
    p.inject(fault, target, severity=severity)
    p.run_until("healed", max_ticks=int(15 / TICK_S))

    for _ in range(4):  # traffic stays healthy after the fix
        p.tick()
        for f in flows:
            assert p.latest[f].loss_pct < 1
            assert p.latest[f].latency_ms <= 1.1 * baseline[f]

    inc = p.incidents.current or p.incidents.history[-1]  # a full fix closes the incident
    assert inc.status == "resolved"
    assert 1 <= inc.mttd_s <= 3  # measured from the real fault start, not from detection
    assert inc.mttd_s < inc.mttr_s <= 15
    assert [e.stage for e in inc.timeline][:5] == ["detect", "diagnose", "decide", "heal", "verify"]


def test_twin_ranks_candidates_and_guardrails_label_them():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    proposed = next(payload for kind, payload in p.events if kind == "proposed")
    assert len(proposed) >= 2
    assert all(c.twin_prediction is not None and c.opa_decision for c in proposed)
    best = proposed[0]
    assert best.opa_decision == "allow"
    assert best.twin_prediction.loss_pct < 1
    assert "dist1-library" not in str(best.params["routes"])


def test_bad_action_is_rolled_back():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    original = list(p.net.routes["library-internet"])
    still_broken = ["library", "dist1", "core2", "internet"]  # still crosses the dead link
    bad = ActionCandidate(
        incident_id="manual",
        type="reroute",
        params={"avoid": [], "routes": {"library-internet": still_broken}},
    )
    applied = p.healer.apply(bad, p.latest, p.net, ["library-internet"])
    p.relearn(applied)
    p.events += applied
    p.run_until("escalated", max_ticks=10)  # nothing left to try after the rollback
    result = next(payload for kind, payload in p.events if kind == "result")
    assert result.rolled_back and not result.verified
    assert p.net.routes["library-internet"] == original


def test_fault_on_idle_link_needs_no_action():
    p = Pipeline()
    p.inject("gray_failure", "dist4-cafeteria", severity=0.5)
    p.run_until("no_action_needed", max_ticks=10)
    assert all(kind != "applied" for kind, _ in p.events)
    # Deciding that nothing needs fixing is still a decision: the timeline shows it.
    incident = p.incidents.current or p.incidents.history[-1]
    assert [e.stage for e in incident.timeline][:3] == ["detect", "diagnose", "decide"]


def test_overloaded_building_switch_cannot_be_drained_so_it_escalates():
    p = Pipeline()
    p.inject("node_overload", "lab_cs")
    p.run_until("escalated", max_ticks=10)
    assert p.incidents.current.status == "failed"


def test_incident_closes_after_reset():
    p = Pipeline()
    p.inject("misconfig", "admin-internet")
    p.run_until("healed", max_ticks=30)
    for _ in range(10):
        p.tick()
    assert p.incidents.current is None
    assert p.incidents.history[-1].timeline[-1].stage == "close"


def test_incident_keeps_its_context_after_closing():
    p = Pipeline()
    p.inject("misconfig", "admin-internet")
    p.run_until("healed", max_ticks=30)
    for _ in range(10):
        p.tick()
    inc = p.incidents.history[-1]
    assert p.incidents.get(inc.id) is inc
    ctx = p.incidents.context[inc.id]
    assert "admin-internet" in ctx["anomalies"]
    assert ctx["diagnosis"][0].cause == "misconfig"
    assert [a["kind"] for a in ctx["actions"]] == ["proposed", "applied", "result"]


@pytest.mark.parametrize(
    ("fault", "target", "severity"),
    [("congestion", "dist1-hostel_a", 1.0), ("link_down", "dist1-library", 1.0)],
)
def test_new_path_is_not_flagged_after_healing(fault, target, severity):
    """Traffic moved onto an idle backup path is the new normal, not an anomaly."""
    p = Pipeline()
    p.inject(fault, target, severity=severity)
    p.run_until("healed", max_ticks=30)
    for _ in range(40):
        p.tick()
    assert set(p.det.active) == {target}  # only the faulty part stays flagged
    assert any(kind == "rebaseline" for kind, _ in p.events)


def test_gnn_still_names_the_root_cause_after_traffic_was_rerouted():
    from services.ml.gnn import load

    p = Pipeline()
    p.rca = RCAEngine(gnn=load())
    p.inject("gray_failure", "dist1-hostel_b", severity=0.6)
    p.run_until("healed", max_ticks=30)
    for _ in range(4):
        p.tick()
    top = p.rca.hypotheses[0]
    assert (top.cause, top.target) == ("gray_failure", "dist1-hostel_b")
    assert top.method_scores["gnn"] > 0.5  # it learned post-heal situations from the twin


def test_policy_blocks_draining_a_core_router_and_escalates():
    p = Pipeline()
    p.inject("node_overload", "core1", severity=0.6)
    p.run_until("escalated", max_ticks=20)
    proposed = next(payload for kind, payload in p.events if kind == "proposed")
    assert all(c.opa_decision == "deny" for c in proposed)
    assert all(any("core router" in r for r in c.policy_reasons) for c in proposed)
    assert all(kind != "applied" for kind, _ in p.events)


def kinds(p):
    return [kind for kind, _ in p.events]


def test_level_0_only_alerts():
    p = Pipeline()
    p.healer.level = 0
    p.inject("link_down", "dist1-library")
    p.run_until("alert_only", max_ticks=10)
    assert "proposed" not in kinds(p) and "applied" not in kinds(p)


def test_level_1_recommends_but_never_applies():
    p = Pipeline()
    p.healer.level = 1
    p.inject("link_down", "dist1-library")
    p.run_until("recommended", max_ticks=10)
    for _ in range(10):
        p.tick()
    assert "recommended" in kinds(p) and "applied" not in kinds(p)


def test_level_2_waits_for_approval_then_heals():
    p = Pipeline()
    p.healer.level = 2
    p.inject("link_down", "dist1-library")
    p.run_until("awaiting_approval", max_ticks=10)
    for _ in range(6):  # nothing happens while it waits
        p.tick()
    assert "applied" not in kinds(p)
    pending = p.healer.awaiting
    p.events += p.healer.approve(pending.id, p.latest, p.net)
    p.run_until("healed", max_ticks=10)
    assert "applied" in kinds(p)


def test_level_2_rejection_applies_nothing():
    p = Pipeline()
    p.healer.level = 2
    p.inject("link_down", "dist1-library")
    p.run_until("awaiting_approval", max_ticks=10)
    p.events += p.healer.reject(p.healer.awaiting.id)
    assert p.healer.status == "rejected" and p.healer.awaiting is None
    for _ in range(6):
        p.tick()
    assert "applied" not in kinds(p)


@pytest.mark.parametrize(
    ("fault", "target", "status"),
    [("link_down", "dist1-library", "healed"),  # moves 1 flow: small, automatic
     ("node_overload", "dist1", "awaiting_approval")],  # moves several flows: ask first
)  # fmt: skip
def test_level_3_automates_only_small_fixes(fault, target, status):
    p = Pipeline()
    p.healer.level = 3
    p.inject(fault, target, severity=0.6)
    p.run_until(status, max_ticks=20)


def test_replans_when_a_premature_diagnosis_is_corrected():
    """On real networks the flow's alarm can arrive before its link's. RCA then first blames a
    misconfiguration; once the link alarm arrives it corrects to link failure, and the healer
    must act on the corrected diagnosis instead of staying escalated."""
    from contracts.models import RCAHypothesis

    net, healer = Network(seed=1), Healer()
    net.inject_fault("link_down", "dist1-library")
    samples = net.step()
    baseline = {f: 9.0 for f in net.flows}

    def hypothesis(cause, target):
        return [
            RCAHypothesis(
                incident_id="inc-1", cause=cause, target=target, confidence=0.9, evidence=[]
            )
        ]

    first = healer.update(samples, hypothesis("misconfig", "library-internet"), net, baseline)
    assert healer.status == "escalated" and "applied" not in [k for k, _ in first]

    second = healer.update(samples, hypothesis("link_failure", "dist1-library"), net, baseline)
    assert "applied" in [k for k, _ in second]  # acted on the corrected diagnosis

    healer.current = None  # pretend verification finished
    healer.status = "healed"
    third = healer.update(samples, hypothesis("flapping", "dist1-library"), net, baseline)
    assert third == []  # once a fix is applied, a refined diagnosis doesn't trigger another


class FakeRL:
    """Stands in for the trained agent: proposes fixed routes."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def propose(self, net, latest, target):
        self.calls.append(target)
        return self.routes


def _broken_library(healer):
    from contracts.models import RCAHypothesis

    net = Network(seed=3)
    net.inject_fault("link_down", "dist1-library")
    latest = {s.entity_id: s for s in net.step()}
    h = RCAHypothesis(incident_id="i", cause="link_failure", target="dist1-library",
                      confidence=0.9, evidence=[], method_scores={})  # fmt: skip
    return healer.plan(h, net, latest)


def test_rl_proposal_is_twin_tested_and_policy_checked_like_any_fix():
    detour = ["library", "dist2", "core1", "internet"]
    rl = FakeRL({"library-internet": detour})
    candidates, affected = _broken_library(Healer(rl=rl))
    assert rl.calls == ["dist1-library"] and affected == ["library-internet"]
    proposal = next(c for c in candidates if c.params.get("planner") == "rl")
    assert proposal.params["routes"] == {"library-internet": detour}
    assert proposal.params["avoid"] == ["dist1-library"]
    assert proposal.twin_prediction.loss_pct < 1 and proposal.opa_decision == "allow"


def test_a_bad_rl_proposal_loses_to_the_rule_fixes():
    through_fault = ["library", "dist1", "core2", "internet"]  # still crosses the dead link
    candidates, _ = _broken_library(Healer(rl=FakeRL({"library-internet": through_fault})))
    assert candidates[0].params.get("planner") != "rl"
    assert candidates[-1].params.get("planner") == "rl"
    assert candidates[-1].twin_prediction.loss_pct > 50


def test_no_rl_candidate_when_the_agent_moves_nothing():
    candidates, _ = _broken_library(Healer(rl=FakeRL({})))
    assert all(c.params.get("planner") != "rl" for c in candidates)


def test_replans_when_a_verified_fix_stops_holding():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    assert p.net.routes["library-internet"][1] == "dist2"
    p.net.inject_fault("gray_failure", "dist2-library", severity=1.0)  # the detour breaks too
    p.run_until("escalated", max_ticks=30)  # no third path: a human, not a false "healed"
    kinds = [k for k, _ in p.events]
    assert kinds.count("relapsed") == 1
    assert kinds.index("relapsed") > kinds.index("result")
    assert p.incidents.current.status == "failed"


def test_a_fix_that_keeps_holding_is_left_alone():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    for _ in range(30):
        p.tick()
    assert p.healer.status == "healed"
    assert "relapsed" not in [k for k, _ in p.events]


def test_a_clear_new_cause_after_a_relapse_is_fixed_again():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    detour = p.net.routes["library-internet"]
    uplink = p.net.path_links(detour)[1]  # e.g. dist2 -> core2: the detour's own uplink
    p.net.inject_fault("link_down", uplink)
    p.run_until("relapsed", max_ticks=10)
    p.run_until("healed", max_ticks=40)
    assert uplink not in p.net.path_links(p.net.routes["library-internet"])
    assert [k for k, _ in p.events].count("relapsed") == 1


def test_alert_only_level_does_not_claim_the_incident_is_resolved():
    # At comfort level 0 nothing is fixed: the traffic is still broken, so the incident
    # must say a human was alerted, not that it is resolved.
    p = Pipeline()
    p.healer.level = 0
    p.inject("link_down", "dist1-library")
    p.run_until("alert_only", max_ticks=10)
    incident = p.incidents.current
    assert incident.status == "alerted"
    assert [e.stage for e in incident.timeline][:3] == ["detect", "diagnose", "decide"]


def test_an_approval_is_rechecked_against_the_network_as_it_is_now():
    p = Pipeline()
    p.healer.level = 2
    p.inject("link_down", "dist1-library")
    p.run_until("awaiting_approval", max_ticks=10)
    fix = p.healer.awaiting
    detour = fix.params["routes"]["library-internet"]
    p.net.inject_fault("link_down", p.net.path_links(detour)[0])  # the detour breaks too
    p.tick()
    events = p.healer.approve(fix.id, p.latest, p.net)
    assert "applied" not in [k for k, _ in events]  # a stale fix is never applied
    assert p.net.routes["library-internet"] != detour
    assert p.healer.status == "replanning"
