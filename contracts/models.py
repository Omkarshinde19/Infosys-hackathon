"""Message contracts shared by every NetHeal service. Documented in docs/CONTRACTS.md."""

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


def new_id() -> str:
    return str(uuid4())


EntityType = Literal["link", "node", "flow"]
Cause = Literal[
    "link_failure", "gray_failure", "congestion", "node_overload", "misconfig", "flapping"
]
ActionType = Literal[
    "reroute", "ecmp_split", "rate_limit", "drain_node", "rollback_config", "quarantine_link"
]
IncidentStatus = Literal["open", "diagnosing", "healing", "resolved", "alerted", "failed"]


class TelemetrySample(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    ts: AwareDatetime
    entity_type: EntityType
    entity_id: str
    latency_ms: float | None = Field(default=None, ge=0)
    loss_pct: float | None = Field(default=None, ge=0, le=100)
    throughput_mbps: float | None = Field(default=None, ge=0)
    util: float | None = Field(default=None, ge=0)  # offered load may exceed capacity
    cpu: float | None = Field(default=None, ge=0)
    queue_len: float | None = Field(default=None, ge=0)


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
    model_config = ConfigDict(allow_inf_nan=False)

    id: str = Field(default_factory=new_id)
    incident_id: str
    cause: Cause
    target: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]
    method_scores: dict[str, float] = {}
    confidence_kind: Literal["heuristic"] = "heuristic"
    supported: bool = True


class TwinPrediction(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    latency_ms: float = Field(ge=0)
    loss_pct: float = Field(ge=0, le=100)
    max_util: float = Field(ge=0)
    max_loss_pct: float = Field(default=0.0, ge=0, le=100)
    other_latency_ratio: float = Field(default=0.0, ge=0)
    per_flow: dict[str, dict[str, float | bool]] = Field(default_factory=dict)


class ActionCandidate(BaseModel):
    id: str = Field(default_factory=new_id)
    incident_id: str
    type: ActionType
    params: dict[str, Any]
    twin_prediction: TwinPrediction | None = None
    opa_decision: Literal["allow", "deny"] | None = None
    policy_reasons: list[str] = []  # why the guardrails denied it (empty when allowed)
    risk_score: float = 0.0
    planned_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    state_fingerprint: str | None = None
    planning_version: str | None = None


class ActionResult(BaseModel):
    action_id: str
    applied_at: datetime
    verified: bool
    rolled_back: bool
    before: dict[str, float]
    after: dict[str, float]
    per_flow_before: dict[str, dict[str, float | bool]] = Field(default_factory=dict)
    per_flow_after: dict[str, dict[str, float | bool]] = Field(default_factory=dict)
    rollback_attempted: bool = False
    rollback_error: str | None = None
    failure_reason: str | None = None
    verification_reasons: list[str] = Field(default_factory=list)
    outcome: Literal["verified", "rolled_back", "execution_failed", "rollback_failed"] | None = None


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
    first_healed_at: AwareDatetime | None = None
    recovery_attempts: list[dict[str, Any]] = Field(default_factory=list)
    decision_reason: str | None = None


class LedgerEntry(BaseModel):
    seq: int
    ts: datetime
    actor: Literal["system", "user"]
    event_type: str
    payload: dict[str, Any] = {}
    payload_hash: str
    prev_hash: str
    hash: str


class Envelope(BaseModel):
    """WebSocket message from the gateway to the frontend."""

    type: Literal["telemetry", "anomaly", "rca", "action", "incident", "kpi", "audit", "autonomy"]
    data: Any
    generation: str | None = None
    sequence: int | None = None
    event_id: str = Field(default_factory=new_id)
    emitted_at: AwareDatetime | None = None
    detector: dict[str, Any] | None = None
