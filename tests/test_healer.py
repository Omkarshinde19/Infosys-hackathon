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
