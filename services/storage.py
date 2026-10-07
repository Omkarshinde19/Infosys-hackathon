"""Local durable event journal and reviewed history checkpoint.

SQLite is the native demo's history/outbox store. A controller restart starts a clean
simulator and invalidates unfinished actions; it never resumes forwarding commands.
The optional Timescale sink remains the long-term telemetry archive in Docker mode.
"""

import json
import sqlite3
from pathlib import Path

from fastapi.encoders import jsonable_encoder

from contracts.models import (
    ActionCandidate,
    ActionResult,
    Anomaly,
    Incident,
    LedgerEntry,
    RCAHypothesis,
)


class Journal:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL,
                kind TEXT NOT NULL, envelope TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS checkpoint (
                id INTEGER PRIMARY KEY CHECK (id = 1), body TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def append(self, envelope: dict, checkpoint: dict | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO events(event_id,sequence,kind,envelope) VALUES(?,?,?,?)",
                (
                    envelope["event_id"],
                    envelope["sequence"],
                    envelope["type"],
                    json.dumps(envelope, allow_nan=False),
                ),
            )
            if checkpoint is not None:
                self._save(checkpoint)

    def pending(self, limit: int = 100) -> list[dict]:
        return [
            json.loads(row[0])
            for row in self.conn.execute(
                "SELECT envelope FROM events WHERE delivered=0 ORDER BY rowid LIMIT ?", (limit,)
            )
        ]

    def pending_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM events WHERE delivered=0").fetchone()[0]

    def delivered(self, event_id: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE events SET delivered=1 WHERE event_id=?", (event_id,))

    def save(self, body: dict) -> None:
        with self.conn:
            self._save(body)

    def _save(self, body: dict) -> None:
        self.conn.execute(
            "INSERT INTO checkpoint(id,body) VALUES(1,?) "
            "ON CONFLICT(id) DO UPDATE SET body=excluded.body",
            (json.dumps(body, allow_nan=False),),
        )

    def load(self) -> dict | None:
        row = self.conn.execute("SELECT body FROM checkpoint WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        self.conn.close()


def capture_history(incidents, ledger, reports: dict, level: int, sequence: int) -> dict:
    return jsonable_encoder(
        {
            "version": 1,
            "history": incidents.history,
            "current": incidents.current,
            "context": incidents.context,
            "ledger": ledger.entries,
            "reports": reports,
            "level": level,
            "sequence": sequence,
        }
    )


def restore_history(body: dict, incidents, ledger, now) -> tuple[dict, int, int]:
    """Restore reviewed evidence, never an executable candidate or network configuration."""
    if body.get("version") != 1:
        raise ValueError("Unsupported controller checkpoint version")
    history = [Incident.model_validate(i) for i in body["history"]]
    current = Incident.model_validate(body["current"]) if body.get("current") else None
    context = {}
    for key, raw in body["context"].items():
        ctx = dict(raw)
        ctx["anomalies"] = {k: Anomaly.model_validate(a) for k, a in raw["anomalies"].items()}
        ctx["diagnosis"] = [RCAHypothesis.model_validate(h) for h in raw["diagnosis"]]
        ctx["actions"] = []
        for action in raw["actions"]:
            payload, kind = action["payload"], action["kind"]
            if kind == "proposed":
                payload = [ActionCandidate.model_validate(c) for c in payload]
            elif kind == "applied":
                payload = ActionCandidate.model_validate(payload)
            elif kind == "result":
                payload = ActionResult.model_validate(payload)
            ctx["actions"].append({"kind": kind, "payload": payload})
        context[key] = ctx
    entries = [LedgerEntry.model_validate(e) for e in body["ledger"]]
    # Validate before installing any restored state.
    from services.ledger.ledger import Ledger

    checked = Ledger()
    checked.entries = entries
    if not checked.verify()["valid"]:
        raise ValueError("Controller checkpoint audit chain is invalid")
    if current:
        if current.status not in ("resolved", "failed"):
            current.status = "failed"
            current.healed_at, current.mttr_s = None, None
        current.closed_at = now
        current.decision_reason = (
            "Controller restarted; simulator reset and unfinished commands invalidated."
        )
        history.append(current)
    incidents.history, incidents.context = history, context
    incidents.current, incidents.fault_at = None, None
    ledger.entries = entries
    return body.get("reports", {}), int(body.get("level", 3)), int(body.get("sequence", 0))
