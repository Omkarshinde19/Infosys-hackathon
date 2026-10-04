import statistics

import pytest

from services.netsim.engine import Network


def run(net: Network, ticks: int) -> list[dict]:
    """Return per-tick {entity_id: sample} maps."""
    return [{s.entity_id: s for s in net.step()} for _ in range(ticks)]


def mean(ticks: list[dict], entity: str, metric: str) -> float:
    return statistics.fmean(getattr(t[entity], metric) for t in ticks)


def test_healthy_baseline_is_stable():
    net = Network(seed=1)
    ticks = run(net, 200)
    for fid in net.flows:
        lat = [t[fid].latency_ms for t in ticks]
        assert max(t[fid].loss_pct for t in ticks) < 1.0
        assert statistics.stdev(lat) / statistics.fmean(lat) < 0.1


def test_link_down_breaks_only_flows_through_it():
    net = Network(seed=1)
    net.inject_fault("link_down", "dist1-library")
    tick = run(net, 1)[0]
    assert tick["library-internet"].loss_pct == 100
    assert tick["library-internet"].throughput_mbps == 0
    assert tick["dist1-library"].throughput_mbps == 0
    assert tick["hostel_a-internet"].loss_pct < 1


def test_reroute_restores_flow_after_link_down():
    net = Network(seed=1)
    net.inject_fault("link_down", "dist1-library")
    net.set_route("library-internet", ["library", "dist2", "core1", "internet"])
    tick = run(net, 1)[0]
    assert tick["library-internet"].loss_pct < 1


def test_congestion_raises_latency_non_linearly():
    lat = []
    for sev in (0.2, 0.4, 0.6):
        net = Network(seed=1)
        net.inject_fault("congestion", "dist1-library", severity=sev)
        lat.append(mean(run(net, 40), "dist1-library", "latency_ms"))
    assert lat[2] - lat[1] > 2 * (lat[1] - lat[0])


def test_gray_failure_loses_packets_while_link_is_up():
    net = Network(seed=1)
    net.inject_fault("gray_failure", "dist1-library", severity=0.5)
    tick = run(net, 1)[0]
    assert tick["dist1-library"].latency_ms is not None
    assert 8 < tick["library-internet"].loss_pct < 15


def test_node_overload_slows_flows_through_node():
    net = Network(seed=1)
    healthy = mean(run(net, 20), "library-internet", "latency_ms")
    net.inject_fault("node_overload", "dist1")
    ticks = run(net, 20)
    assert mean(ticks, "dist1", "cpu") > 0.9
    assert mean(ticks, "library-internet", "latency_ms") > 3 * healthy


def test_flapping_link_alternates():
    net = Network(seed=1)
    net.inject_fault("flapping", "dist1-library")
    states = [t["dist1-library"].latency_ms is None for t in run(net, 16)]
    assert any(states) and not all(states)


def test_misconfig_blackholes_one_flow():
    net = Network(seed=1)
    net.inject_fault("misconfig", "admin-internet")
    tick = run(net, 1)[0]
    assert tick["admin-internet"].loss_pct == 100
    assert tick["library-internet"].loss_pct < 1


def test_ramp_makes_fault_gradual():
    net = Network(seed=1)
    net.inject_fault("gray_failure", "dist1-library", severity=1.0, ramp_s=10)
    loss = [t["library-internet"].loss_pct for t in run(net, 20)]
    assert loss[2] < loss[10] < loss[19]


def test_same_seed_same_output():
    a, b, c = Network(seed=7), Network(seed=7), Network(seed=8)
    for net in (a, b, c):
        net.inject_fault("congestion", "dist3-lab_cs", ramp_s=5)
    out_a = [s.model_dump() for _ in range(50) for s in a.step()]
    out_b = [s.model_dump() for _ in range(50) for s in b.step()]
    out_c = [s.model_dump() for _ in range(50) for s in c.step()]
    assert out_a == out_b
    assert out_a != out_c


def test_snapshot_is_independent():
    net = Network(seed=1)
    twin = net.snapshot()
    twin.inject_fault("link_down", "dist1-library")
    assert run(twin, 1)[0]["library-internet"].loss_pct == 100
    assert run(net, 1)[0]["library-internet"].loss_pct < 1


@pytest.mark.parametrize(
    ("type", "target"),
    [("teleport", "dist1-library"), ("link_down", "nope"), ("node_overload", "dist1-library")],
)
def test_rejects_bad_faults(type, target):
    with pytest.raises(ValueError):
        Network().inject_fault(type, target)


def test_rejects_invalid_route():
    with pytest.raises(ValueError):
        Network().set_route("library-internet", ["library", "core1", "internet"])
