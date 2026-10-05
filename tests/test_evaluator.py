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
    assert "| Recovered (SLA met, last 10 s) | 0% | – | 100% | – |" in md


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
