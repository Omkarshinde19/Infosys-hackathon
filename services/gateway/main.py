"""NetHeal engine: runs the detect -> diagnose -> decide -> heal loop.

Serves the REST control API and its own WebSocket, and, when KAFKA_BOOTSTRAP is set,
publishes every event to Redpanda for the sink (TimescaleDB) and stream services.
"""

import asyncio
import copy
import hashlib
import json
import os
import time
import traceback
import urllib.request
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Literal
from uuid import uuid4
from weakref import WeakKeyDictionary

from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field

from contracts.models import Envelope
from services import auth, bus
from services import observability as obs
from services.copilot.agent import Context, ask
from services.copilot.rag import EMBED_MODEL, DocIndex
from services.detector.detector import Z_THRESHOLD, Detector
from services.healer.healer import LEVELS, Healer
from services.healer.incidents import IncidentTracker
from services.healer.whatif import what_if
from services.ledger.ledger import Ledger
from services.llm.reports import MODEL, entity_namer, incident_facts, make_client, write_report
from services.ml import forecast, gnn, lstm_ae, rl
from services.netsim.emu import EmuNetwork
from services.netsim.engine import TICK_S, Network
from services.rca.engine import RCAEngine
from services.storage import Journal, capture_history, restore_history

EMULAB_URL = os.getenv("EMULAB_URL", "http://localhost:9000")
backend = "sim"  # "sim" (Python simulator) or "emu" (Mininet + Open vSwitch, real packets)


def new_network() -> Network:
    if backend == "emu":
        return EmuNetwork(EMULAB_URL, t0=datetime.now(UTC))
    return Network(t0=datetime.now(UTC))


def new_detector() -> Detector:
    return Detector(forecaster=forecast.load(), autoencoder=lstm_ae.load())


def emulab_ready() -> bool:
    try:
        with urllib.request.urlopen(EMULAB_URL + "/health", timeout=2) as res:
            return json.load(res)["ready"]
    except OSError:
        return False


net = new_network()
detector = new_detector()
rca = RCAEngine(gnn=gnn.load())
healer = Healer(rl=rl.load())  # the RL agent's proposal joins the twin-tested candidates
incidents = IncidentTracker()
ledger = Ledger()
last_samples: list = []  # latest tick, for fixes approved between ticks
llm = make_client()
docs = DocIndex(llm.cloud if llm else None)  # offline: keyword search
reports: dict[str, dict] = {}  # incident id -> generated report
clients: set[WebSocket] = set()
obs.WS_CLIENTS.labels("engine").set_function(lambda: len(clients))
producer: AIOKafkaProducer | None = None
generation = str(uuid4())
sequence = 0
last_observed_at: datetime | None = None
last_tick_error: str | None = None
_locks: WeakKeyDictionary = WeakKeyDictionary()
healer.generation = generation
journal: Journal | None = None
archive_queue: deque[dict] = deque(maxlen=256)


def checkpoint() -> None:
    if journal:
        journal.save(capture_history(incidents, ledger, reports, healer.level, sequence))


def control_lock() -> asyncio.Lock:
    """One mutation boundary per event loop; test clients can own independent loops."""
    loop = asyncio.get_running_loop()
    if loop not in _locks:
        _locks[loop] = asyncio.Lock()
    return _locks[loop]


def advance_generation() -> None:
    global generation, last_samples, last_observed_at
    generation = str(uuid4())
    last_samples = []
    last_observed_at = None
    healer.generation = generation


def snapshot_state() -> dict:
    """Immutable coherent bootstrap; sequence identifies the last published event."""
    return jsonable_encoder(
        {
            "generation": generation,
            "sequence": sequence,
            "topology": topology(),
            "telemetry": last_samples,
            "detector": {
                "ready": detector.ready,
                "progress": min(1.0, detector.ticks_seen / detector.warmup_ticks),
            },
            "anomalies": list(detector.active.values()),
            "diagnosis": rca.hypotheses,
            "diagnosis_meta": {
                "status": getattr(rca, "diagnosis_status", "supported"),
                "reason": getattr(rca, "uncertainty_reason", None),
                "confidence_kind": "heuristic",
            },
            "incident": incident_state(),
            "autonomy": get_autonomy(),
            "backend": {"kind": backend},
            "observed_at": last_observed_at,
            "emitted_at": datetime.now(UTC),
        }
    )


