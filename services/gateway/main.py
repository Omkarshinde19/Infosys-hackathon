"""API gateway: runs the detect -> diagnose -> decide -> heal loop and streams it over WebSocket."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from contracts.models import Envelope
from services.detector.detector import Detector
from services.healer.healer import Healer
from services.healer.incidents import IncidentTracker
from services.netsim.engine import TICK_S, Network
from services.rca.engine import RCAEngine


def new_network() -> Network:
    return Network(t0=datetime.now(UTC))


net = new_network()
detector = Detector()
rca = RCAEngine()
healer = Healer()
incidents = IncidentTracker()
clients: set[WebSocket] = set()


async def broadcast(envelope: Envelope) -> None:
    message = envelope.model_dump_json()
    for ws in list(clients):
        try:
            await ws.send_text(message)
        except Exception:
            clients.discard(ws)


async def tick_loop() -> None:
    while True:
        samples = net.step()
        raised, cleared = detector.update(samples)
        await broadcast(Envelope(type="telemetry", data=samples))
        if raised or cleared:
            await broadcast(Envelope(type="anomaly", data={"raised": raised, "cleared": cleared}))
        if rca.update(samples, detector.active, net):
            await broadcast(Envelope(type="rca", data=rca.hypotheses))
        await heal(samples)
        await asyncio.sleep(TICK_S)


async def heal(samples) -> None:
    events = []
    if detector.ready:
        baseline = {f: detector.median[f][0] for f in net.flows}
        events = healer.update(samples, rca.hypotheses, net, baseline)
    if incidents.update(net.now, detector.active, rca.hypotheses, events):
        for kind, payload in events:
            await broadcast(Envelope(type="action", data={"kind": kind, "payload": payload}))
        await broadcast(Envelope(type="incident", data=incident_state()))


def incident_state() -> dict:
    incident = incidents.current or (incidents.history[-1] if incidents.history else None)
    return {
        "incident": incident,
        "healer_status": healer.status,
        "actions": incidents.context[incident.id]["actions"] if incident else [],
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(tick_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="NetHeal Gateway", lifespan=lifespan)


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
def inject_fault(req: FaultRequest) -> dict:
    try:
        fault = net.inject_fault(req.type, req.target, req.severity, req.ramp_s)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    incidents.note_fault(net.now)
    return vars(fault)


@app.post("/reset")
async def reset() -> dict:
    global net
    net = new_network()
    cleared = list(detector.active)
    detector.clear()
    rca.clear()
    healer.clear()
    incidents.close(net.now)
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
