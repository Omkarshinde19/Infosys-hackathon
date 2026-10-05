"""NetHeal engine: runs the detect -> diagnose -> decide -> heal loop.

Serves the REST control API and its own WebSocket, and, when KAFKA_BOOTSTRAP is set,
publishes every event to Redpanda for the sink (TimescaleDB) and stream services.
"""

import asyncio
import traceback
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Annotated

from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from contracts.models import Envelope
from services import auth, bus
from services.detector.detector import Detector
from services.healer.healer import LEVELS, Healer
from services.healer.incidents import IncidentTracker
from services.ledger.ledger import Ledger
from services.llm.reports import entity_namer, incident_facts, make_client, write_report
from services.ml import forecast, gnn, lstm_ae
from services.netsim.engine import TICK_S, Network
from services.rca.engine import RCAEngine


def new_network() -> Network:
    return Network(t0=datetime.now(UTC))


net = new_network()
detector = Detector(forecaster=forecast.load(), autoencoder=lstm_ae.load())
rca = RCAEngine(gnn=gnn.load())
healer = Healer()
incidents = IncidentTracker()
ledger = Ledger()
last_samples: list = []  # latest tick, for fixes approved between ticks
llm = make_client()
reports: dict[str, dict] = {}  # incident id -> generated report
clients: set[WebSocket] = set()
producer: AIOKafkaProducer | None = None


async def broadcast(envelope: Envelope) -> None:
    message = envelope.model_dump_json()
    if producer:
        await producer.send(bus.TOPICS[envelope.type], message.encode())
    for ws in list(clients):
        try:
            await ws.send_text(message)
        except Exception:
            clients.discard(ws)


Operator = Annotated[dict, Depends(auth.require("operator"))]
Admin = Annotated[dict, Depends(auth.require("admin"))]


async def audit(actor: str, event_type: str, payload: dict) -> None:
    """Append to the tamper-evident ledger and publish it (sink stores it in TimescaleDB)."""
    entry = ledger.append(net.now, actor, event_type, payload)
    await broadcast(Envelope(type="audit", data=entry))


def summary(payload) -> dict:
    if isinstance(payload, list) and payload and isinstance(payload[0], BaseModel):  # candidates
        keep = {"id", "type", "opa_decision", "policy_reasons"}
        return {"candidates": [c.model_dump(mode="json", include=keep) for c in payload]}
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return {"value": payload}


async def tick_loop() -> None:
    while True:
        try:
            await tick()
        except Exception:  # one bad tick must never freeze the live network
            traceback.print_exc()
        await asyncio.sleep(TICK_S)


async def tick() -> None:
    global last_samples
    samples = last_samples = net.step()
    raised, cleared = detector.update(samples)
    await broadcast(Envelope(type="telemetry", data=samples))
    if raised or cleared:
        await broadcast(Envelope(type="anomaly", data={"raised": raised, "cleared": cleared}))
    if rca.update(samples, detector.active, net, detector=detector):
        await broadcast(Envelope(type="rca", data=rca.hypotheses))
    await heal(samples)


async def heal(samples) -> None:
    events = []
    if detector.ready:
        baseline = {f: detector.median[f][0] for f in net.flows}
        events = healer.update(samples, rca.hypotheses, net, baseline)
    await handle(events)


async def handle(events: list) -> None:
    """Apply side effects of healing events, record them, update and stream the incident."""
    before = incidents.current
    changed = incidents.update(net.now, detector.active, rca.hypotheses, events)
    switched = incidents.current is not before
    if switched and incidents.current:  # audit in causal order: opened, healing steps, closed
        await audit("system", "incident.opened", {"incident": incidents.current.id})
    for kind, payload in events:
        if kind == "rebaseline":  # traffic moved on purpose: new normal for the new path
            detector.relearn(payload)
        await audit("system", f"healing.{kind}", summary(payload))
    if switched and before:
        await audit("system", "incident.closed", {"incident": before.id, "status": before.status})
    if changed:
        for kind, payload in events:
            await broadcast(Envelope(type="action", data={"kind": kind, "payload": payload}))
        await broadcast(Envelope(type="incident", data=incident_state()))