@asynccontextmanager
async def serialized():
    async with control_lock():
        yield


def controlled(fn):
    """Serialize REST control commands with telemetry and forwarding changes."""

    @wraps(fn)
    async def wrapped(*args, **kwargs):
        async with serialized():
            result = await fn(*args, **kwargs)
            checkpoint()
            return result

    return wrapped


async def broadcast(envelope: Envelope) -> None:
    global sequence
    sequence += 1
    envelope.generation, envelope.sequence = generation, sequence
    envelope.emitted_at = datetime.now(UTC)
    if envelope.type == "telemetry":
        envelope.detector = {
            "ready": detector.ready,
            "progress": min(1.0, detector.ticks_seen / detector.warmup_ticks),
        }
    record = envelope.model_dump(mode="json")
    if envelope.type == "rca":
        record["diagnosis_meta"] = {
            "status": getattr(rca, "diagnosis_status", "uncertain"),
            "reason": getattr(rca, "uncertainty_reason", None),
            "unexplained_flows": getattr(rca, "unexplained_flows", []),
            "confidence_kind": "heuristic",
        }
    message = json.dumps(record, allow_nan=False)
    if journal and envelope.type != "telemetry":
        journal.append(record, capture_history(incidents, ledger, reports, healer.level, sequence))
    elif bus.BOOTSTRAP or producer:
        archive_queue.append(record)

    async def send(ws):
        try:
            await asyncio.wait_for(ws.send_text(message), timeout=0.15)
        except Exception:
            clients.discard(ws)
            with suppress(Exception):
                await asyncio.wait_for(ws.close(code=1013), timeout=0.1)

    if clients:
        await asyncio.gather(*(send(ws) for ws in list(clients)))


async def archive_loop() -> None:
    """Broker acknowledgements and retries never block simulation or operator commands."""
    global producer
    while True:
        try:
            if producer is None and bus.BOOTSTRAP:
                candidate = AIOKafkaProducer(bootstrap_servers=bus.BOOTSTRAP, linger_ms=20)
                try:
                    await asyncio.wait_for(candidate.start(), timeout=8)
                except Exception:
                    await candidate.stop()
                    raise
                producer = candidate
            if producer is None:
                await asyncio.sleep(0.25)
                continue
            pending = journal.pending(limit=1) if journal else []
            record = pending[0] if pending else (archive_queue[0] if archive_queue else None)
            if record is None:
                await asyncio.sleep(0.05)
                continue
            await asyncio.wait_for(
                producer.send_and_wait(bus.TOPICS[record["type"]], json.dumps(record).encode()),
                timeout=3,
            )
            if pending:
                journal.delivered(record["event_id"])
            else:
                # Queue eviction during the await must not drop an unacknowledged event.
                with suppress(ValueError):
                    archive_queue.remove(record)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            obs.BUS_ERRORS.inc()
            print(f"Event archive retry: {type(error).__name__}", flush=True)
            await asyncio.sleep(1)


Operator = Annotated[dict, Depends(auth.require("operator"))]
Admin = Annotated[dict, Depends(auth.require("admin"))]
Viewer = Annotated[dict, Depends(auth.require("viewer"))]


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
    """One tick every TICK_S of wall-clock time: a tick's own work isn't added to the gap."""
    global last_tick_error
    next_at = time.monotonic()
    while True:
        started = time.monotonic()
        try:
            await tick()
        except Exception as error:  # one bad tick must never freeze the live network
            last_tick_error = type(error).__name__
            traceback.print_exc()
        elapsed = time.monotonic() - started
        obs.TICK_SECONDS.observe(elapsed)
        if elapsed > TICK_S:
            obs.TICK_OVERRUNS.inc()
        next_at = max(next_at + TICK_S, time.monotonic())  # after a slow tick: no catch-up burst
        await asyncio.sleep(next_at - time.monotonic())


async def tick() -> None:
    async with serialized():
        await _tick()


