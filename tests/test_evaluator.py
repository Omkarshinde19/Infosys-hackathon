import pytest

from services.evaluator import harness


@pytest.fixture
def link_down(monkeypatch):
    monkeypatch.setattr(harness, "random_fault", lambda rng, net: ("link_down", "dist1-library",
                                                                   1.0, 0.0))  # fmt: skip


def test_healing_recovers_a_link_failure_that_no_heal_does_not(link_down):
    twin = harness.run(harness.FIRST_SEED, "twin")
    assert twin["detected"] and twin["top1"]
    assert twin["healed"] and twin["recovered"] and twin["mttr_s"] <= 15
    no_heal = harness.run(harness.FIRST_SEED, "no_heal")
    assert no_heal["sla_impact"] and not no_heal["recovered"] and not no_heal["applied"]
    assert no_heal["sla_violation_s"] > twin["sla_violation_s"]


def test_reactive_policy_applies_untested_detours(link_down):
    r = harness.run(harness.FIRST_SEED, "reactive")
    assert r["applied"] >= 1
    h = harness.ReactiveHealer()
    candidates, _ = h.plan(_diagnosis(), harness.Network())
    assert candidates and all(c.opa_decision == "allow" for c in candidates)


def test_rl_policy_adds_the_agents_proposal(link_down, monkeypatch):
    calls = []

    class Agent:
        def propose(self, net, latest, target):
            calls.append(target)
            return {}

    monkeypatch.setattr(harness.rl, "load", lambda: Agent())
    r = harness.run(harness.FIRST_SEED, "rl")
    assert calls and calls[0] == "dist1-library"
    assert r["healed"]  # with no proposal the rule candidates still heal it


def test_healthy_control_raises_no_alarm(monkeypatch):
    monkeypatch.setattr(harness, "random_fault", lambda rng, net: None)
    r = harness.run(harness.FIRST_SEED, "twin")
    assert r["fault"] is None and not r["detected"] and not r["sla_impact"]


def test_summary_and_report():
    runs = [
        _row("twin", fault=True, detected=True, sla_impact=True, recovered=True, healed=True),
        _row("twin", fault=False, detected=True, seed=1),
        _row("no_heal", fault=True, detected=True, sla_impact=True),
    ]
    s = harness.summarize(runs)["policies"]
    assert s["twin"]["detection"]["precision"] == 0.5
    assert s["twin"]["detection"]["false_positive_rate"] == 1.0
    assert s["twin"]["healing"]["recovered_rate"] == 1.0
    assert s["no_heal"]["healing"]["recovered_rate"] == 0.0
    assert s["twin"]["detection"]["median_mttd_gradual_s"] == 1.5
    md = harness.markdown({"summary": harness.summarize(runs),
                           "meta": {"scenarios": 2, "run_s": 60}})  # fmt: skip
    expected = "| Recovered (SLA met, last 10 s) | 0% | – | – | – | 100% | – | – |"
    assert expected in md
    assert "Median of run-level p95" in md and "not a full OSPF" in md


def test_policies_are_compared_on_the_faults_that_hurt_users_without_healing():
    # A fix that lands before the SLA breaks counts as recovered, not as a fault that vanished.
    runs = [
        _row("no_heal", fault=True, detected=True, sla_impact=True, seed=7),
        _row("twin", fault=True, detected=True, recovered=True, healed=True, seed=7),
        _row("twin", fault=True, detected=True, recovered=True, seed=8),  # harmless fault
    ]
    healing = harness.summarize(runs)["policies"]["twin"]["healing"]
    assert healing["sla_impacting_faults"] == 1
    assert healing["recovered_rate"] == 1.0
    assert healing["median_recovery_s"] == 0.0


def test_guarded_reactive_keeps_the_production_guards(link_down):
    h = harness.GuardedReactiveHealer()
    candidates, _ = h.plan(_diagnosis(), harness.Network())
    assert len(candidates) <= 1
    assert candidates[0].twin_prediction.per_flow
    r = harness.run(harness.FIRST_SEED, "guarded_reactive")
    assert r["policy"] == "guarded_reactive" and r["detected"]
    assert r["actions"] and all(a["per_flow_after"] for a in r["actions"])


def test_native_reference_uses_observed_reachability_with_convergence_delay():
    net = harness.Network()
    original = net.routes["library-internet"][:]
    native = harness.NativeShortestRouting()
    net.inject_fault("link_down", "dist1-library")
    assert native.update(net.step(), net) == []
    assert native.update(net.step(), net) == []
    moved = native.update(net.step(), net)
    assert "library-internet" in moved and net.routes["library-internet"] != original
    net = harness.Network()
    native = harness.NativeShortestRouting()
    net.inject_fault("gray_failure", "dist1-library", severity=0.5)
    assert all(not native.update(net.step(), net) for _ in range(6))