def incident_state() -> dict:
    incident = incidents.current or (incidents.history[-1] if incidents.history else None)
    return {
        "incident": incident,
        "healer_status": healer.status,
        "awaiting": healer.awaiting,
        "actions": incidents.context[incident.id]["actions"] if incident else [],
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    global producer
    if bus.BOOTSTRAP:
        producer = AIOKafkaProducer(bootstrap_servers=bus.BOOTSTRAP, linger_ms=20)
        await producer.start()
    task = asyncio.create_task(tick_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    if producer:
        await producer.stop()


app = FastAPI(title="NetHeal Gateway", lifespan=lifespan)


class LoginRequest(BaseModel):
    username: str
    password: str


class AutonomyRequest(BaseModel):
    level: int


@app.post("/auth/login")
async def login(req: LoginRequest) -> dict:
    session = auth.login(req.username, req.password)
    if session is None:
        raise HTTPException(401, "Wrong username or password")
    await audit("user", "auth.login", {"by": req.username})
    return session


@app.get("/auth/me")
def me(user: Annotated[dict, Depends(auth.require("viewer"))]) -> dict:
    return user


class FaultRequest(BaseModel):
    type: str
    target: str
    severity: float = 1.0
    ramp_s: float = 0.0


@app.get("/topology")
def topology() -> dict:
    g = net.graph
    return {
        "nodes": [{"id": n, **d} for n, d in g.nodes(data=True)],
        "links": [{"a": a, "b": b, **d} for a, b, d in g.edges(data=True)],
        "flows": [{**f, "route": net.routes[fid]} for fid, f in net.flows.items()],
    }


@app.post("/fault")
async def inject_fault(req: FaultRequest, user: Operator) -> dict:
    try:
        fault = net.inject_fault(req.type, req.target, req.severity, req.ramp_s)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    incidents.note_fault(net.now)
    await audit("user", "fault.injected", {"by": user["username"], **req.model_dump()})
    return vars(fault)


@app.post("/reset")
async def reset(user: Operator) -> dict:
    global net
    net = new_network()
    cleared = list(detector.active)
    detector.clear()
    rca.clear()
    healer.clear()
    incidents.close(net.now)  # history and reports are kept
    await audit("user", "network.reset", {"by": user["username"]})
    if cleared:
        await broadcast(Envelope(type="anomaly", data={"raised": [], "cleared": cleared}))
        await broadcast(Envelope(type="rca", data=[]))
        await broadcast(Envelope(type="incident", data=incident_state()))
    return {"ok": True}


@app.get("/anomalies")
def anomalies() -> dict:
    return {
        "ready": detector.ready,
        "warmup_progress": min(1.0, detector.ticks_seen / detector.warmup_ticks),
        "active": list(detector.active.values()),
    }


@app.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


@app.get("/rca")
def diagnosis() -> list:
    return rca.hypotheses


@app.get("/incident")
def incident() -> dict:
    return incident_state()


@app.get("/incidents")
def list_incidents() -> list:
    out = []
    for inc in reversed([*incidents.history, *([incidents.current] if incidents.current else [])]):
        top = incidents.context[inc.id]["diagnosis"][:1]
        out.append({"incident": inc, "root_cause": top[0] if top else None})
    return out


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    inc = incidents.get(incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    ctx = incidents.context[incident_id]
    return {
        "incident": inc,
        "anomalies": list(ctx["anomalies"].values()),
        "diagnosis": ctx["diagnosis"],
        "actions": ctx["actions"],
        "report": reports.get(incident_id),
    }


@app.post("/incidents/{incident_id}/report")
async def report(incident_id: str, user: Operator, refresh: bool = False) -> dict:
    inc = incidents.get(incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    if refresh or incident_id not in reports:
        facts = incident_facts(inc, incidents.context[incident_id], entity_namer(net))
        reports[incident_id] = await write_report(facts, llm)
    return reports[incident_id]


@app.get("/autonomy")
def get_autonomy() -> dict:
    return {"level": healer.level, "levels": LEVELS}


@app.put("/autonomy")
async def set_autonomy(req: AutonomyRequest, user: Admin) -> dict:
    if req.level not in LEVELS:
        raise HTTPException(400, f"level must be one of {list(LEVELS)}")
    await audit("user", "autonomy.changed", {"by": user["username"], "from": healer.level,
                                             "to": req.level})  # fmt: skip
    healer.level = req.level
    return get_autonomy()


@app.get("/approvals")
def approvals() -> dict:
    return {"awaiting": healer.awaiting, "incident_id": rca.incident_id}


@app.post("/approvals/{action_id}/{decision}")
async def decide(action_id: str, decision: str, user: Operator) -> dict:
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "use approve or reject")
    try:
        if decision == "approve":
            events = healer.approve(action_id, {s.entity_id: s for s in last_samples}, net)
        else:
            events = healer.reject(action_id)
    except KeyError as e:
        raise HTTPException(409, "That fix is no longer waiting for approval") from e
    await audit("user", f"approval.{decision}d", {"by": user["username"], "action": action_id})
    await handle(events)
    return incident_state()


@app.get("/audit")
def audit_log(limit: int = 200) -> list:
    return ledger.entries[-limit:][::-1]


@app.get("/audit/verify")
def audit_verify() -> dict:
    return ledger.verify()
