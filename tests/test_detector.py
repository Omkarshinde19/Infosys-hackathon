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


def trained_with_forecaster():
    from services.ml.forecast import load

    forecaster = load()
    assert forecaster is not None, "train it with: python -m ml.train_forecast"
    net, det = Network(seed=3), Detector(forecaster=forecaster)
    for _ in range(WARMUP_TICKS):
        det.update(net.step())
    return net, det


def test_forecaster_predicts_its_original_label_while_stricter_service_already_degrades():
    import copy

    from services.ml.forecast import breached

    net, det = trained_with_forecaster()
    baseline = det.median["library-internet"][0]
    independent = copy.deepcopy(det.forecaster)
    flow_baselines = {f: float(det.median[f][0]) for f in net.flows}
    net.inject_fault("gray_failure", "dist1-library", severity=0.6, ramp_s=20)
    warned_at = breached_at = operational_at = None
    for tick in range(60):
        samples = net.step()
        raised, _ = det.update(samples)
        flow = next(s for s in samples if s.entity_id == "library-internet")
        model_warning = independent.update(samples, flow_baselines)
        if "library-internet" in model_warning and warned_at is None:
            warned_at = tick
        if any(a.entity_id == "library-internet" for a in raised) and operational_at is None:
            operational_at = tick
        if breached_at is None and breached(flow.latency_ms, flow.loss_pct, baseline):
            breached_at = tick
    assert warned_at is not None and breached_at is not None
    assert warned_at < breached_at  # early only against the model's 2% / 2x training label
    assert operational_at is not None and operational_at < breached_at


def test_forecaster_raises_no_false_warnings_in_five_healthy_minutes():
    net, det = trained_with_forecaster()
    for _ in range(int(300 / TICK_S)):
        raised, _ = det.update(net.step())
        assert raised == []


def test_lstm_autoencoder_joins_alerts_as_a_temporal_opinion():
    from services.ml.lstm_ae import SEQ, load

    autoencoder = load()
    assert autoencoder is not None, "train it with: python -m ml.train_lstm_ae"
    net, det = Network(seed=3), Detector(autoencoder=autoencoder)
    for _ in range(WARMUP_TICKS + SEQ):  # warm-up, then 10 s of healthy history
        det.update(net.step())
    net.inject_fault("gray_failure", "dist3-lab_cs", severity=0.5)
    for _ in range(6):
        det.update(net.step())
    assert det.active["dist3-lab_cs"].detectors == ["zscore", "iforest", "lstm_ae"]


def test_clear_restores_warmup_baselines_and_forgets_ml_history():
    from services.ml.forecast import load

    net, det = Network(seed=3), Detector(forecaster=load())
    for _ in range(WARMUP_TICKS):
        det.update(net.step())
    original = det.median["dist2-library"].copy()
    det.relearn(["dist2-library"])
    net.set_route("library-internet", ["library", "dist2", "core1", "internet"])
    for _ in range(25):  # long enough to re-learn a busy baseline
        det.update(net.step())
    assert det.median["dist2-library"][0] > original[0]

    det.clear()  # e.g. the network was reset
    assert (det.median["dist2-library"] == original).all()
    assert det.relearning == {} and len(det.forecaster.history) == 0


def bump_latency(samples, link: str, ms: float):
    return [s.model_copy(update={"latency_ms": s.latency_ms + ms}) if s.entity_id == link else s
            for s in samples]  # fmt: skip


def test_brief_latency_only_blip_does_not_alert_but_sustained_does():
    """Latency rising without load or loss (e.g. a CPU hiccup) must persist ~3-4 s to alert."""
    net, det = trained()
    for _ in range(4):  # 2 s blip on a lightly loaded link
        raised, _ = det.update(bump_latency(net.step(), "dist1-library", 6.0))
        assert "dist1-library" not in {a.entity_id for a in raised}
    for _ in range(10):
        det.update(net.step())
    alerted_at = None
    for tick in range(10):  # now it stays high
        raised, _ = det.update(bump_latency(net.step(), "dist1-library", 6.0))
        if any(a.entity_id == "dist1-library" for a in raised):
            alerted_at = tick
            break
    assert alerted_at is not None and alerted_at >= 5  # held back until sustained