async def _tick() -> None:
    global last_samples, last_observed_at, last_tick_error
    with obs.stage("tick"):
        with obs.stage("simulate"):
            samples = last_samples = await asyncio.to_thread(net.step)  # emulator: ~0.2 s
            last_observed_at = datetime.now(UTC)
            last_tick_error = None
            obs.LAST_SAMPLE_UNIX.set(last_observed_at.timestamp())
        with obs.stage("detect"):
            raised, cleared = detector.update(samples)
        for a in raised:
            obs.ANOMALIES_RAISED.labels(a.severity).inc()
        obs.ACTIVE_ANOMALIES.set(len(detector.active))
        await broadcast(Envelope(type="telemetry", data=samples))
        if raised or cleared:
            await broadcast(Envelope(type="anomaly", data={"raised": raised, "cleared": cleared}))
        with obs.stage("diagnose"):
            diagnosed = rca.update(samples, detector.active, net, detector=detector)
        if diagnosed:
            await broadcast(Envelope(type="rca", data=rca.hypotheses))
        with obs.stage("heal"):
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
        obs.HEALING_EVENTS.labels(kind).inc()
        if kind == "rebaseline":  # traffic moved on purpose: new normal for the new path
            detector.relearn(payload)
        await audit("system", f"healing.{kind}", summary(payload))
    if switched and before:
        await audit("system", "incident.closed", {"incident": before.id, "status": before.status})
        obs.INCIDENTS.labels(before.status).inc()
        if before.mttd_s is not None:
            obs.MTTD.observe(before.mttd_s)
        if before.mttr_s is not None:
            obs.MTTR.observe(before.mttr_s)
    if changed:
        for kind, payload in events:
            await broadcast(Envelope(type="action", data={"kind": kind, "payload": payload}))
        await broadcast(Envelope(type="incident", data=incident_state()))
        checkpoint()


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
    global producer, journal, reports, sequence
    archive_queue.clear()
    if state_path := os.getenv("NETHEAL_STATE_PATH"):
        journal = Journal(Path(state_path))
        if body := journal.load():
            reports, level, saved_sequence = restore_history(body, incidents, ledger, net.now)
            healer.level = level if level in LEVELS else 3
            sequence = max(sequence, saved_sequence)
            await audit(
                "system",
                "controller.restarted",
                {"generation": generation, "commands_invalidated": True},
            )
    task = asyncio.create_task(tick_loop())
    archive_task = asyncio.create_task(archive_loop())
    try:
        yield
    finally:
        task.cancel()
        archive_task.cancel()
        for running in (task, archive_task):
            with suppress(asyncio.CancelledError):
                await running
        checkpoint()
        if producer:
            await producer.stop()
            producer = None
        if journal:
            journal.close()
            journal = None


app = FastAPI(title="NetHeal Gateway", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())
obs.setup_tracing("engine", app)


@app.get("/snapshot")
async def snapshot() -> dict:
    async with serialized():
        return snapshot_state()


@app.get("/health")
async def health() -> dict:
    age = (datetime.now(UTC) - last_observed_at).total_seconds() if last_observed_at else None
    return {
        "ok": True,
        "ready": detector.ready
        and age is not None
        and age < 3
        and not detector.quality_issues
        and last_tick_error is None,
        "generation": generation,
        "sequence": sequence,
        "backend": backend,
        "telemetry_age_s": age,
        "detector_ready": detector.ready,
        "last_error": last_tick_error,
        "quality_issues": detector.quality_issues,
        "archive": {
            "configured": bool(bus.BOOTSTRAP),
            "connected": producer is not None,
            "pending_control_events": journal.pending_count() if journal else 0,
        },
    }


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1000)


class AutonomyRequest(BaseModel):
    level: int


@app.post("/auth/login")
@controlled
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
    severity: float = Field(default=1.0, ge=0, le=2, allow_inf_nan=False)
    ramp_s: float = Field(default=0.0, ge=0, le=300, allow_inf_nan=False)


@app.get("/topology")
def topology() -> dict:
    g = net.graph
    return {
        "nodes": [{"id": n, **d} for n, d in g.nodes(data=True)],
        "links": [{"a": a, "b": b, **d} for a, b, d in g.edges(data=True)],
        "flows": [{**f, "route": net.routes[fid]} for fid, f in net.flows.items()],
    }


