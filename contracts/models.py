"""Message contracts shared by every NetHeal service. Documented in docs/CONTRACTS.md."""

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return str(uuid4())


EntityType = Literal["link", "node", "flow"]
Cause = Literal[
    "link_failure", "gray_failure", "congestion", "node_overload", "misconfig", "flapping"
]
ActionType = Literal[
    "reroute", "ecmp_split", "rate_limit", "drain_node", "rollback_config", "quarantine_link"
]
IncidentStatus = Literal["open", "diagnosing", "healing", "resolved", "failed"]


class TelemetrySample(BaseModel):
    ts: datetime
    entity_type: EntityType
    entity_id: str
    latency_ms: float | None = None
    loss_pct: float | None = None
    throughput_mbps: float | None = None
    util: float | None = None
    cpu: float | None = None
    queue_len: float | None = None


class FeatureVector(BaseModel):
    ts: datetime
    entity_id: str
    window_s: float
    features: dict[str, float]


class Anomaly(BaseModel):
    id: str = Field(default_factory=new_id)
    ts: datetime
    entity_id: str
    metric: str
    value: float
    baseline: float
    score: float
    detectors: list[str]
    severity: Literal["warning", "critical"]


class Evidence(BaseModel):
    anomaly_id: str | None = None
    description: str
    weight: float


class RCAHypothesis(BaseModel):
    id: str = Field(default_factory=new_id)
    incident_id: str
    cause: Cause
    target: str
    confidence: float
    evidence: list[Evidence]
    method_scores: dict[str, float] = {}


class TwinPrediction(BaseModel):
    latency_ms: float
    loss_pct: float
    max_util: float


class ActionCandidate(BaseModel):
    id: str = Field(default_factory=new_id)
    incident_id: str
    type: ActionType
    params: dict[str, Any]
    twin_prediction: TwinPrediction | None = None
    opa_decision: Literal["allow", "deny"] | None = None
    risk_score: float = 0.0


class ActionResult(BaseModel):
    action_id: str
    applied_at: datetime
    verified: bool
    rolled_back: bool
    before: dict[str, float]
    after: dict[str, float]


class TimelineEvent(BaseModel):
    ts: datetime
    stage: Literal["detect", "diagnose", "decide", "heal", "verify", "rollback", "close"]
    ref_id: str | None = None


class Incident(BaseModel):
    id: str = Field(default_factory=new_id)
    status: IncidentStatus
    opened_at: datetime
    detected_at: datetime | None = None
    diagnosed_at: datetime | None = None
    healed_at: datetime | None = None
    closed_at: datetime | None = None
    mttd_s: float | None = None
    mttr_s: float | None = None
    timeline: list[TimelineEvent] = []


class LedgerEntry(BaseModel):
    seq: int
    ts: datetime
    actor: Literal["system", "user"]
    event_type: str
    payload_hash: str
    prev_hash: str
    hash: str


class Envelope(BaseModel):
    """WebSocket message from the gateway to the frontend."""

    type: Literal["telemetry", "anomaly", "rca", "action", "incident", "kpi"]
    data: Any
