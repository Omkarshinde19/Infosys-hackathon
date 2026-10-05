"""Stream gateway: fans NetHeal events out from Redpanda to browsers over WebSocket.

Any number of these can run; each reads every message (no consumer group). Redis keeps
the latest *full-state* envelopes (telemetry tick, diagnosis, incident) so a browser that
connects mid-incident sees the current state immediately.

Run: uvicorn services.stream.main:app  (needs KAFKA_BOOTSTRAP and REDIS_URL)
"""

import asyncio
import os
from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from services import bus

STATE_TYPES = ("telemetry", "rca", "incident")  # anomaly/action events are deltas: not replayed
STATE_TOPICS = {bus.TOPICS[t]: t for t in STATE_TYPES}

clients: set[WebSocket] = set()
cache: redis.Redis | None = None


async def on_message(topic: str, message: str) -> None:
    if topic in STATE_TOPICS:
        await cache.set(f"last:{STATE_TOPICS[topic]}", message)
    for ws in list(clients):
        try:
            await ws.send_text(message)
        except Exception:
            clients.discard(ws)


async def consume() -> None:
    consumer = AIOKafkaConsumer(
        *bus.TOPICS.values(), bootstrap_servers=bus.BOOTSTRAP, auto_offset_reset="latest"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            await on_message(msg.topic, msg.value.decode())
    finally:
        await consumer.stop()


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


@app.get("/health")
def health() -> dict:
    return {"ok": True, "clients": len(clients)}


@app.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    for t in STATE_TYPES:  # catch up a late joiner
        if last := await cache.get(f"last:{t}"):
            await ws.send_text(last.decode())
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
