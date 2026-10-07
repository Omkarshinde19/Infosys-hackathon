"""Regression scenarios for service-level recovery and transaction outcomes."""

import copy
from statistics import fmean

import pytest

from contracts.models import ActionCandidate, ActionResult, Anomaly, RCAHypothesis, TelemetrySample
from services.healer.healer import APPROVAL_TTL_S, VERIFY_TICKS, Healer
from services.healer.incidents import IncidentTracker
from services.netsim.engine import TICK_S, Network


def ready_network():
    net, healer = Network(seed=3), Healer()
    ticks = [{s.entity_id: s for s in net.step()} for _ in range(12)]
    baseline = {f: fmean(t[f].latency_ms for t in ticks) for f in net.flows}
    healer.baseline = baseline
    return net, healer, baseline, ticks[-1]


def start_library_repair(affected=None, net=None):
    if net is None:
        net, healer, baseline, _ = ready_network()
    else:
        healer = Healer()
        healthy = {s.entity_id: s for s in net.step()}
        baseline = {f: healthy[f].latency_ms for f in net.flows}
        healer.baseline = baseline
    affected = affected or ["library-internet"]
    net.inject_fault("link_down", "dist1-library")
    latest = {s.entity_id: s for s in net.step()}
    routes = {f: [net.flows[f]["src"], "dist2", "core2", "internet"] for f in affected}
    candidate = ActionCandidate(incident_id="episode", type="reroute", params={"routes": routes})
    events = healer.apply(candidate, latest, net, affected)
    assert "applied" in [kind for kind, _ in events]
    return net, healer, baseline


def finish_verification(net, healer, baseline, change):
    events = []
    for _ in range(VERIFY_TICKS):
        latest = {s.entity_id: s for s in net.step()}
        change(latest)
        events += healer.update(list(latest.values()), [], net, baseline)
    return next(payload for kind, payload in events if kind == "result"), events


def test_one_bad_affected_flow_cannot_hide_inside_a_healthy_group_mean():
    affected = ["library-internet", "hostel_a-internet", "hostel_b-internet"]
    net, healer, baseline = start_library_repair(affected)

    def change(latest):
        for fid in affected:
            latest[fid] = latest[fid].model_copy(
                update={"loss_pct": 2.0 if fid == affected[0] else 0.0}
            )

    result, _ = finish_verification(net, healer, baseline, change)
    assert result.after["loss_pct"] < 1  # the old aggregate check would accept this
    assert not result.verified and result.rolled_back
    assert result.per_flow_after[affected[0]]["loss_pct"] == 2
    assert any(affected[0] in reason for reason in result.verification_reasons)


@pytest.mark.parametrize("metric", ["loss", "latency"])
def test_a_fix_is_rolled_back_if_it_breaks_an_unaffected_service(metric):
    net, healer, baseline = start_library_repair()
    original = ["library", "dist1", "core1", "internet"]

    def change(latest):
        field, value = (
            ("loss_pct", 2.0)
            if metric == "loss"
            else ("latency_ms", 1.3 * baseline["admin-internet"])
        )
        latest["admin-internet"] = latest["admin-internet"].model_copy(update={field: value})

    result, _ = finish_verification(net, healer, baseline, change)
    assert result.after["loss_pct"] < 1
    assert not result.verified and result.rolled_back
    assert net.routes["library-internet"] == original
    assert any(
        "Collateral service admin-internet" in reason for reason in result.verification_reasons
    )


def test_missing_service_evidence_never_becomes_verified_recovery():
    net, healer, baseline = start_library_repair()
    result, _ = finish_verification(
        net, healer, baseline, lambda latest: latest.pop("admin-internet")
    )
    assert not result.verified and result.rolled_back
    assert any("Missing service telemetry" in reason for reason in result.verification_reasons)


def test_capacity_breach_after_apply_is_not_hidden_by_healthy_flow_averages():
    net, healer, baseline = start_library_repair()

    def change(latest):
        latest["dist2-library"] = latest["dist2-library"].model_copy(update={"util": 0.86})

    result, _ = finish_verification(net, healer, baseline, change)
    assert result.after["loss_pct"] < 1 and not result.verified and result.rolled_back
    assert any("85% safety limit" in reason for reason in result.verification_reasons)


def waiting_approval():
    net, healer, baseline, _ = ready_network()
    healer.level, healer.generation = 2, "generation-a"
    net.inject_fault("link_down", "dist1-library")
    samples = net.step()
    hypothesis = RCAHypothesis(
        incident_id="episode",
        cause="link_failure",
        target="dist1-library",
        confidence=1,
        evidence=[],
    )
    healer.update(samples, [hypothesis], net, baseline)
    assert healer.awaiting is not None
    return net, healer, baseline, healer.awaiting


