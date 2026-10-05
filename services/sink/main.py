"""Sink: consumes every NetHeal topic from Redpanda and stores it in TimescaleDB.

Run: python -m services.sink.main  (needs KAFKA_BOOTSTRAP and DATABASE_URL)
Schema: infra/timescale/init.sql
"""

import asyncio
import json
import os
from datetime import datetime

import asyncpg
from aiokafka import AIOKafkaConsumer

from services import bus

TELEMETRY_COLUMNS = (
    "ts", "entity_type", "entity_id", "latency_ms", "loss_pct",
    "throughput_mbps", "util", "cpu", "queue_len",
)  # fmt: skip


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def to_rows(envelope: dict) -> dict[str, list[tuple]]:
    """Map one bus envelope to rows per table."""
    kind, data = envelope["type"], envelope["data"]
    if kind == "telemetry":
        return {"telemetry": [(_ts(s["ts"]), *(s[c] for c in TELEMETRY_COLUMNS[1:])) for s in data]}
    if kind == "anomaly":
        return {
            "anomalies": [
                (a["id"], _ts(a["ts"]), a["entity_id"], a["metric"], a["value"],
                 a["baseline"], a["score"], a["severity"], a["detectors"])
                for a in data["raised"]
            ]
        }  # fmt: skip
    if kind == "incident":
        inc = data["incident"]
        if inc is None:
            return {}
        return {
            "incidents": [
                (inc["id"], inc["status"], _ts(inc["opened_at"]), _ts(inc["closed_at"]),
                 inc["mttd_s"], inc["mttr_s"], json.dumps(inc))
            ]
        }  # fmt: skip
    return {"events": [(bus.TOPICS[kind], json.dumps(data))]}  # rca, action


async def write(conn: asyncpg.Connection, rows: dict[str, list[tuple]]) -> None:
    if rows.get("telemetry"):
        await conn.copy_records_to_table(
            "telemetry", records=rows["telemetry"], columns=TELEMETRY_COLUMNS
        )
    if rows.get("anomalies"):
        await conn.executemany(
            "INSERT INTO anomalies VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT DO NOTHING",
            rows["anomalies"],
        )
    if rows.get("incidents"):
        await conn.executemany(
            """INSERT INTO incidents VALUES ($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT (id) DO UPDATE SET status = $2, closed_at = $4, mttd_s = $5,
               mttr_s = $6, data = $7""",
            rows["incidents"],
        )
    if rows.get("events"):
        await conn.executemany("INSERT INTO events (topic, data) VALUES ($1, $2)", rows["events"])


async def main() -> None:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    consumer = AIOKafkaConsumer(
        *bus.TOPICS.values(),
        bootstrap_servers=bus.BOOTSTRAP,
        group_id="sink",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    print("sink: consuming", list(bus.TOPICS.values()), flush=True)
    try:
        async for msg in consumer:
            await write(conn, to_rows(json.loads(msg.value)))
    finally:
        await consumer.stop()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