def test_per_flow_evidence_and_frozen_fault_cohort_are_saved(link_down):
    r = harness.run(harness.FIRST_SEED, "twin")
    assert r["original_exposed_flows"] == ["library-internet"]
    assert r["per_flow"]["library-internet"]["exposed_to_fault"]
    assert not r["per_flow"]["admin-internet"]["exposed_to_fault"]
    assert r["per_flow_before_first_action"] and r["actions"]
    assert r["flow_violation_s"] >= r["sla_violation_s"]


def test_unknown_telemetry_and_a_single_bad_service_fail_closed():
    net = harness.Network()
    flow = next(s for s in net.step() if s.entity_type == "flow")
    assert not harness.service_breached(flow, flow.latency_ms)
    assert harness.service_breached(flow.model_copy(update={"loss_pct": 1.0}), flow.latency_ms)
    assert harness.service_breached(None, flow.latency_ms)
    assert harness.service_breached(
        flow.model_copy(update={"loss_pct": float("nan")}), flow.latency_ms
    )


def test_missing_diagnoses_are_counted_as_failures_and_coverage_is_explicit():
    diagnosed = _row("twin", fault=True)
    diagnosed["diagnosed"] = True
    unknown = _row("twin", fault=True, seed=1)
    unknown.update(diagnosed=False, top1=False, top3=False)
    rca = harness.policy_summary([diagnosed, unknown], set())["rca"]
    assert rca["coverage"] == 0.5
    assert rca["top1_over_all_faults"] == 0.5 and rca["top1_given_diagnosis"] == 1.0


def test_confidence_intervals_resample_whole_paired_scenarios():
    interval = harness.paired_interval([-4.0, -2.0, 0.0, 2.0])
    assert interval == harness.paired_interval([-4.0, -2.0, 0.0, 2.0])
    assert interval["mean"] == -1 and interval["paired_scenarios"] == 4
    assert interval["ci95"][0] <= -1 <= interval["ci95"][1]
    assert harness.paired_interval([1])["ci95"] is None
    low, high = harness.rate_ci95([True] * 5)
    assert 0 < low < 1 and high == 1


def test_evaluation_provenance_hashes_sources_and_preserved_models():
    meta = harness.metadata(3)
    assert meta["schema_version"] == "netheal.evaluation.v2"
    assert meta["seed_range"] == [harness.FIRST_SEED, harness.FIRST_SEED + 2]
    assert len(meta["source_sha256"]["services/evaluator/harness.py"]) == 64
    assert len(meta["model_sha256"]["services/ml/models/rca_gnn.pt"]) == 64
    assert meta["service_definition"]["loss_pct_lt"] == 1.0


def test_stress_delay_is_absent_from_twin_and_independent_of_fault_labels():
    net = harness.DelayStressNetwork(seed=8)
    net.tick = harness.WARMUP_TICKS + 5
    twin = net.snapshot()
    assert type(twin) is harness.Network
    actual = {s.entity_id: s for s in net.step()}
    predicted = {s.entity_id: s for s in twin.step()}
    for fid in harness.STRESS_FLOWS:
        assert actual[fid].latency_ms == pytest.approx(predicted[fid].latency_ms * 1.18)
    assert actual["admin-internet"].latency_ms == predicted["admin-internet"].latency_ms
    meta = harness.metadata(2, "unmodeled_delay")
    assert meta["plant_perturbation"]["included_in_twin"] is False


def test_disturbed_controls_are_not_counted_as_healthy_false_positives():
    row = _row("twin", fault=False, detected=True)
    row["suite"] = "unmodeled_delay"
    summary = harness.policy_summary([row], set())
    assert summary["healthy"] == 0 and summary["disturbance_controls"] == 1
    assert summary["detection"]["false_positive_rate"] is None
    assert summary["detection"]["precision"] is None
    assert summary["detection"]["disturbance_control_detection_rate"] == 1.0


def _diagnosis():
    from contracts.models import RCAHypothesis

    return RCAHypothesis(incident_id="i", cause="link_failure", target="dist1-library",
                         confidence=0.9, evidence=[], method_scores={})  # fmt: skip


def _row(policy, fault, detected=False, sla_impact=False, recovered=False, healed=False, seed=0):
    return {
        "seed": seed, "policy": policy,
        "fault": {"type": "link_down", "ramp_s": 10.0} if fault else None,
        "detected": detected, "mttd_s": 1.5 if detected else None,
        "top1": True if fault else None, "top3": True if fault else None,
        "voting_top1": False if fault else None, "healed": healed,
        "mttr_s": 4.5 if healed else None, "applied": int(healed), "rollbacks": 0,
        "escalated": False, "sla_impact": sla_impact, "recovered": recovered,
        "recovery_s": (1.5 if sla_impact else 0.0) if recovered else None, "sla_violation_s": 1.5,
        "p95_latency_ms": 9.0, "mean_loss_pct": 0.1,
    }  # fmt: skip