@app.post("/fault")
@controlled
async def inject_fault(req: FaultRequest, user: Operator) -> dict:
    try:
        fault = net.inject_fault(req.type, req.target, req.severity, req.ramp_s)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    incidents.note_fault(net.now)
    await audit("user", "fault.injected", {"by": user["username"], **req.model_dump()})
    return vars(fault)


@app.post("/reset")
@controlled
async def reset(user: Operator) -> dict:
    global net
    incidents.close(net.now, reason="Network reset interrupted any unfinished recovery.")
    net = new_network()
    cleared = list(detector.active)
    detector.clear()
    rca.clear()
    healer.clear()
    advance_generation()
    await audit("user", "network.reset", {"by": user["username"]})
    await broadcast(Envelope(type="anomaly", data={"raised": [], "cleared": cleared}))
    await broadcast(Envelope(type="rca", data=[]))
    await broadcast(Envelope(type="incident", data=incident_state()))
    return {"ok": True, "generation": generation, "sequence": sequence}


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
async def get_incident(incident_id: str) -> dict:
    async with serialized():
        return jsonable_encoder(incident_detail(incident_id))


def incident_detail(incident_id: str) -> dict:
    inc = incidents.get(incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    ctx = incidents.context[incident_id]
    cached = reports.get(incident_id)
    if cached:
        facts = incident_facts(inc, ctx, entity_namer(net))
        current_hash = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
        if cached.get("evidence_hash") != current_hash:
            cached = None
    return {
        "incident": inc,
        "anomalies": list(ctx["anomalies"].values()),
        "diagnosis": ctx["diagnosis"],
        "actions": ctx["actions"],
        "report": cached,
    }


@app.post("/incidents/{incident_id}/report")
async def report(incident_id: str, user: Operator, refresh: bool = False) -> dict:
    async with serialized():
        inc = incidents.get(incident_id)
        if inc is None:
            raise HTTPException(404, "incident not found")
        facts = incident_facts(inc, incidents.context[incident_id], entity_namer(net))
        evidence_hash = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
        cached = reports.get(incident_id)
        if not refresh and cached and cached.get("evidence_hash") == evidence_hash:
            return copy.deepcopy(cached)
        report_generation = generation
    result = await write_report(facts, llm)
    result.update(
        evidence_hash=evidence_hash,
        generation=report_generation,
        generated_at=datetime.now(UTC).isoformat(),
    )
    async with serialized():
        current = incidents.get(incident_id)
        current_facts = incident_facts(current, incidents.context[incident_id], entity_namer(net))
        current_hash = hashlib.sha256(
            json.dumps(current_facts, sort_keys=True).encode()
        ).hexdigest()
        if generation != report_generation or evidence_hash != current_hash:
            raise HTTPException(409, "Incident changed during report generation; generate again")
        reports[incident_id] = result
        checkpoint()
        return copy.deepcopy(result)


@app.get("/autonomy")
def get_autonomy() -> dict:
    return {"level": healer.level, "levels": LEVELS}


@app.put("/autonomy")
@controlled
async def set_autonomy(req: AutonomyRequest, user: Admin) -> dict:
    if req.level not in LEVELS:
        raise HTTPException(400, f"level must be one of {list(LEVELS)}")
    await audit("user", "autonomy.changed", {"by": user["username"], "from": healer.level,
                                             "to": req.level})  # fmt: skip
    healer.set_level(req.level)
    await broadcast(Envelope(type="autonomy", data=get_autonomy()))
    return get_autonomy()


@app.get("/approvals")
def approvals() -> dict:
    return {"awaiting": healer.awaiting, "incident_id": rca.incident_id}


@app.post("/approvals/{action_id}/{decision}")
@controlled
async def decide(action_id: str, decision: str, user: Operator) -> dict:
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "use approve or reject")
    try:
        if decision == "approve":
            if not last_observed_at or (datetime.now(UTC) - last_observed_at).total_seconds() > 3:
                raise HTTPException(409, "Telemetry is stale; wait for fresh measurements")
            events = healer.approve(
                action_id,
                {s.entity_id: s for s in last_samples},
                net,
                baseline={
                    f: float(detector.median[f][0]) for f in net.flows if f in detector.median
                },
            )
        else:
            events = healer.reject(action_id)
    except KeyError as e:
        raise HTTPException(409, "That fix is no longer waiting for approval") from e
    outcome = f"approval.{decision}d"
    if decision == "approve" and not any(kind == "applied" for kind, _ in events):
        outcome = "approval.not_applied"
    await audit("user", outcome, {"by": user["username"], "action": action_id})
    await handle(events)
    return incident_state()


