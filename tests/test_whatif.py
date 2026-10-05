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