def test_approval_expires_without_applying_or_reusing_old_candidates():
    net, healer, _, candidate = waiting_approval()
    routes = copy.deepcopy(net.routes)
    for _ in range(int(APPROVAL_TTL_S / TICK_S) + 1):
        latest = {s.entity_id: s for s in net.step()}
    events = healer.approve(candidate.id, latest, net)
    assert "applied" not in [kind for kind, _ in events]
    assert healer.status == "replanning" and not healer.pending
    assert net.routes == routes and "expired" in events[0][1]


def test_approval_is_bound_to_the_backend_generation():
    net, healer, _, candidate = waiting_approval()
    healer.generation = "generation-b"
    latest = {s.entity_id: s for s in net.step()}
    events = healer.approve(candidate.id, latest, net)
    assert "applied" not in [kind for kind, _ in events]
    assert "generation" in events[0][1]


def test_approval_rechecks_the_current_application_rate_budget():
    net, healer, _, candidate = waiting_approval()
    healer.applied_at = [net.now] * 3
    latest = {s.entity_id: s for s in net.step()}
    events = healer.approve(candidate.id, latest, net)
    assert "applied" not in [kind for kind, _ in events]
    assert "Rate limit" in events[0][1]


def test_a_retry_is_predicted_again_and_rejects_a_now_broken_route():
    net, healer, _, _ = ready_network()
    net.inject_fault("link_down", "dist1-library")
    latest = {s.entity_id: s for s in net.step()}
    healer.pending = [
        ActionCandidate(
            incident_id="episode",
            type="reroute",
            params={
                "routes": {"library-internet": ["library", "dist1", "core2", "internet"]},
            },
        )
    ]
    old = copy.deepcopy(net.routes)
    events = healer._apply_next(latest, net, ["library-internet"])
    assert "applied" not in [kind for kind, _ in events]
    assert healer.status == "escalated" and net.routes == old


def test_a_retry_requires_its_own_human_approval():
    net, healer, _, candidate = waiting_approval()
    latest = {s.entity_id: s for s in net.step()}
    old = copy.deepcopy(net.routes)
    events = healer._apply_next(latest, net, ["library-internet"])
    assert "applied" not in [kind for kind, _ in events]
    assert events[0][0] == "awaiting_approval" and healer.awaiting.id == candidate.id
    assert healer.awaiting in healer.pending and net.routes == old


def test_raising_autonomy_replans_an_alert_only_active_incident():
    net, healer, baseline, _ = ready_network()
    healer.set_level(0)
    net.inject_fault("link_down", "dist1-library")
    hypothesis = RCAHypothesis(
        incident_id="episode",
        cause="link_failure",
        target="dist1-library",
        confidence=1,
        evidence=[],
    )
    healer.update(net.step(), [hypothesis], net, baseline)
    assert healer.status == "alert_only"
    healer.set_level(4)
    events = healer.update(net.step(), [hypothesis], net, baseline)
    assert "applied" in [kind for kind, _ in events]


def test_changing_autonomy_invalidates_an_old_approval():
    net, healer, _, candidate = waiting_approval()
    healer.set_level(1)
    assert healer.awaiting is None and not healer.pending
    with pytest.raises(KeyError):
        healer.approve(candidate.id, {s.entity_id: s for s in net.step()}, net)


def test_changing_autonomy_preserves_verification_but_blocks_automatic_retries():
    net, healer, baseline = start_library_repair()
    healer.set_level(0)
    assert healer.current is not None
    result, _ = finish_verification(net, healer, baseline, lambda latest: None)
    assert result.verified


def test_approval_rechecks_observed_diagnosis_support():
    net, healer, baseline, candidate = waiting_approval()
    unsupported = RCAHypothesis(
        incident_id="episode",
        cause="link_failure",
        target="dist1-library",
        confidence=1,
        evidence=[],
        supported=False,
    )
    samples = net.step()
    healer.update(samples, [unsupported], net, baseline)
    events = healer.approve(candidate.id, {s.entity_id: s for s in samples}, net)
    assert "applied" not in [kind for kind, _ in events]
    assert "observed support" in events[0][1]