@app.get("/audit")
def audit_log(limit: int = 200) -> list:
    return ledger.entries[-limit:][::-1]


@app.get("/audit/verify")
def audit_verify() -> dict:
    return ledger.verify()


class WhatIfRequest(BaseModel):
    fault: str
    target: str
    severity: float = Field(default=1.0, ge=0, le=2, allow_inf_nan=False)
    preserve_faults: bool = False


@app.post("/whatif")
async def simulate(req: WhatIfRequest) -> dict:
    """Read-only: runs the fault and NetHeal's plan on a digital twin."""
    try:
        async with serialized():
            twin = net.snapshot()
            preview_healer = Healer(healer.policy, healer.rl)
            preview_healer.level = healer.level
            preview_healer.applied_at = list(healer.applied_at)
            preview_healer.generation = generation
            preview_healer.baseline = dict(healer.baseline)
        return await asyncio.to_thread(
            what_if,
            twin,
            preview_healer,
            req.fault,
            req.target,
            req.severity,
            preserve_faults=req.preserve_faults,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


class Turn(BaseModel):
    """Earlier chat turns: only user/assistant text, so nobody can inject a "system" message."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default=[], max_length=200)  # the agent uses the last 6


@app.post("/copilot")
async def copilot(req: CopilotRequest, user: Viewer) -> dict:
    async with serialized():
        captured_at = datetime.now(UTC)
        observed_at = last_observed_at
        await audit(
            "user", "copilot.asked", {"by": user["username"], "question_chars": len(req.question)}
        )
        isolated_healer = Healer(healer.policy, healer.rl)
        isolated_healer.level = healer.level
        isolated_healer.applied_at = list(healer.applied_at)
        isolated_healer.baseline = dict(healer.baseline)
        isolated_healer.generation = generation
        ctx = Context(
            net=net.snapshot(),
            latest=copy.deepcopy({s.entity_id: s for s in last_samples}),
            detector=SimpleNamespace(active=copy.deepcopy(detector.active)),
            rca=SimpleNamespace(hypotheses=copy.deepcopy(rca.hypotheses)),
            incidents=copy.deepcopy(incidents),
            ledger=copy.deepcopy(ledger),
            healer=isolated_healer,
            docs=docs,
            snapshot_generation=generation,
        )
    with obs.COPILOT_SECONDS.time():
        history = [t.model_dump() for t in req.history]
        answer = await ask(req.question, history, ctx, llm)
    now = datetime.now(UTC)
    age = (now - captured_at).total_seconds()
    stale = (
        generation != ctx.snapshot_generation
        or observed_at is None
        or (now - observed_at).total_seconds() >= 3
    )
    answer.update(
        captured_at=captured_at.isoformat(),
        observed_at=observed_at.isoformat() if observed_at else None,
        generation=ctx.snapshot_generation,
        snapshot_age_s=round(age, 3),
        stale=stale,
        documentation_version=docs.version,
    )
    if stale:
        answer["answer"] = (
            f"This answer describes a captured snapshot from {captured_at:%H:%M:%S} UTC. "
            "The live dashboard may have newer state.\n\n" + answer["answer"]
        )
    return answer


MODELS_DIR = Path(__file__).resolve().parents[1] / "ml" / "models"


@app.get("/insights")
def insights() -> dict:
    every = [*incidents.history, *([incidents.current] if incidents.current else [])]
    done = [i for i in every if i.status == "resolved" and i.mttr_s is not None]
    causes: dict[str, int] = {}
    for i in every:
        top = incidents.context[i.id]["diagnosis"][:1]
        if top:
            causes[top[0].cause] = causes.get(top[0].cause, 0) + 1
    return {
        "models": {
            name: json.loads((MODELS_DIR / f"{name}_eval.json").read_text())
            for name in ("rca", "forecast", "lstm_ae", "rl")
        },  # fmt: skip
        "incidents": {
            "total": len(every),
            "healed": len(done),
            "escalated": sum(i.status == "failed" for i in every),
            "avg_mttd_s": round(
                sum(i.mttd_s for i in every if i.mttd_s is not None)
                / max(1, sum(i.mttd_s is not None for i in every)),
                2,
            )
            if every
            else None,
            "avg_mttr_s": round(sum(i.mttr_s for i in done) / len(done), 2) if done else None,
            "by_cause": causes,
        },
    }


@app.get("/insights/shap.png")
def shap_plot() -> FileResponse:
    return FileResponse(MODELS_DIR / "forecast_shap.png")


EVALUATION = Path(__file__).resolve().parents[2] / "docs" / "evaluation.json"


@app.get("/evaluation")
def evaluation() -> FileResponse:
    """Results of `./netheal eval`: summary per policy and fault type, plus every run."""
    if not EVALUATION.exists():
        raise HTTPException(404, "No evaluation yet: run ./netheal eval")
    return FileResponse(EVALUATION, media_type="application/json")


STUDY_DOCUMENT = (
    Path(__file__).resolve().parents[2] / "deliverables" / "NetHeal-Study-Companion.html"
)


@app.get("/study", include_in_schema=False)
def study_companion() -> FileResponse:
    if not STUDY_DOCUMENT.is_file():
        raise HTTPException(404, "The packaged study companion is unavailable")
    return FileResponse(
        STUDY_DOCUMENT, media_type="text/html", headers={"Cache-Control": "no-store"}
    )


@app.get("/settings")
def settings() -> dict:
    return {
        "autonomy": get_autonomy(),
        "policy": healer.policy.source,
        "users": [{"username": u, "role": d["role"]} for u, d in auth.USERS.items()],
        "llm": {
            "model": MODEL,
            "configured": llm is not None,
            "embeddings": EMBED_MODEL,
            "providers": [{"model": m, "label": a} for _, m, a in (llm.providers if llm else [])],
        },
        "detector": {
            "warmup_s": detector.warmup_ticks * TICK_S,
            "z_threshold": Z_THRESHOLD,
            "raise_after": "3 of 4 bad readings",
            "clear_after": "6 good readings",
        },  # fmt: skip
        "models_loaded": {
            "gnn": rca.gnn is not None,
            "forecaster": detector.forecaster is not None,
            "lstm_autoencoder": detector.autoencoder is not None,
            "rl_router": healer.rl is not None,
        },  # fmt: skip
    }


class BackendRequest(BaseModel):
    kind: str


@app.get("/backend")
def get_backend() -> dict:
    return {"kind": backend, "emulab_url": EMULAB_URL, "emulab_ready": emulab_ready()}


@app.post("/backend")
@controlled
async def set_backend(req: BackendRequest, user: Admin) -> dict:
    """Swap simulator <-> emulated network. The detector re-learns the new network's normal."""
    global net, detector, backend
    if req.kind not in ("sim", "emu"):
        raise HTTPException(400, "kind must be sim or emu")
    if req.kind == "emu" and not emulab_ready():
        raise HTTPException(409, "The emulated network isn't running (start it with ./netheal emu)")
    cleared = list(detector.active)
    if backend == "emu":  # leave the emulator clean (faults off)
        with suppress(OSError):
            net.clear_faults()
    incidents.close(net.now, reason="Backend switch interrupted any unfinished recovery.")
    backend = req.kind
    net, detector = new_network(), new_detector()
    rca.clear()
    healer.clear()
    advance_generation()
    await audit("user", "backend.switched", {"by": user["username"], "to": backend})
    if cleared:
        await broadcast(Envelope(type="anomaly", data={"raised": [], "cleared": cleared}))
        await broadcast(Envelope(type="rca", data=[]))
    await broadcast(Envelope(type="incident", data=incident_state()))
    return {**get_backend(), "generation": generation, "sequence": sequence}
