from services.netsim.emu import EmuNetwork
from services.netsim.engine import Network


class FakeAgent:
    """Records what the engine asks the emulator to do; answers telemetry from a simulator."""

    def __init__(self):
        self.calls, self.sim = [], Network(seed=1)

    def __call__(self, method: str, path: str, body=None):
        self.calls.append((method, path, body))
        if path == "/telemetry":
            return [s.model_dump(exclude={"ts"}) for s in self.sim.step()]
        return {"ok": True}


def emu() -> tuple[EmuNetwork, FakeAgent]:
    agent = FakeAgent()
    return EmuNetwork("http://emulab", request=agent), agent


def test_start_sends_every_route_to_the_emulator():
    net, agent = emu()
    method, path, body = agent.calls[0]
    assert (method, path) == ("POST", "/reset") and body["routes"] == net.routes


def test_step_returns_real_telemetry_stamped_with_engine_time():
    net, _ = emu()
    samples = net.step()
    assert {s.entity_type for s in samples} == {"link", "node", "flow"}
    assert samples[0].ts == net.now


def test_actions_go_to_the_emulator():
    net, agent = emu()
    net.inject_fault("link_down", "dist1-library")
    net.set_route("library-internet", ["library", "dist2", "core1", "internet"])
    net.rollback_config("admin-internet")
    net.clear_faults()
    paths = [p for _, p, _ in agent.calls[1:]]
    assert paths == ["/fault", "/route", "/rollback_config", "/clear_faults"]


def test_twin_is_the_simulator_with_the_same_routes_and_faults():
    net, agent = emu()
    net.inject_fault("link_down", "dist1-library")
    net.set_route("hostel_a-internet", ["hostel_a", "dist2", "core1", "internet"])
    calls = len(agent.calls)
    twin = net.snapshot()
    assert type(twin) is Network
    assert twin.routes == net.routes and [f.target for f in twin.faults.values()] == [
        "dist1-library"
    ]
    twin.set_route("library-internet", ["library", "dist2", "core1", "internet"])
    twin.step()
    assert len(agent.calls) == calls  # dry runs never touch the real network
