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
    # Uncalibrated heuristic score: a link that has just gone down looks like a flapping
    # link in its "down" phase, so the GNN splits its belief roughly evenly between the two.
    assert top.method_scores["gnn"] > 0.4
    assert any("Graph neural network" in e.description for e in top.evidence)


def test_without_a_model_rca_is_unchanged():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    for _ in range(5):
        step(net, det, rca)
    assert "gnn" not in rca.hypotheses[0].method_scores


@pytest.mark.parametrize("value", [0.0, float("nan")])
def test_ensemble_ignores_a_gnn_with_no_valid_pick(value):
    """Seen live after an emu -> sim switch: masked probabilities with no usable maximum made
    the GNN's "top pick" the 'none' class, and building that hypothesis crashed RCA each tick."""
    import torch

    from services.ml.gnn import ensemble
    from services.ml.graph import CAUSES

    ids = ["dist1-library", "core1"]
    probs = torch.full((len(ids), len(CAUSES)), value)
    ranked = ensemble([("link_failure", "dist1-library", 0.9, 1.0)], probs, ids)
    assert [(c, t) for c, t, *_ in ranked] == [("link_failure", "dist1-library")]
    assert ranked[0][3] == 0.0


def test_forecast_only_risk_has_no_actionable_cause():
    from contracts.models import Anomaly

    net, det, rca = trained()
    samples = net.step()
    warning = Anomaly(
        ts=samples[0].ts,
        entity_id="library-internet",
        metric="predicted_sla_breach",
        value=0.95,
        baseline=0.9,
        score=0.95,
        detectors=["forecast"],
        severity="warning",
    )
    assert rca.update(samples, {warning.entity_id: warning}, net, detector=det)
    assert rca.diagnosis_status == "uncertain" and rca.uncertainty_reason
    assert not rca.hypotheses


def test_rca_refreshes_evidence_without_changing_hypothesis_identity():
    net, det, rca = trained()
    net.inject_fault("gray_failure", "dist1-library", severity=0.2)
    for _ in range(5):
        step(net, det, rca)
    first = rca.hypotheses[0]
    net.inject_fault("gray_failure", "dist1-library", severity=0.8)
    samples = net.step()
    det.update(samples)
    assert rca.update(samples, det.active, net, detector=det)
    fresh = next(h for h in rca.hypotheses if h.target == first.target)
    assert fresh.id == first.id and fresh.incident_id == first.incident_id
    assert fresh.evidence[0].description != first.evidence[0].description
    assert fresh.confidence_kind == "heuristic"


def test_invalid_or_missing_telemetry_causes_explicit_non_actuation_uncertainty():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    for _ in range(5):
        step(net, det, rca)
    samples = [s for s in net.step() if s.entity_id != "core2"]
    det.update(samples)
    rca.update(samples, det.active, net, detector=det)
    assert rca.diagnosis_status == "uncertain" and rca.uncertainty_reason
    assert all(not h.supported for h in rca.hypotheses)


def test_unreachable_flow_with_an_unobserved_path_is_not_named_misconfiguration():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    det.relearn(["dist1-library"])
    for _ in range(5):
        samples = net.step()
        det.update(samples)
    flow_only = {"library-internet": det.active["library-internet"]}
    rca.update(samples, flow_only, net, detector=det)
    assert not any(h.cause == "misconfig" for h in rca.hypotheses)


def test_a_clearing_old_alert_is_not_evidence_for_a_new_congestion_cause():
    net, det, rca = trained()
    net.inject_fault("link_down", "dist1-library")
    for _ in range(4):
        step(net, det, rca)
    assert rca.hypotheses[0].cause == "link_failure"
    net.clear_faults()
    samples = net.step()
    det.update(samples)
    assert det.active  # clear debounce has not expired
    rca.update(samples, det.active, net, detector=det)
    assert not rca.hypotheses and rca.diagnosis_status == "uncertain"


def test_idle_known_fault_does_not_explain_a_new_unrelated_service_symptom():
    from contracts.models import Anomaly

    net, det, rca = trained()
    net.inject_fault("link_down", "dist4-cafeteria")  # standby, no route uses this link
    for _ in range(4):
        step(net, det, rca)
    samples = net.step()
    det.update(samples)
    flow = "admin-internet"
    det.active[flow] = Anomaly(
        ts=samples[0].ts,
        entity_id=flow,
        metric="latency_ms",
        value=20,
        baseline=10,
        score=0.7,
        detectors=["service_sla"],
        severity="warning",
    )
    rca.update(samples, det.active, net, detector=det)
    assert flow in rca.unexplained_flows and rca.diagnosis_status == "uncertain"
    assert all(not h.supported for h in rca.hypotheses)
