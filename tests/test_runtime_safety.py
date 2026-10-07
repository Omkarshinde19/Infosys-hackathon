import asyncio
import copy
import json
from datetime import UTC, datetime

import pytest

from contracts.models import Envelope
from services.gateway import main
from services.healer.healer import Healer
from services.healer.incidents import IncidentTracker
from services.ledger.ledger import Ledger
from services.netsim.emu import EmuNetwork
from services.netsim.engine import Network
from services.storage import capture_history, restore_history
from tests.test_healer import Pipeline


def test_copilot_marks_answer_from_retired_network_generation_as_snapshot(monkeypatch):
    monkeypatch.setattr(main, "generation", "before-reset")
    monkeypatch.setattr(main, "healer", Healer())
    monkeypatch.setattr(main, "ledger", Ledger())
    monkeypatch.setattr(main, "clients", set())
    monkeypatch.setattr(main, "journal", None)
    monkeypatch.setattr(main, "last_samples", [])
    monkeypatch.setattr(main, "last_observed_at", datetime.now(UTC))

    async def delayed_answer(question, history, ctx, llm):
        assert ctx.snapshot_generation == "before-reset"
        main.advance_generation()
        return {"answer": "Captured evidence", "source": "template", "evidence": {}}

    monkeypatch.setattr(main, "ask", delayed_answer)
    reply = asyncio.run(
        main.copilot(main.CopilotRequest(question="status"), {"username": "viewer"})
    )
    assert reply["stale"] and reply["generation"] == "before-reset"
    assert reply["captured_at"] and reply["observed_at"]
    assert "captured snapshot" in reply["answer"]


def test_snapshot_reset_invalidates_old_generation_and_clears_samples(monkeypatch):
    monkeypatch.setattr(main, "last_samples", Network().step())
    monkeypatch.setattr(main, "last_observed_at", datetime.now(UTC))
    previous = main.generation
    main.advance_generation()
    assert main.generation != previous and main.healer.generation == main.generation
    snapshot = main.snapshot_state()
    assert snapshot["telemetry"] == [] and snapshot["observed_at"] is None


def test_broker_failure_does_not_block_control_or_remove_unacknowledged_event(monkeypatch):
    class Offline:
        async def send_and_wait(self, *args):
            raise ConnectionError("offline")

    monkeypatch.setattr(main, "producer", Offline())
    monkeypatch.setattr(main, "clients", set())
    monkeypatch.setattr(main, "journal", None)
    main.archive_queue.clear()

    async def run():
        await asyncio.wait_for(main.broadcast(Envelope(type="audit", data={})), timeout=0.1)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(main.archive_loop(), timeout=0.15)

    asyncio.run(run())
    assert len(main.archive_queue) == 1
    main.archive_queue.clear()


def test_acknowledging_an_evicted_event_never_removes_a_different_event(monkeypatch):
    class Producer:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.sent = []

        async def send_and_wait(self, topic, value):
            self.sent.append(json.loads(value)["event_id"])
            self.started.set()
            await self.release.wait()

    monkeypatch.setattr(main, "journal", None)
    main.archive_queue.clear()
    main.archive_queue.append({"event_id": "original", "type": "telemetry"})

    async def run():
        producer = Producer()
        monkeypatch.setattr(main, "producer", producer)
        task = asyncio.create_task(main.archive_loop())
        await producer.started.wait()
        for index in range(257):
            main.archive_queue.append({"event_id": str(index), "type": "telemetry"})
        producer.release.set()
        # Observe the first next delivery; it must be the oldest surviving record.
        for _ in range(20):
            await asyncio.sleep(0)
            if len(producer.sent) >= 2:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert producer.sent[:2] == ["original", "1"]

    asyncio.run(run())
    main.archive_queue.clear()


def test_history_restore_keeps_typed_reports_and_invalidates_unfinished_actions():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    saved = capture_history(p.incidents, Ledger(), {}, 3, 17)
    inc = saved["current"]
    inc["status"] = "healing"
    restored, ledger = IncidentTracker(), Ledger()
    reports, level, sequence = restore_history(saved, restored, ledger, p.net.now)
    assert restored.current is None and restored.history[-1].status == "failed"
    assert restored.history[-1].mttr_s is None
    assert restored.context[inc["id"]]["actions"][-1]["payload"] is not None
    assert (reports, level, sequence) == ({}, 3, 17)


def test_corrupt_checkpoint_audit_is_rejected_before_restore():
    ledger = Ledger()
    ledger.append(datetime.now(UTC), "system", "test", {"count": 1})
    body = capture_history(IncidentTracker(), ledger, {}, 3, 1)
    body["ledger"][0]["payload"]["count"] = 2
    restored = IncidentTracker()
    with pytest.raises(ValueError, match="audit chain"):
        restore_history(body, restored, Ledger(), datetime.now(UTC))
    assert not restored.history


def test_emulator_rejection_keeps_local_routes_and_faults_consistent():
    accept = {"ok": True}
    net = EmuNetwork("http://test", request=lambda *args: accept)
    before = copy.deepcopy(net.routes)
    accept["ok"] = False
    with pytest.raises(OSError):
        net.set_route("library-internet", ["library", "dist2", "core1", "internet"])
    with pytest.raises(OSError):
        net.inject_fault("gray_failure", "dist1-library")
    assert net.routes == before and not net.faults


@pytest.mark.parametrize(
    "path",
    [
        [],
        ["library"],
        ["library", "nope", "internet"],
        ["library", "dist1", "library", "dist2", "core1", "internet"],
    ],
)
def test_invalid_routes_fail_without_changing_network(path):
    net = Network()
    before = json.dumps(net.routes)
    with pytest.raises(ValueError):
        net.set_route("library-internet", path)
    assert json.dumps(net.routes) == before
