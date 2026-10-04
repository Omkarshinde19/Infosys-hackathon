import pytest

from services.detector.detector import WARMUP_TICKS, Detector
from services.netsim.engine import TICK_S, Network


def trained(seed: int = 3) -> tuple[Network, Detector]:
    net, det = Network(seed=seed), Detector()
    for _ in range(WARMUP_TICKS):
        det.update(net.step())
    assert det.ready
    return net, det


def ticks_until_detected(net: Network, det: Detector, entity: str, max_ticks: int = 20) -> int:
    for tick in range(1, max_ticks + 1):
        raised, _ = det.update(net.step())
        if any(a.entity_id == entity for a in raised):
            return tick
    raise AssertionError(f"{entity} not detected within {max_ticks} ticks")


def test_no_false_alerts_in_five_healthy_minutes():
    net, det = trained()
    for _ in range(int(300 / TICK_S)):
        raised, _ = det.update(net.step())
        assert raised == []


@pytest.mark.parametrize(
    ("fault", "target", "severity"),
    [
        ("link_down", "dist1-library", 1.0),
        ("gray_failure", "dist1-library", 0.3),
        ("congestion", "dist3-lab_cs", 0.5),
        ("flapping", "dist1-hostel_a", 1.0),
        ("node_overload", "dist1", 0.5),
        ("misconfig", "admin-internet", 1.0),
    ],
)
def test_every_fault_type_is_detected_within_three_seconds(fault, target, severity):
    net, det = trained()
    net.inject_fault(fault, target, severity=severity)
    assert ticks_until_detected(net, det, target) * TICK_S <= 3.0


def test_alert_clears_after_recovery():
    net, det = trained()
    net.inject_fault("link_down", "dist1-library")
    ticks_until_detected(net, det, "dist1-library")
    net.clear_faults()
    cleared = []
    for _ in range(10):
        cleared += det.update(net.step())[1]
    assert "dist1-library" in cleared
    assert "dist1-library" not in det.active


def test_hard_failure_is_critical_and_degradation_names_metric():
    net, det = trained()
    net.inject_fault("link_down", "dist1-library")
    net.inject_fault("gray_failure", "dist3-lab_cs", severity=0.5)
    for _ in range(6):
        det.update(net.step())
    assert det.active["dist1-library"].severity == "critical"
    assert det.active["dist3-lab_cs"].metric == "loss_pct"
    assert det.active["dist3-lab_cs"].detectors == ["zscore", "iforest"]


def test_no_alerts_during_warmup():
    net, det = Network(seed=3), Detector()
    net.inject_fault("link_down", "dist1-library")
    for _ in range(WARMUP_TICKS - 1):
        assert det.update(net.step()) == ([], [])
