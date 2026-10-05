"""End-to-end test against the Docker stack started by `make demo` (run: `make e2e`).

engine (REST) -> Redpanda -> stream (WebSocket) and sink (TimescaleDB).
"""

import asyncio
import json
import os
import time
import urllib.request

import asyncpg
import pytest
import websockets

pytestmark = pytest.mark.skipif(not os.getenv("NETHEAL_E2E"), reason="needs `make demo` running")

ENGINE = "http://localhost:8001"
STREAM = "ws://localhost:8002/ws/live"
DATABASE = "postgresql://netheal:netheal@localhost:5433/netheal"


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        ENGINE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=10))


async def heal_through_the_stack() -> dict:
    call("/reset", {})
    deadline = time.monotonic() + 60
    while not call("/anomalies")["ready"]:  # detector warm-up after a cold start
        assert time.monotonic() < deadline, "detector never became ready"
        await asyncio.sleep(1)

    async with websockets.connect(STREAM) as ws:
        call("/fault", {"type": "link_down", "target": "dist3-lab_ece"})
        while time.monotonic() < deadline + 30:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if msg["type"] == "incident" and msg["data"]["healer_status"] == "healed":
                return msg["data"]["incident"]
    raise AssertionError("no healed incident arrived over the stream")


async def stored(incident_id: str) -> tuple:
    conn = await asyncpg.connect(DATABASE)
    try:
        for _ in range(20):  # the sink is asynchronous: give it a moment
            row = await conn.fetchrow(
                "SELECT status, mttr_s FROM incidents WHERE id = $1", incident_id
            )
            if row:
                break
            await asyncio.sleep(0.5)
        telemetry = await conn.fetchval(
            "SELECT count(*) FROM telemetry WHERE ts > now() - interval '1 minute'"
        )
        events = await conn.fetchval("SELECT count(DISTINCT topic) FROM events")
        return row, telemetry, events
    finally:
        await conn.close()


def test_fault_is_healed_through_redpanda_and_stored_in_timescale():
    incident = asyncio.run(heal_through_the_stack())
    assert incident["status"] == "resolved" and incident["mttr_s"] <= 15

    row, recent_telemetry, event_topics = asyncio.run(stored(incident["id"]))
    assert row is not None and row["status"] == "resolved"
    assert recent_telemetry > 100  # ~51 entities x 2 ticks/s
    assert event_topics == 2  # rca.hypotheses and actions
    call("/reset", {})
