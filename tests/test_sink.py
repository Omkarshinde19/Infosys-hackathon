import json

from contracts.models import Envelope
from services.netsim.engine import Network
from services.sink.main import TELEMETRY_COLUMNS, to_rows
from tests.test_healer import Pipeline


def as_bus_message(envelope: Envelope) -> dict:
    return json.loads(envelope.model_dump_json())  # exactly what the sink reads from Redpanda


def test_telemetry_becomes_one_row_per_sample():
    samples = Network(seed=1).step()
    rows = to_rows(as_bus_message(Envelope(type="telemetry", data=samples)))["telemetry"]
    assert len(rows) == len(samples)
    assert all(len(r) == len(TELEMETRY_COLUMNS) for r in rows)
    assert rows[0][0].tzinfo is not None  # timestamps parsed, timezone-aware


def test_anomalies_incidents_and_events_are_mapped():
    p = Pipeline()
    p.inject("link_down", "dist1-library")
    p.run_until("healed", max_ticks=30)
    anomaly = Envelope(type="anomaly", data={"raised": list(p.det.active.values()), "cleared": []})
    assert {r[2] for r in to_rows(as_bus_message(anomaly))["anomalies"]} >= {"dist1-library"}

    state = {"incident": p.incidents.current, "healer_status": "healed", "actions": []}
    (row,) = to_rows(as_bus_message(Envelope(type="incident", data=state)))["incidents"]
    assert row[1] == "resolved" and row[5] == 4.5
    assert json.loads(row[6])["timeline"][0]["stage"] == "detect"

    rca = Envelope(type="rca", data=p.rca.hypotheses)
    assert to_rows(as_bus_message(rca))["events"][0][0] == "rca.hypotheses"


def test_empty_incident_state_writes_nothing():
    msg = as_bus_message(Envelope(type="incident", data={"incident": None, "actions": []}))
    assert to_rows(msg) == {}
