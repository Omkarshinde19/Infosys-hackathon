from datetime import UTC, datetime

import pytest

from contracts.models import (
    ActionCandidate,
    ActionResult,
    Anomaly,
    Envelope,
    Evidence,
    FeatureVector,
    Incident,
    LedgerEntry,
    RCAHypothesis,
    TelemetrySample,
    TimelineEvent,
    TwinPrediction,
)

NOW = datetime(2026, 10, 7, 10, 42, 1, tzinfo=UTC)

EXAMPLES = [
    TelemetrySample(
        ts=NOW,
        entity_type="link",
        entity_id="core1-dist2",
        latency_ms=4.2,
        loss_pct=0.1,
        throughput_mbps=612.0,
        util=0.61,
        queue_len=12,
    ),
    FeatureVector(ts=NOW, entity_id="core1-dist2", window_s=10, features={"latency_z": 0.3}),
    Anomaly(
        ts=NOW,
        entity_id="core1-library",
        metric="loss_pct",
        value=14.2,
        baseline=0.1,
        score=0.97,
        detectors=["zscore"],
        severity="critical",
    ),
    RCAHypothesis(
        incident_id="i1",
        cause="gray_failure",
        target="core1-library",
        confidence=0.94,
        evidence=[Evidence(description="11/12 failing flows", weight=0.6)],
    ),
    ActionCandidate(
        incident_id="i1",
        type="reroute",
        params={"avoid": ["core1-library"]},
        twin_prediction=TwinPrediction(latency_ms=22, loss_pct=0.2, max_util=0.58),
    ),
    ActionResult(
        action_id="a1",
        applied_at=NOW,
        verified=True,
        rolled_back=False,
        before={"latency_ms": 180},
        after={"latency_ms": 22},
    ),
    Incident(status="resolved", opened_at=NOW, timeline=[TimelineEvent(ts=NOW, stage="detect")]),
    LedgerEntry(
        seq=1,
        ts=NOW,
        actor="system",
        event_type="action.applied",
        payload_hash="a",
        prev_hash="b",
        hash="c",
    ),
    Envelope(type="telemetry", data=[{"entity_id": "x"}]),
]


@pytest.mark.parametrize("msg", EXAMPLES, ids=lambda m: type(m).__name__)
def test_json_round_trip(msg):
    assert type(msg).model_validate_json(msg.model_dump_json()) == msg


def test_rejects_unknown_cause():
    with pytest.raises(ValueError):
        RCAHypothesis(incident_id="i1", cause="aliens", target="x", confidence=1, evidence=[])
