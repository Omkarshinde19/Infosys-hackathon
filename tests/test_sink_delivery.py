"""Failure/order tests for the sink boundary, using explicit DB/broker fakes.

These prove application call order and recovery logic; they do not constitute a
PostgreSQL/Kafka integration run or prove SQL execution on an actual server.
"""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from aiokafka.structs import TopicPartition

from services import bus
from services.sink.main import process_message, to_rows, write


def message(event_id="event-a", offset=11, clear=False):
    envelope = {
        "event_id": event_id,
        "generation": "generation-a",
        "sequence": offset,
        "type": "anomaly",
        "data": {"raised": [], "cleared": ["alert-a"] if clear else []},
    }
    return SimpleNamespace(
        topic=bus.TOPICS["anomaly"], partition=0, offset=offset, value=json.dumps(envelope).encode()
    )


class Transaction:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        self.before = copy.deepcopy((self.db.receipts, self.db.events))
        self.db.log.append("db.begin")

    async def __aexit__(self, kind, value, traceback):
        if kind or self.db.fail_commit:
            self.db.receipts, self.db.events = self.before
            self.db.log.append("db.rollback")
            if self.db.fail_commit:
                raise OSError("database commit failed")
        else:
            self.db.log.append("db.commit")


class Database:
    def __init__(self, log, fail_write=False, fail_commit=False):
        self.log, self.receipts, self.events = log, {}, []
        self.fail_write, self.fail_commit = fail_write, fail_commit
        self.statements = []

    def transaction(self):
        return Transaction(self)

    async def fetchval(self, sql, topic, partition, offset, event_id):
        self.log.append("db.receipt")
        key = (topic, partition, offset)
        if key in self.receipts or event_id and event_id in self.receipts.values():
            return None
        self.receipts[key] = event_id
        return 1

    async def executemany(self, sql, rows):
        self.statements.append((sql, rows))
        if self.fail_write:
            raise OSError("database payload write failed")
        if "INSERT INTO events" in sql:
            self.log.append("db.payload")
            self.events.extend(copy.deepcopy(rows))


class Broker:
    def __init__(self, log, fail_once=False):
        self.log, self.offsets, self.fail_once = log, [], fail_once

    async def commit(self, offsets):
        self.log.append("broker.ack")
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("broker acknowledgement failed")
        self.offsets.append(offsets)


def test_database_transaction_finishes_before_offset_acknowledgement():
    log = []
    db, broker = Database(log), Broker(log)
    msg = message(clear=True)
    asyncio.run(process_message(db, broker, msg))
    assert log == ["db.begin", "db.receipt", "db.payload", "db.commit", "broker.ack"]
    assert broker.offsets == [{TopicPartition(msg.topic, 0): 12}]
    assert json.loads(db.events[0][1])["data"]["cleared"] == ["alert-a"]


@pytest.mark.parametrize("failure", ["write", "commit", "mapping"])
def test_database_or_mapping_failure_rolls_back_receipt_and_never_acks(failure):
    log = []
    db = Database(log, fail_write=failure == "write", fail_commit=failure == "commit")
    broker, msg = Broker(log), message()
    if failure == "mapping":
        msg.value = json.dumps({"event_id": "bad", "type": "incident", "data": {}}).encode()
    with pytest.raises((OSError, KeyError)):
        asyncio.run(process_message(db, broker, msg))
    assert not db.receipts and not db.events and not broker.offsets
    assert "db.rollback" in log and "broker.ack" not in log


@pytest.mark.parametrize("new_offset", [11, 12])
def test_duplicate_coordinate_or_event_uuid_writes_payload_only_once(new_offset):
    log = []
    db, broker = Database(log), Broker(log)
    asyncio.run(process_message(db, broker, message()))
    asyncio.run(process_message(db, broker, message(offset=new_offset)))
    assert len(db.events) == 1 and len(db.receipts) == 1
    assert broker.offsets[-1] == {TopicPartition(bus.TOPICS["anomaly"], 0): new_offset + 1}


def test_broker_ack_failure_after_db_commit_can_replay_without_duplicate_payload():
    log = []
    db, broker = Database(log), Broker(log, fail_once=True)
    msg = message()
    with pytest.raises(ConnectionError):
        asyncio.run(process_message(db, broker, msg))
    assert len(db.receipts) == len(db.events) == 1 and not broker.offsets
    asyncio.run(process_message(db, broker, msg))
    assert len(db.events) == 1 and broker.offsets == [{TopicPartition(msg.topic, 0): 12}]


def test_anomaly_mapping_retains_updated_evidence_and_the_entire_clear_delta():
    alert = {
        "id": "stable-a",
        "ts": "2026-10-07T06:00:00+00:00",
        "entity_id": "link-a",
        "metric": "loss_pct",
        "value": 10.0,
        "baseline": 0.1,
        "score": 1.0,
        "severity": "critical",
        "detectors": ["zscore", "reachability"],
    }
    envelope = {
        "event_id": "new-a",
        "type": "anomaly",
        "data": {"raised": [alert], "cleared": ["old-a"]},
    }
    rows, db = to_rows(envelope), Database([])
    assert json.loads(rows["events"][0][1]) == envelope
    assert rows["anomalies"][0][4:9] == (10.0, 0.1, 1.0, "critical", alert["detectors"])
    asyncio.run(write(db, rows))
    assert json.loads(db.events[0][1])["data"]["cleared"] == ["old-a"]
