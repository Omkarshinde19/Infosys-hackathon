import json
import time

from fastapi.testclient import TestClient

from services import bus
from services.gateway.main import app
from tests.accounts import bearer, demo_password

OP = bearer("operator")


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
        r = client.post("/fault", headers=OP, json={"type": "link_down", "target": "dist1-library"})
        assert r.status_code == 200
        ws.receive_json()  # tick may have been computed before the fault landed
        assert flow_loss(ws.receive_json(), "library-internet") == 100
        client.post("/reset", headers=OP)
        ws.receive_json()
        assert flow_loss(ws.receive_json(), "library-internet") < 1


def test_bad_fault_is_rejected():
    with TestClient(app) as client:
        r = client.post("/fault", headers=OP, json={"type": "link_down", "target": "nope"})
    assert r.status_code == 400


def test_anomaly_events_are_streamed_and_listed(monkeypatch):
    from services.detector.detector import Detector
    from services.gateway import main

    monkeypatch.setattr(main, "detector", Detector(warmup_ticks=4))
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", headers=OP, json={"type": "link_down", "target": "dist1-library"})
        for _ in range(12):
            msg = ws.receive_json()
            if msg["type"] == "anomaly":
                break
        raised = {a["entity_id"] for a in msg["data"]["raised"]}
        assert "dist1-library" in raised
        active = {a["entity_id"] for a in client.get("/anomalies").json()["active"]}
        assert "dist1-library" in active
        client.post("/reset", headers=OP)
        assert client.get("/anomalies").json()["active"] == []
        for _ in range(60):  # other event types (rca, incident, action, audit) arrive alongside
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
        client.post("/fault", headers=OP, json={"type": "link_down", "target": "dist3-lab_cs"})
        for _ in range(12):
            msg = ws.receive_json()
            if msg["type"] == "rca":
                break
        assert (msg["data"][0]["cause"], msg["data"][0]["target"]) == (
            "link_failure",
            "dist3-lab_cs",
        )
        assert client.get("/rca").json()[0]["target"] == "dist3-lab_cs"
        client.post("/reset", headers=OP)
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
        client.post("/reset", headers=OP)
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", headers=OP, json={"type": "link_down", "target": "dist1-library"})
        kinds = []
        for _ in range(120):  # ~15 s of ticks, a few messages each
            msg = ws.receive_json()
            if msg["type"] == "action" and msg["data"]["kind"] != "rebaseline":
                kinds.append(msg["data"]["kind"])
            if msg["type"] == "incident" and msg["data"]["healer_status"] == "healed":
                break
        assert kinds[:3] == ["proposed", "applied", "result"]
        state = client.get("/incident").json()
        assert state["incident"]["status"] == "resolved"
        assert state["incident"]["mttr_s"] <= 15
        logged = [a["kind"] for a in state["actions"] if a["kind"] != "rebaseline"]
        assert logged[:3] == kinds[:3]


def test_incident_history_detail_and_offline_report(monkeypatch):
    from services.detector.detector import Detector
    from services.gateway import main
    from services.healer.healer import Healer
    from services.healer.incidents import IncidentTracker
    from services.rca.engine import RCAEngine

    for name, value in [("detector", Detector(warmup_ticks=8)), ("rca", RCAEngine()),
                        ("healer", Healer()), ("incidents", IncidentTracker()),
                        ("llm", None), ("reports", {})]:  # fmt: skip
        monkeypatch.setattr(main, name, value)  # llm=None: no network in tests
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        client.post("/reset", headers=OP)
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", headers=OP, json={"type": "misconfig", "target": "admin-internet"})
        while client.get("/incident").json()["healer_status"] != "healed":
            ws.receive_json()
        listed = client.get("/incidents").json()
        assert listed[0]["root_cause"]["cause"] == "misconfig"
        inc_id = listed[0]["incident"]["id"]
        detail = client.get(f"/incidents/{inc_id}").json()
        assert detail["diagnosis"][0]["target"] == "admin-internet" and detail["report"] is None
        report = client.post(f"/incidents/{inc_id}/report", headers=OP).json()
        assert report["source"] == "template" and "Admin Block" in report["markdown"]
        assert client.get(f"/incidents/{inc_id}").json()["report"] == report
        assert client.get("/incidents/nope").status_code == 404


def test_events_are_published_to_their_bus_topic(monkeypatch):
    from services.gateway import main

    sent = []

    class FakeProducer:
        async def send(self, topic, value):
            sent.append((topic, json.loads(value)))

        async def stop(self):
            pass

    monkeypatch.setattr(main, "producer", FakeProducer())
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        ws.receive_json()
        ws.receive_json()
    telemetry = [v for t, v in sent if t == "telemetry.raw"]
    assert telemetry and telemetry[0]["type"] == "telemetry"
    assert {t for t, _ in sent} <= set(bus.TOPICS.values())


def test_roles_protect_actions():
    fault = {"type": "link_down", "target": "dist1-library"}
    with TestClient(app) as client:
        assert client.post("/fault", json=fault).status_code == 401  # not logged in
        assert client.post("/fault", headers=bearer("viewer"), json=fault).status_code == 403
        assert client.put("/autonomy", headers=OP, json={"level": 2}).status_code == 403
        assert client.get("/topology").status_code == 200  # looking is always allowed
        client.post("/reset", headers=OP)


def test_login_with_demo_account():
    with TestClient(app) as client:
        bad = client.post("/auth/login", json={"username": "operator", "password": "nope"})
        assert bad.status_code == 401
        good = client.post(
            "/auth/login", json={"username": "operator", "password": demo_password("operator")}
        ).json()
        assert good["role"] == "operator"
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {good['token']}"}).json()
        assert me == {"username": "operator", "role": "operator"}


def test_level_2_waits_for_approval_over_the_api_and_everything_is_audited(monkeypatch):
    from services.detector.detector import Detector
    from services.gateway import main
    from services.healer.healer import Healer
    from services.healer.incidents import IncidentTracker
    from services.ledger.ledger import Ledger
    from services.rca.engine import RCAEngine

    for name, value in [("detector", Detector(warmup_ticks=8)), ("rca", RCAEngine()),
                        ("healer", Healer()), ("incidents", IncidentTracker()),
                        ("ledger", Ledger())]:  # fmt: skip
        monkeypatch.setattr(main, name, value)
    with TestClient(app) as client, client.websocket_connect("/ws/live") as ws:
        assert (
            client.put("/autonomy", headers=bearer("admin"), json={"level": 2}).json()["level"] == 2
        )
        while not client.get("/anomalies").json()["ready"]:
            ws.receive_json()
        client.post("/fault", headers=OP, json={"type": "link_down", "target": "dist1-library"})
        while client.get("/incident").json()["healer_status"] != "awaiting_approval":
            ws.receive_json()
        for _ in range(6):  # it keeps waiting
            ws.receive_json()
        pending = client.get("/approvals").json()["awaiting"]
        assert client.get("/incident").json()["healer_status"] == "awaiting_approval"
        approve = f"/approvals/{pending['id']}/approve"
        assert client.post(approve, headers=bearer("viewer")).status_code == 403
        assert client.post(approve, headers=OP).status_code == 200
        while client.get("/incident").json()["healer_status"] != "healed":
            ws.receive_json()

        events = [e["event_type"] for e in client.get("/audit").json()][::-1]
        for expected in ["autonomy.changed", "fault.injected", "incident.opened",
                         "healing.awaiting_approval", "approval.approved", "healing.applied",
                         "healing.result"]:  # fmt: skip
            assert expected in events
        assert client.get("/audit/verify").json()["valid"]
        client.post("/reset", headers=OP)
