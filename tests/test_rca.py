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


def test_fault_on_idle_standby_link_is_reported_without_inflated_confidence():
    net, det, rca = trained()
    net.inject_fault("gray_failure", "dist4-cafeteria", severity=0.5)  # no flow uses dist4
    for _ in range(6):
        step(net, det, rca)
    top = rca.hypotheses[0]
    assert (top.cause, top.target) == ("gray_failure", "dist4-cafeteria")
    assert top.method_scores["voting"] == 0.5  # no affected flows: voting is neutral
    assert "No user traffic is affected yet" in top.evidence[1].description


def test_gnn_adds_a_third_opinion_when_a_model_is_loaded():
    from services.ml.gnn import load

    model = load()
    assert model is not None, "train it with: python -m ml.train_gnn"
    net, det, _ = trained()
    rca = RCAEngine(gnn=model)
    net.inject_fault("link_down", "dist1-library")
    for _ in range(5):
        samples = net.step()
        det.update(samples)
        rca.update(samples, det.active, net, detector=det)
    top = rca.hypotheses[0]
    assert (top.cause, top.target) == ("link_failure", "dist1-library")
    # Calibrated, not certain: a link that has just gone down is a flapping link about half the
    # time in the training data, so the GNN keeps some doubt until it sees the link stay down.
    assert top.method_scores["gnn"] > 0.5
    assert any("Graph neural network" in e.description for e in top.evidence)


def test_without_a_model_rca_is_unchanged():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    for _ in range(5):
        step(net, det, rca)
    assert "gnn" not in rca.hypotheses[0].method_scores
