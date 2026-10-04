import pytest

from services.detector.detector import WARMUP_TICKS, Detector
from services.netsim.engine import Network
from services.rca.engine import RCAEngine


def trained(seed: int = 3):
    net, det, rca = Network(seed=seed), Detector(), RCAEngine()
    for _ in range(WARMUP_TICKS):
        samples = net.step()
        det.update(samples)
        rca.update(samples, det.active, net)
    return net, det, rca


def step(net, det, rca):
    samples = net.step()
    det.update(samples)
    rca.update(samples, det.active, net)


@pytest.mark.parametrize(
    ("fault", "target", "severity", "cause", "max_ticks"),
    [
        ("link_down", "dist1-library", 1.0, "link_failure", 6),
        ("gray_failure", "dist1-library", 0.3, "gray_failure", 6),
        ("congestion", "dist3-lab_cs", 0.5, "congestion", 6),
        ("congestion", "dist3-lab_cs", 1.0, "congestion", 6),
        ("node_overload", "dist1", 0.5, "node_overload", 6),
        ("misconfig", "admin-internet", 1.0, "misconfig", 6),
        ("flapping", "dist1-hostel_a", 1.0, "flapping", 20),  # needs to see it flip twice
    ],
)
def test_top_hypothesis_names_cause_and_target(fault, target, severity, cause, max_ticks):
    net, det, rca = trained()
    net.inject_fault(fault, target, severity=severity)
    for _ in range(max_ticks):
        step(net, det, rca)
        if rca.hypotheses and (rca.hypotheses[0].cause, rca.hypotheses[0].target) == (
            cause,
            target,
        ):
            break
    top = rca.hypotheses[0]
    assert (top.cause, top.target) == (cause, target)
    assert top.confidence >= 0.7
    assert len(top.evidence) == 2


def test_healthy_network_has_no_diagnosis():
    net, det, rca = trained()
    for _ in range(40):
        step(net, det, rca)
    assert rca.hypotheses == [] and rca.incident_id is None


def test_incident_id_is_stable_then_resets_after_recovery():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    for _ in range(4):
        step(net, det, rca)
    first = rca.incident_id
    step(net, det, rca)
    assert first and rca.incident_id == first
    assert all(h.incident_id == first for h in rca.hypotheses)
    net.clear_faults()
    for _ in range(10):
        step(net, det, rca)
    assert rca.incident_id is None


def test_update_reports_only_changes():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    changes = []
    for _ in range(8):
        samples = net.step()
        det.update(samples)
        changes.append(rca.update(samples, det.active, net))
    assert 1 <= sum(changes) <= 2  # diagnosis appears once (maybe refined once), not every tick
