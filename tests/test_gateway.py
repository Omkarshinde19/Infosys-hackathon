import time

from fastapi.testclient import TestClient

from services.gateway.main import app


def flow_loss(message: dict, flow_id: str) -> float:
    return next(s["loss_pct"] for s in message["data"] if s["entity_id"] == flow_id)


def test_topology_lists_nodes_links_and_routes():
    with TestClient(app) as client:
        body = client.get("/topology").json()
    assert len(body["nodes"]) == 15
    assert {"id": "dist1-library"}.items() <= next(
        link for link in body["links"] if link["id"] == "dist1-library"
    ).items()
    assert all(len(f["route"]) >= 2 for f in body["flows"])


def test_websocket_streams_at_least_two_ticks_per_second():
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        ws.receive_json()
        start = time.monotonic()
        for _ in range(4):
            msg = ws.receive_json()
        assert time.monotonic() - start <= 2.2
    assert msg["type"] == "telemetry"
    assert {s["entity_type"] for s in msg["data"]} == {"link", "node", "flow"}


def test_fault_changes_next_ticks_and_reset_clears_it():
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        assert flow_loss(ws.receive_json(), "library-internet") < 1
        r = client.post("/fault", json={"type": "link_down", "target": "dist1-library"})
        assert r.status_code == 200
        ws.receive_json()  # tick may have been computed before the fault landed
        assert flow_loss(ws.receive_json(), "library-internet") == 100
        client.post("/reset")
        ws.receive_json()
        assert flow_loss(ws.receive_json(), "library-internet") < 1


def test_bad_fault_is_rejected():
    with TestClient(app) as client:
        r = client.post("/fault", json={"type": "link_down", "target": "nope"})
    assert r.status_code == 400


def test_anomaly_events_are_streamed_and_listed(monkeypatch):
    from services.detector.detector import Detector
    from services.gateway import main

    monkeypatch.setattr(main, "detector", Detector(warmup_ticks=4))
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", json={"type": "link_down", "target": "dist1-library"})
        for _ in range(12):
            msg = ws.receive_json()
            if msg["type"] == "anomaly":
                break
        raised = {a["entity_id"] for a in msg["data"]["raised"]}
        assert "dist1-library" in raised
        active = {a["entity_id"] for a in client.get("/anomalies").json()["active"]}
        assert "dist1-library" in active
        client.post("/reset")
        assert client.get("/anomalies").json()["active"] == []
        for _ in range(10):  # other event types (rca, incident) arrive alongside
            msg = ws.receive_json()
            if msg["type"] == "anomaly":
                break
        assert "dist1-library" in msg["data"]["cleared"]


def test_rca_diagnosis_is_streamed_and_listed(monkeypatch):
    from services.detector.detector import Detector
    from services.gateway import main
    from services.rca.engine import RCAEngine

    monkeypatch.setattr(main, "detector", Detector(warmup_ticks=4))
    monkeypatch.setattr(main, "rca", RCAEngine())
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", json={"type": "link_down", "target": "dist3-lab_cs"})
        for _ in range(12):
            msg = ws.receive_json()
            if msg["type"] == "rca":
                break
        assert (msg["data"][0]["cause"], msg["data"][0]["target"]) == (
            "link_failure",
            "dist3-lab_cs",
        )
        assert client.get("/rca").json()[0]["target"] == "dist3-lab_cs"
        client.post("/reset")
        assert client.get("/rca").json() == []


def test_fault_is_healed_end_to_end(monkeypatch):
    from services.detector.detector import Detector
    from services.gateway import main
    from services.healer.healer import Healer
    from services.healer.incidents import IncidentTracker
    from services.rca.engine import RCAEngine

    monkeypatch.setattr(main, "detector", Detector(warmup_ticks=8))
    monkeypatch.setattr(main, "rca", RCAEngine())
    monkeypatch.setattr(main, "healer", Healer())
    monkeypatch.setattr(main, "incidents", IncidentTracker())
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        client.post("/reset")
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", json={"type": "link_down", "target": "dist1-library"})
        kinds = []
        for _ in range(120):  # ~15 s of ticks, a few messages each
            msg = ws.receive_json()
            if msg["type"] == "action":
                kinds.append(msg["data"]["kind"])
            if msg["type"] == "incident" and msg["data"]["healer_status"] == "healed":
                break
        assert kinds[:3] == ["proposed", "applied", "result"]
        state = client.get("/incident").json()
        assert state["incident"]["status"] == "resolved"
        assert state["incident"]["mttr_s"] <= 15
        assert [a["kind"] for a in state["actions"]][:3] == kinds[:3]