def test_no_action_decision_is_reconsidered_after_routing_changes():
    net, healer, baseline, _ = ready_network()
    net.inject_fault("gray_failure", "dist2-library")
    hypothesis = RCAHypothesis(
        incident_id="episode",
        cause="gray_failure",
        target="dist2-library",
        confidence=1,
        evidence=[],
    )
    first = healer.update(net.step(), [hypothesis], net, baseline)
    assert first[0][0] == "no_action"
    net.set_route("library-internet", ["library", "dist2", "core2", "internet"])
    second = healer.update(net.step(), [hypothesis], net, baseline)
    assert "applied" in [kind for kind, _ in second]


def test_no_action_cannot_claim_resolution_while_another_service_is_unhealthy():
    net, healer, baseline, _ = ready_network()
    net.inject_fault("gray_failure", "dist2-library")
    net.inject_fault("misconfig", "admin-internet")
    hypothesis = RCAHypothesis(
        incident_id="episode",
        cause="gray_failure",
        target="dist2-library",
        confidence=1,
        evidence=[],
    )
    events = healer.update(net.step(), [hypothesis], net, baseline)
    assert "no_action" not in [kind for kind, _ in events] and healer.status == "escalated"


def test_new_independent_service_fault_is_seen_and_repaired_during_a_held_fix():
    net, healer, baseline = start_library_repair()
    finish_verification(net, healer, baseline, lambda latest: None)
    original = RCAHypothesis(
        incident_id="episode",
        cause="link_failure",
        target="dist1-library",
        confidence=0.99,
        evidence=[],
    )
    secondary = RCAHypothesis(
        incident_id="episode",
        cause="misconfig",
        target="admin-internet",
        confidence=0.9,
        evidence=[],
    )
    net.inject_fault("misconfig", "admin-internet")
    events = []
    for _ in range(VERIFY_TICKS):
        events += healer.update(net.step(), [original, secondary], net, baseline)
    assert any(kind == "relapsed" for kind, _ in events)
    events = healer.update(net.step(), [original, secondary], net, baseline)
    applied = next(payload for kind, payload in events if kind == "applied")
    assert applied.type == "rollback_config" and applied.params["flow"] == "admin-internet"
    result, _ = finish_verification(net, healer, baseline, lambda latest: None)
    assert result.verified
    # A further regression must still clear the claimed recovery, even though
    # this episode's one automatic recovery retry is exhausted.
    third = secondary.model_copy(update={"target": "lab_cs-internet"})
    net.inject_fault("misconfig", "lab_cs-internet")
    events = []
    for _ in range(VERIFY_TICKS):
        events += healer.update(net.step(), [original, third], net, baseline)
    assert "relapsed" in [kind for kind, _ in events]
    assert "escalated" in [kind for kind, _ in events] and healer.status == "escalated"


def test_a_configuration_repair_restores_removed_faults_if_verification_fails():
    net, healer, baseline, _ = ready_network()
    fault = net.inject_fault("misconfig", "admin-internet")
    latest = {s.entity_id: s for s in net.step()}
    candidate = ActionCandidate(
        incident_id="episode", type="rollback_config", params={"flow": "admin-internet"}
    )
    healer.apply(candidate, latest, net, ["admin-internet"])
    assert fault.id not in net.faults

    def change(latest):
        latest["admin-internet"] = latest["admin-internet"].model_copy(update={"loss_pct": 2.0})

    result, _ = finish_verification(net, healer, baseline, change)
    assert not result.verified and result.rolled_back and result.rollback_attempted
    assert net.faults[fault.id] == fault


def test_configuration_undo_preserves_a_new_independent_fault():
    net, healer, baseline, _ = ready_network()
    removed = net.inject_fault("misconfig", "admin-internet")
    latest = {s.entity_id: s for s in net.step()}
    candidate = ActionCandidate(
        incident_id="episode", type="rollback_config", params={"flow": "admin-internet"}
    )
    healer.apply(candidate, latest, net, ["admin-internet"])
    added = net.inject_fault("misconfig", "library-internet")
    result, _ = finish_verification(net, healer, baseline, lambda latest: None)
    assert result.rolled_back and not result.verified
    assert net.faults[removed.id] == removed and net.faults[added.id] == added


