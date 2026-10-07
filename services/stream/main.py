"""Stream gateway: fans NetHeal events out from Redpanda to browsers over WebSocket.

Any number of these can run; each reads every message (no consumer group). Redis keeps
the latest *full-state* envelopes (telemetry tick, diagnosis, incident) so a browser that
connects mid-incident sees the current state immediately.

Run: uvicorn services.stream.main:app  (needs KAFKA_BOOTSTRAP and REDIS_URL)
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from prometheus_client import make_asgi_app

from services import bus
from services import observability as obs

STATE_TYPES = ("telemetry", "rca", "incident")  # anomaly/action events are deltas: not replayed
STATE_TOPICS = {bus.TOPICS[t]: t for t in STATE_TYPES}

clients: set[WebSocket] = set()
obs.WS_CLIENTS.labels("stream").set_function(lambda: len(clients))
cache: redis.Redis | None = None
consumer_ready = False
last_error: str | None = None


async def on_message(topic: str, message: str) -> None:
    obs.MESSAGES.labels("stream", topic).inc()
    if topic in STATE_TOPICS:
        try:
            key = f"last:{STATE_TOPICS[topic]}"
            incoming = json.loads(message)
            prior = await cache.get(key)
            previous = json.loads(prior) if prior else {}
            # Wall emission time orders cache state across controller generations.
            fresh = (
                not incoming.get("emitted_at")
                or not previous.get("emitted_at")
                or incoming["emitted_at"] >= previous["emitted_at"]
            )
            if fresh:
                await cache.set(key, message)
        except Exception as error:
            obs.BUS_ERRORS.inc()
            print(f"Stream cache unavailable: {type(error).__name__}", flush=True)

    async def send(ws):
        try:
            await asyncio.wait_for(ws.send_text(message), timeout=0.15)
        except Exception:
            clients.discard(ws)
            with suppress(Exception):
                await asyncio.wait_for(ws.close(code=1013), timeout=0.1)

    if clients:
        await asyncio.gather(*(send(ws) for ws in list(clients)))


async def consume() -> None:
    global consumer_ready, last_error
    while True:
        consumer = AIOKafkaConsumer(
            *bus.TOPICS.values(), bootstrap_servers=bus.BOOTSTRAP, auto_offset_reset="latest"
        )
        try:
            await consumer.start()
            consumer_ready, last_error = True, None
            async for msg in consumer:
                await on_message(msg.topic, msg.value.decode())
        except asyncio.CancelledError:
            raise
        except Exception as error:
            consumer_ready, last_error = False, type(error).__name__
            obs.BUS_ERRORS.inc()
            print(f"Stream broker retry: {last_error}", flush=True)
        finally:
            consumer_ready = False
            await consumer.stop()
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global cache
    cache = redis.from_url(os.environ["REDIS_URL"])
    task = asyncio.create_task(consume())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await cache.aclose()


app = FastAPI(title="NetHeal Stream", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())
obs.setup_tracing("stream", app)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ready": consumer_ready, "clients": len(clients), "last_error": last_error}


@app.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    for t in STATE_TYPES:  # catch up a late joiner
        try:
            if last := await cache.get(f"last:{t}"):
                await asyncio.wait_for(ws.send_text(last.decode()), timeout=0.15)
        except Exception:
            break  # browser bootstraps from the coherent engine /snapshot
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
