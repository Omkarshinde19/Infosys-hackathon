"""EmuNetwork: the same interface as the simulator, backed by the real emulated network.

Telemetry, routes and faults go to the emulab agent (Mininet + Open vSwitch, real packets).
The digital twin used for dry runs (snapshot) stays the fast simulator, configured with the
same routes and faults, so healing decisions are still tested before they touch anything.
"""

import copy
import json
import urllib.request
from collections.abc import Callable
from datetime import datetime

from contracts.models import TelemetrySample
from services.netsim.engine import Fault, Network

TIMEOUT_S = 3


def http(base: str) -> Callable:
    def request(method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"content-type": "application/json"})  # fmt: skip
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
            return json.load(res)

    return request


class EmuNetwork(Network):
    def __init__(self, url: str, t0: datetime | None = None, request: Callable | None = None):
        super().__init__(t0=t0)
        self.url = url
        self.request = request or http(url)
        self.request("POST", "/reset", {"routes": self.routes})

    def step(self) -> list[TelemetrySample]:
        rows = self.request("GET", "/telemetry")
        self.tick += 1
        return [TelemetrySample(ts=self.now, **row) for row in rows]

    def inject_fault(
        self, type: str, target: str, severity: float = 1.0, ramp_s: float = 0.0
    ) -> Fault:
        # Validate in an isolated twin, then update local state only after the agent accepts.
        twin = self.snapshot()
        fault = twin.inject_fault(type, target, severity, ramp_s)
        self._accepted(
            "/fault", {"type": type, "target": target, "severity": severity, "ramp_s": ramp_s}
        )
        self.faults[fault.id] = fault
        return fault

    def clear_faults(self) -> None:
        self._accepted("/clear_faults", {})
        super().clear_faults()

    def set_route(self, flow_id: str, path: list[str]) -> None:
        self.snapshot().set_route(flow_id, path)
        self._accepted("/route", {"flow": flow_id, "path": path})
        super().set_route(flow_id, path)

    def rollback_config(self, flow_id: str) -> None:
        self.snapshot().rollback_config(flow_id)
        self._accepted("/rollback_config", {"flow": flow_id})
        super().rollback_config(flow_id)

    def _accepted(self, path: str, body: dict) -> None:
        response = self.request("POST", path, body)
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise OSError(f"Emulator did not acknowledge {path}")

    def snapshot(self) -> Network:
        """The twin: a plain simulator with the same routes, faults and clock."""
        twin = Network(t0=self.t0)
        twin.routes, twin.faults = copy.deepcopy(self.routes), copy.deepcopy(self.faults)
        twin.tick = self.tick
        return twin
