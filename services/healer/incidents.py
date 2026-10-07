"""Incident lifecycle: one incident per episode of alerts, with the MAPE-K timeline.

MTTD = detected_at - opened_at, MTTR = healed_at - opened_at. When the fault was
injected through the API we know its true start time (opened_at); otherwise the
incident opens when it is first detected.

Each incident also keeps its context (alerts, diagnosis, healing actions) so it can be
reviewed and reported on after it closes.
"""

import copy
from datetime import datetime

from contracts.models import Anomaly, Incident, RCAHypothesis, TimelineEvent


class IncidentTracker:
    def __init__(self):
        self.current: Incident | None = None
        self.history: list[Incident] = []
        self.fault_at: datetime | None = None
        self.context: dict[str, dict] = {}  # incident id -> anomalies, diagnosis, actions

    def get(self, incident_id: str) -> Incident | None:
        return next((i for i in [self.current, *self.history] if i and i.id == incident_id), None)

    def note_fault(self, ts: datetime) -> None:
        if self.current is None and self.fault_at is None:
            self.fault_at = ts

    def close(self, ts: datetime, reason: str | None = None) -> bool:
        """End the current incident (alerts gone, or the network was reset)."""
        self.fault_at = None
        if self.current is None:
            return False
        inc = self.current
        if inc.status in ("open", "diagnosing", "healing", "alerted"):
            inc.status = "failed"
            inc.healed_at, inc.mttr_s = None, None
            inc.decision_reason = (
                reason
                or "Alerts cleared without verified service recovery; the incident was closed."
            )
        elif reason and inc.status == "failed":
            inc.decision_reason = reason
        self._mark(ts, "close")
        self.current.closed_at = ts
        self.history.append(self.current)
        self.current = None
        return True

    def update(
        self,
        ts: datetime,
        active: dict[str, Anomaly],
        hypotheses: list[RCAHypothesis],
        events: list[tuple[str, object]],
    ) -> bool:
        """Feed one tick. Returns True when the incident changed."""
        changed = False
        inc = self.current
        if inc is None:
            if not active:
                return False  # healthy (an injected fault may not be detected yet)
            opened = self.fault_at or ts
            inc = self.current = Incident(
                status="open", opened_at=opened, detected_at=ts,
                mttd_s=(ts - opened).total_seconds(),
            )  # fmt: skip
            self.context[inc.id] = {
                "anomalies": {},
                "diagnosis": [],
                "diagnosis_history": [],
                "actions": [],
            }
            self._mark(ts, "detect")
            changed = True

        ctx = self.context[inc.id]
        for entity, anomaly in active.items():
            ctx["anomalies"].setdefault(entity, anomaly.model_copy(deep=True))
        planning = any(kind in ("proposed", "relapsed", "replanning") for kind, _ in events)
        if hypotheses and (inc.status in ("open", "diagnosing") or planning):
            ctx["diagnosis"] = [h.model_copy(deep=True) for h in hypotheses]
            if planning:
                ctx["diagnosis_history"].append({"ts": ts, "hypotheses": ctx["diagnosis"]})
        if hypotheses and inc.diagnosed_at is None:
            inc.diagnosed_at, inc.status = ts, "diagnosing"
            self._mark(ts, "diagnose", hypotheses[0].id)
            changed = True

        for kind, payload in events:
            changed = True
            ctx["actions"].append({"kind": kind, "payload": copy.deepcopy(payload)})
            if kind == "proposed":
                inc.status = "healing"
                inc.decision_reason = (
                    "Candidate repairs are being checked against service SLAs and policy."
                )
                self._mark(ts, "decide")
            elif kind == "applied":
                inc.status = "healing"
                inc.healed_at, inc.mttr_s = None, None
                self._mark(ts, "heal", payload.id)
            elif kind == "result" and payload.verified:
                inc.status, inc.healed_at = "resolved", ts
                inc.first_healed_at = inc.first_healed_at or ts
                inc.mttr_s = (ts - inc.opened_at).total_seconds()
                inc.recovery_attempts.append(
                    {
                        "action_id": payload.action_id,
                        "at": ts,
                        "verified": True,
                        "outcome": payload.outcome or "verified",
                        "mttr_s": inc.mttr_s,
                    }
                )
                self._mark(ts, "verify", payload.action_id)
            elif kind == "result":
                inc.healed_at, inc.mttr_s = None, None
                inc.recovery_attempts.append(
                    {
                        "action_id": payload.action_id,
                        "at": ts,
                        "verified": False,
                        "rolled_back": payload.rolled_back,
                        "outcome": payload.outcome,
                        "failure_reason": payload.failure_reason,
                        "rollback_error": payload.rollback_error,
                    }
                )
                if payload.rollback_attempted or payload.rolled_back:
                    self._mark(ts, "rollback", payload.action_id)
            elif kind == "escalated":
                inc.status = "failed"
                inc.healed_at, inc.mttr_s = None, None
                inc.decision_reason = str(payload)
            elif kind == "relapsed":  # the verified fix stopped holding
                inc.status = "healing"
                inc.healed_at, inc.mttr_s = None, None
                inc.decision_reason = str(payload)
            elif kind == "no_action":  # decided: nothing to fix (no user traffic affected)
                inc.status = "resolved"
                inc.decision_reason = str(payload)
                self._mark(ts, "decide")
            elif kind == "alert_only":  # comfort level 0: a human was alerted, nothing fixed
                inc.status = "alerted"
                inc.decision_reason = str(payload)
                self._mark(ts, "decide")
            elif kind == "replanning":
                inc.status = "diagnosing"
                inc.healed_at, inc.mttr_s = None, None
                inc.decision_reason = str(payload)
            elif kind == "awaiting_approval":
                inc.status = "healing"
                inc.decision_reason = (
                    "This candidate requires fresh human approval before it can be applied."
                )
            elif kind == "recommended":
                inc.decision_reason = (
                    "A safe repair was recommended for a human to apply; "
                    "service recovery is unverified."
                )
            elif kind == "rejected":
                inc.status = "alerted"
                inc.decision_reason = (
                    "The proposed repair was rejected; no service recovery was verified."
                )
        if not active:  # after the events, so a fix that ends the incident is recorded
            self.close(ts)
            changed = True
        return changed

    def _mark(self, ts: datetime, stage: str, ref_id: str | None = None) -> None:
        self.current.timeline.append(TimelineEvent(ts=ts, stage=stage, ref_id=ref_id))
