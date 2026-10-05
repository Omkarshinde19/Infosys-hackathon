"""Tamper-evident audit ledger: an append-only SHA-256 hash chain.

Each entry stores the hash of its payload and of the previous entry, so changing any
past entry (or deleting/reordering one) breaks every hash after it, and verify() points at
the first broken entry.
"""

import hashlib
import json
from datetime import datetime

from contracts.models import LedgerEntry

GENESIS = "0" * 64


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _payload_hash(payload: dict) -> str:
    return _sha(json.dumps(payload, sort_keys=True, default=str))


def _entry_hash(e: LedgerEntry) -> str:
    return _sha(
        f"{e.seq}|{e.ts.isoformat()}|{e.actor}|{e.event_type}|{e.payload_hash}|{e.prev_hash}"
    )


class Ledger:
    def __init__(self):
        self.entries: list[LedgerEntry] = []

    def append(self, ts: datetime, actor: str, event_type: str, payload: dict) -> LedgerEntry:
        entry = LedgerEntry(
            seq=len(self.entries) + 1, ts=ts, actor="user" if actor != "system" else "system",
            event_type=event_type, payload=payload, payload_hash=_payload_hash(payload),
            prev_hash=self.entries[-1].hash if self.entries else GENESIS, hash="",
        )  # fmt: skip
        entry.hash = _entry_hash(entry)
        self.entries.append(entry)
        return entry

    def verify(self) -> dict:
        """{"valid": bool, "broken_at": seq of the first bad entry or None, "entries": n}."""
        prev = GENESIS
        for e in self.entries:
            if (
                e.prev_hash != prev
                or e.payload_hash != _payload_hash(e.payload)
                or e.hash != _entry_hash(e)
            ):
                return {"valid": False, "broken_at": e.seq, "entries": len(self.entries)}
            prev = e.hash
        return {"valid": True, "broken_at": None, "entries": len(self.entries)}
