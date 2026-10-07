import pytest

from services.healer.healer import Healer
from services.healer.whatif import what_if
from services.netsim.engine import Network


def test_link_failure_shows_impact_and_a_safe_fix_without_touching_the_live_network():
    net = Network(seed=1)
    routes = dict(net.routes)
    result = what_if(net, Healer(), "link_down", "dist1-library")
    assert [i["flow"] for i in result["impact"]] == ["library-internet"]
    assert result["impact"][0]["loss_during_pct"] == 100
    assert result["best"].opa_decision == "allow"
    assert "automatically" in result["verdict"]
    assert net.routes == routes and not net.faults  # the real network is untouched


def test_core_router_overload_needs_a_human():
    result = what_if(Network(seed=1), Healer(), "node_overload", "core1", severity=0.8)
    assert result["impact"] and result["best"] is None
    assert "escalate" in result["verdict"]
    assert any("core router" in r for c in result["candidates"] for r in c.policy_reasons)


def test_idle_link_failure_affects_nobody():
    result = what_if(Network(seed=1), Healer(), "link_down", "dist4-cafeteria")
    assert result["impact"] == [] and "maintenance" in result["verdict"]


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError):
        what_if(Network(seed=1), Healer(), "link_down", "nope")


@pytest.mark.parametrize(
    ("level", "phrase", "approval"),
    [
        (0, "alert a human", False),
        (1, "recommend", False),
        (2, "request human approval", True),
        (3, "automatically", False),
        (4, "automatically", False),
    ],
)
def test_verdict_obeys_the_current_comfort_level(level, phrase, approval):
    healer = Healer()
    healer.level = level
    result = what_if(Network(seed=1), healer, "link_down", "dist1-library")
    assert phrase in result["verdict"] and result["autonomy"] == level
    assert result["approval_required"] is approval
    if level == 0:
        assert not result["candidates"] and result["best"] is None


def test_whatif_preserves_the_current_application_rate_budget():
    net, healer = Network(seed=1), Healer()
    healer.applied_at = [net.now] * 3
    result = what_if(net, healer, "link_down", "dist1-library")
    assert result["best"] is None
    assert any(
        "Rate limit" in reason
        for candidate in result["candidates"]
        for reason in candidate.policy_reasons
    )
    assert healer.applied_at == [net.now] * 3 and net.tick == 0


def test_compound_whatif_does_not_silently_clear_an_existing_backup_failure():
    net = Network(seed=1)
    original_fault = net.inject_fault("link_down", "dist2-library")
    result = what_if(net, Healer(), "link_down", "dist1-library", preserve_faults=True)
    assert result["mode"] == "compound" and result["best"] is None
    assert net.tick == 0 and list(net.faults) == [original_fault.id]
    isolated = what_if(net, Healer(), "link_down", "dist1-library")
    assert isolated["mode"] == "isolated" and isolated["best"] is not None