def test_joint_planner_splits_demands_when_lockstep_paths_overload(tmp_path):
    # Two 70-Mbps services fit separately on the two 100-Mbps backups, but
    # every same-rank path combination overloads one. The primary has spare
    # capacity but is physically down; the alternative is faster but smaller.
    path = tmp_path / "joint.yaml"
    path.write_text(
        """nodes:
  - {id: source, layer: access, name: Source}
  - {id: primary, layer: distribution, name: Primary}
  - {id: backup1, layer: distribution, name: Backup1}
  - {id: backup2, layer: distribution, name: Backup2}
  - {id: target, layer: edge, name: Target}
links:
  - {a: source, b: primary, capacity_mbps: 300, base_latency_ms: 1}
  - {a: primary, b: target, capacity_mbps: 300, base_latency_ms: 1}
  - {a: source, b: backup1, capacity_mbps: 100, base_latency_ms: 2}
  - {a: backup1, b: target, capacity_mbps: 100, base_latency_ms: 2}
  - {a: source, b: backup2, capacity_mbps: 100, base_latency_ms: 2.1}
  - {a: backup2, b: target, capacity_mbps: 100, base_latency_ms: 2.1}
flows:
  - {id: flow1, src: source, dst: target, demand_mbps: 70}
  - {id: flow2, src: source, dst: target, demand_mbps: 70}
  - {id: background, src: primary, dst: target, demand_mbps: 110}
""",
        encoding="utf-8",
    )
    net, healer = Network(path=path), Healer()
    ticks = [{s.entity_id: s for s in net.step()} for _ in range(12)]
    healthy = ticks[-1]
    # Background traffic raises the measured healthy primary-path latency,
    # while remaining below85% load. Splitting the affected services then
    # meets their genuine observed baseline and improves background latency.
    healer.baseline = {fid: fmean(t[fid].latency_ms for t in ticks) for fid in net.flows}
    net.inject_fault("link_down", "source-primary")
    hypothesis = RCAHypothesis(
        incident_id="joint",
        cause="link_failure",
        target="source-primary",
        confidence=1,
        evidence=[],
    )
    candidates, affected = healer.plan(hypothesis, net, healthy)
    lockstep = [c for c in candidates if c.params.get("planner") != "capacity"]
    assert all(c.opa_decision == "deny" for c in lockstep)
    best = candidates[0]
    assert best.params["planner"] == "capacity" and best.opa_decision == "allow"
    assert best.params["routes"]["flow1"][1] != best.params["routes"]["flow2"][1]
    assert best.twin_prediction.max_util == pytest.approx(0.7)
    assert set(affected) == {"flow1", "flow2"} and len(candidates) <= 6


@pytest.mark.parametrize("bad", [float("nan"), "invalid", True])
def test_corrupted_runtime_telemetry_fails_verification_without_crashing(bad):
    net, healer, baseline = start_library_repair()

    def change(latest):
        latest["admin-internet"] = latest["admin-internet"].model_copy(update={"loss_pct": bad})

    result, _ = finish_verification(net, healer, baseline, change)
    assert not result.verified and result.rolled_back
    assert any("Invalid service telemetry" in reason for reason in result.verification_reasons)


class FailingRouteNetwork(Network):
    """A second-operation failure after the first route was really changed."""

    def __init__(self, rollback_fails=False):
        super().__init__(seed=3)
        self.calls, self.rollback_fails = 0, rollback_fails

    def set_route(self, flow_id, path):
        self.calls += 1
        if self.calls == 2 or self.rollback_fails and self.calls > 2:
            raise OSError("injected route command failure")
        return super().set_route(flow_id, path)


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_partial_application_is_restored_or_explicitly_escalated(rollback_fails):
    net = FailingRouteNetwork(rollback_fails)
    healer = Healer()
    latest = {s.entity_id: s for s in net.step()}
    before = copy.deepcopy(net.routes)
    routes = {
        fid: [net.flows[fid]["src"], "dist2", "core2", "internet"]
        for fid in ("library-internet", "hostel_a-internet")
    }
    candidate = ActionCandidate(incident_id="episode", type="reroute", params={"routes": routes})
    events = healer.apply(candidate, latest, net, list(routes))
    result = next(payload for kind, payload in events if kind == "result")
    assert "applied" not in [kind for kind, _ in events]
    assert healer.current is None and healer.status == "escalated"
    assert result.rollback_attempted and result.rolled_back is not rollback_fails
    assert result.outcome == ("rollback_failed" if rollback_fails else "execution_failed")
    assert bool(result.rollback_error) is rollback_fails
    if not rollback_fails:
        assert net.routes == before


def test_all_paths_are_validated_before_the_first_mutation():
    net, healer, _, latest = ready_network()
    old = copy.deepcopy(net.routes)
    candidate = ActionCandidate(
        incident_id="episode",
        type="reroute",
        params={
            "routes": {
                "library-internet": ["library", "dist2", "core2", "internet"],
                "hostel_a-internet": [],
            }
        },
    )
    events = healer.apply(candidate, latest, net, ["library-internet", "hostel_a-internet"])
    result = next(payload for kind, payload in events if kind == "result")
    assert net.routes == old and not healer.applied_at
    assert not result.rolled_back and not result.rollback_attempted and result.after == {}


