"""API gateway: runs the simulator tick loop and streams telemetry over WebSocket."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from contracts.models import Envelope
from services.netsim.engine import TICK_S, Network


def new_network() -> Network:
    return Network(t0=datetime.now(UTC))


net = new_network()
clients: set[WebSocket] = set()


async def tick_loop() -> None:
    while True:
        message = Envelope(type="telemetry", data=net.step()).model_dump_json()
        for ws in list(clients):
            try:
                await ws.send_text(message)
            except Exception:
                clients.discard(ws)
        await asyncio.sleep(TICK_S)


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
    return vars(fault)


@app.post("/reset")
def reset() -> dict:
    global net
    net = new_network()
    return {"ok": True}


@app.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
