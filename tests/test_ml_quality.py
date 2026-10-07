import numpy as np
import pytest

from services.ml.forecast import WINDOW, Forecaster, breached, flow_features, healthy_threshold
from services.netsim.engine import Network


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -1.0, 101.0])
def test_unknown_or_invalid_loss_cannot_be_counted_as_meeting_sla(bad):
    assert breached(5.0, bad, 5.0)
    assert flow_features([(5.0, bad)] * (WINDOW + 1), 5.0) is None


@pytest.mark.parametrize("baseline", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_baseline_cannot_generate_features_or_healthy_reading(baseline):
    assert breached(5.0, 0.0, baseline)
    assert flow_features([(5.0, 0.0)] * (WINDOW + 1), baseline) is None


def test_healthy_calibration_never_caps_threshold_below_a_healthy_score():
    p = np.array([0.01, 0.96, 1.0])
    threshold = healthy_threshold(p)
    assert threshold > p.max() and not np.any(p >= threshold)
    assert threshold > 1  # explicit abstention, rather than a false warning at 0.95
    assert healthy_threshold([0.0]) > 0
    with pytest.raises(ValueError):
        healthy_threshold([])


def test_forecaster_discards_invalid_history_and_model_scores():
    class Model:
        def predict_proba(self, x):
            return np.array([[0.0, float("nan")]] * len(x))

    forecaster = Forecaster(Model(), 0.8)
    net = Network()
    flow = next(s for s in net.step() if s.entity_type == "flow")
    baseline = {flow.entity_id: flow.latency_ms}
    for _ in range(WINDOW + 1):
        assert not forecaster.update([flow], baseline)
    bad = flow.model_copy(update={"loss_pct": float("nan")})
    assert not forecaster.update([bad], baseline)
    assert not forecaster.history[flow.entity_id]


def test_gnn_ensemble_drops_nonfinite_and_out_of_range_scores():
    import torch

    from services.ml.gnn import ensemble
    from services.ml.graph import CAUSES

    for value in (float("inf"), float("-inf"), -0.5, 2.0):
        probabilities = torch.full((1, len(CAUSES)), value)
        ranked = ensemble([("link_failure", "l", 0.9, 1.0)], probabilities, ["l"])
        assert len(ranked) == 1 and ranked[0][3] == 0
        assert np.isfinite(ranked[0][2])


def test_optional_rl_failure_or_invalid_action_abstains_without_crashing_healing():
    from services.ml.rl import RLPlanner

    class Broken:
        def predict(self, observation, deterministic):
            raise RuntimeError("model unavailable")

    net = Network()
    latest = {s.entity_id: s for s in net.step()}
    planner = RLPlanner(Broken())
    assert planner.propose(net, latest, "dist1-library") == {}
    assert "model unavailable" in planner.last_error

    class Invalid:
        def predict(self, observation, deterministic):
            return np.full(len(net.flows), 99), None

    planner = RLPlanner(Invalid())
    assert planner.propose(net, latest, "dist1-library") == {}
    assert "invalid" in planner.last_error


def test_rl_detects_topology_vocabulary_drift_and_invalid_observations():
    from services.ml.rl import RLPlanner

    class Model:
        def predict(self, observation, deterministic):
            return np.zeros(8, dtype=int), None

    net = Network()
    latest = {s.entity_id: s for s in net.step()}
    planner = RLPlanner(Model())
    planner.propose(net, latest, "dist1-library")
    latest["core1"].cpu = float("nan")
    assert planner.propose(net, latest, "dist1-library") == {}
    assert "Non-finite" in planner.last_error
    net.graph.remove_edge("dist4", "cafeteria")
    assert planner.propose(net, latest, "dist1-library") == {}
    assert "Topology" in planner.last_error