def test_unsupported_capability_is_denied_without_mutation():
    net, healer, _, latest = ready_network()
    candidate = ActionCandidate(incident_id="episode", type="ecmp_split", params={})
    healer._predict(candidate, net, ["library-internet"])
    assert candidate.opa_decision == "deny"
    assert "Unsupported action" in candidate.policy_reasons[0]


def test_unsupported_diagnosis_is_not_automatically_acted_on():
    net, healer, baseline, _ = ready_network()
    hypothesis = RCAHypothesis(
        incident_id="episode",
        cause="congestion",
        target="dist1-library",
        confidence=1,
        evidence=[],
        supported=False,
    )
    assert healer.update(net.step(), [hypothesis], net, baseline) == []
    assert healer.current is None


def test_relapse_clears_current_recovery_metrics_and_keeps_attempt_history():
    tracker = IncidentTracker()
    net = Network()
    ts = net.now
    alert = Anomaly(
        ts=ts,
        entity_id="dist1-library",
        metric="reachability",
        value=0,
        baseline=1,
        score=1,
        detectors=["reachability"],
        severity="critical",
    )
    initial = RCAHypothesis(
        incident_id="episode",
        cause="link_failure",
        target=alert.entity_id,
        confidence=1,
        evidence=[],
    )
    result = ActionResult(
        action_id="action-a",
        applied_at=ts,
        verified=True,
        rolled_back=False,
        before={},
        after={},
        outcome="verified",
    )
    tracker.update(ts, {alert.entity_id: alert}, [initial], [("result", result)])
    incident = tracker.current
    assert incident.mttr_s == 0 and incident.first_healed_at == ts
    corrected = initial.model_copy(update={"cause": "gray_failure", "target": "dist2-library"})
    tracker.update(ts, {alert.entity_id: alert}, [corrected], [("relapsed", "backup failed")])
    assert incident.status == "healing" and incident.mttr_s is None and incident.healed_at is None
    assert incident.first_healed_at == ts and len(incident.recovery_attempts) == 1
    assert tracker.context[incident.id]["diagnosis"][0].target == "dist2-library"
    tracker.update(ts, {alert.entity_id: alert}, [corrected], [("escalated", "no path")])
    assert incident.status == "failed" and incident.mttr_s is None


@pytest.mark.parametrize("explicit", [True, False])
def test_closing_an_unverified_incident_records_failure_without_mttr(explicit):
    tracker, net = IncidentTracker(), Network()
    ts = net.now
    alert = Anomaly(
        ts=ts,
        entity_id="dist1-library",
        metric="reachability",
        value=0,
        baseline=1,
        score=1,
        detectors=["reachability"],
        severity="critical",
    )
    tracker.update(ts, {alert.entity_id: alert}, [], [])
    reason = "Network reset interrupted verification" if explicit else None
    assert tracker.close(ts, reason=reason)
    incident = tracker.history[-1]
    assert incident.status == "failed" and incident.mttr_s is None and incident.healed_at is None
    assert (
        incident.decision_reason == reason
        if explicit
        else "without verified" in incident.decision_reason
    )


def test_saved_proposal_is_an_immutable_snapshot_of_its_original_prediction():
    tracker, net = IncidentTracker(), Network()
    ts = net.now
    alert = Anomaly(
        ts=ts,
        entity_id="dist1-library",
        metric="reachability",
        value=0,
        baseline=1,
        score=1,
        detectors=["reachability"],
        severity="critical",
    )
    candidate = ActionCandidate(
        incident_id="episode", type="reroute", params={"routes": {"f": ["a", "b"]}}
    )
    tracker.update(ts, {alert.entity_id: alert}, [], [("proposed", [candidate])])
    candidate.params["routes"]["f"] = ["a", "c", "b"]
    candidate.opa_decision = "deny"
    saved = tracker.context[tracker.current.id]["actions"][0]["payload"][0]
    assert saved.params["routes"]["f"] == ["a", "b"] and saved.opa_decision is None


def test_telemetry_rejects_nonfinite_metrics_and_naive_time():
    net = Network()
    with pytest.raises(ValueError):
        TelemetrySample(ts=net.now, entity_type="flow", entity_id="f", loss_pct=float("nan"))
    with pytest.raises(ValueError):
        TelemetrySample(ts=net.now.replace(tzinfo=None), entity_type="flow", entity_id="f")
