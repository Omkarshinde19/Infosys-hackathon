"""Phase 6's scenario on real packets: needs `./netheal start` and `./netheal emu`.

Run: ./netheal e2e

Switches the engine to the Mininet + Open vSwitch network, cuts the Library's link and expects
NetHeal to detect, diagnose, reroute it with OpenFlow rules and verify recovery.
"""

import json
import os
import time
import urllib.request

import pytest

from tests.accounts import demo_password
from tests.e2e.test_stack import ENGINE

pytestmark = pytest.mark.skipif(not os.getenv("NETHEAL_E2E"), reason="needs the docker stack")


def call(path: str, body: dict | None = None, token: str = "", method: str = "POST") -> dict:
    req = urllib.request.Request(
        ENGINE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json", "Authorization": f"Bearer {token}"},
        method=method if body is not None else "GET",
    )
    return json.load(urllib.request.urlopen(req, timeout=10))


def wait(check, seconds: int, what: str):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if result := check():
            return result
        time.sleep(1)
    raise AssertionError(f"timed out waiting for {what}")


def test_link_failure_is_healed_on_the_emulated_network():
    if not call("/backend")["emulab_ready"]:
        pytest.skip("emulated network not running (./netheal emu)")
    token = call("/auth/login", {"username": "admin", "password": demo_password("admin")})["token"]
    try:
        assert call("/backend", {"kind": "emu"}, token)["kind"] == "emu"
        wait(lambda: call("/anomalies")["ready"], 90, "detector warm-up on real telemetry")

        call("/fault", {"type": "link_down", "target": "dist1-library"}, token)
        state = wait(
            lambda: (s := call("/incident"))["healer_status"] == "healed" and s, 60, "healing"
        )
        incident = state["incident"]
        result = next(a["payload"] for a in state["actions"] if a["kind"] == "result")
        before, after = result["before"], result["after"]
        print(f"\nemulated: MTTD {incident['mttd_s']} s, MTTR {incident['mttr_s']} s, latency "
              f"{before['latency_ms']:.1f} -> {after['latency_ms']:.1f} ms, "
              f"loss {before['loss_pct']:.0f}% -> {after['loss_pct']:.1f}%")  # fmt: skip
        assert incident["status"] == "resolved" and incident["mttr_s"] <= 20
        assert result["verified"] and result["after"]["loss_pct"] < 1
    finally:
        call("/backend", {"kind": "sim"}, token)