def test_relearning_never_masks_new_unreachable_flow_or_link():
    net, det = trained()
    det.relearn(["dist1-library", "library-internet"])
    net.inject_fault("link_down", "dist1-library")
    assert ticks_until_detected(net, det, "dist1-library") <= 3
    assert det.active["library-internet"].metric == "reachability"
    assert det.relearning["dist1-library"] == []


def test_bad_startup_observations_do_not_become_a_healthy_baseline():
    net, det = Network(seed=3), Detector(warmup_ticks=4)
    net.inject_fault("gray_failure", "dist1-library", severity=0.5)
    for _ in range(8):
        det.update(net.step())
    assert not det.ready and "dist1-library" in det.baseline_rejected
    net.clear_faults()
    for _ in range(4):
        det.update(net.step())
    assert det.ready
    assert det.median["dist1-library"][1] < 1


def test_missing_and_nonfinite_samples_cannot_poison_baselines_or_clear_active_alerts():
    net, det = trained()
    original = det.median["dist1-library"].copy()
    det.relearn(["dist1-library"])
    for _ in range(6):
        samples = [
            s.model_copy(update={"loss_pct": float("nan")}) if s.entity_id == "dist1-library" else s
            for s in net.step()
        ]
        det.update(samples)
    assert det.quality_issues["dist1-library"]
    assert det.active["dist1-library"].metric == "telemetry_quality"
    assert (det.median["dist1-library"] == original).all()
    for _ in range(8):
        det.update([])
    assert "dist1-library" in det.active


def test_repeated_timestamps_are_quality_failures_and_require_fresh_recovery():
    net, det = trained()
    samples = net.step()
    det.update(samples)
    for _ in range(4):
        det.update(samples)
    assert det.active["dist1-library"].metric == "telemetry_quality"
    for _ in range(6):
        det.update(net.step())
    assert not det.active and not det.quality_issues


def test_active_alert_refreshes_value_score_and_timestamp_with_stable_id():
    net, det = trained()
    net.inject_fault("gray_failure", "dist1-library", severity=0.2)
    ticks_until_detected(net, det, "dist1-library")
    first = det.active["dist1-library"]
    net.inject_fault("gray_failure", "dist1-library", severity=0.8)
    raised, _ = det.update(net.step())
    fresh = det.active["dist1-library"]
    assert fresh.id == first.id and fresh.ts > first.ts
    assert fresh.value > first.value and any(a.id == first.id for a in raised)


def test_failed_relearning_expires_and_retains_previous_baseline():
    from services.detector.detector import RELEARN_TIMEOUT_TICKS

    net, det = trained()
    old = det.median["dist1-library"].copy()
    det.relearn(["dist1-library"])
    net.inject_fault("gray_failure", "dist1-library", severity=0.5)
    for _ in range(RELEARN_TIMEOUT_TICKS):
        det.update(net.step())
    assert not det.relearning and (det.median["dist1-library"] == old).all()
    assert "expired" in det.baseline_rejected["dist1-library"]


def test_sustained_operational_sla_violation_alerts_even_below_zscore_threshold():
    from services.detector.detector import SERVICE_LATENCY_RATIO, TRUSTED_LOSS_PCT
    from services.healer.healer import HEALTHY_LOSS_PCT, LATENCY_TOLERANCE

    assert SERVICE_LATENCY_RATIO == LATENCY_TOLERANCE and TRUSTED_LOSS_PCT == HEALTHY_LOSS_PCT
    net, det = trained()
    flow = "library-internet"
    for _ in range(6):
        samples = [
            s.model_copy(update={"latency_ms": float(det.median[flow][0]) * 1.12})
            if s.entity_id == flow
            else s
            for s in net.step()
        ]
        det.update(samples)
    alert = det.active[flow]
    assert alert.detectors == ["service_sla"] and alert.metric == "latency_ms"
    assert (alert.value - det.median[flow][0]) / det.scale[flow][0] < 6


def test_operational_loss_threshold_and_intended_relearn_cannot_hide_service_failure():
    net, det = trained()
    det.relearn(["library-internet"])
    for _ in range(3):
        samples = [
            s.model_copy(update={"loss_pct": 1.05}) if s.entity_id == "library-internet" else s
            for s in net.step()
        ]
        det.update(samples)
    assert "service_sla" in det.active["library-internet"].detectors
