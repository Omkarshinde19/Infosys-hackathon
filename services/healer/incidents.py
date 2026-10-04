"""Incident lifecycle: one incident per episode of alerts, with the MAPE-K timeline.

MTTD = detected_at - opened_at, MTTR = healed_at - opened_at. When the fault was
injected through the API we know its true start time (opened_at); otherwise the
incident opens when it is first detected.
"""

from datetime import datetime

from contracts.models import Anomaly, Incident, RCAHypothesis, TimelineEvent


class IncidentTracker:
    def __init__(self):
        self.current: Incident | None = None
        self.history: list[Incident] = []
        self.fault_at: datetime | None = None

    def note_fault(self, ts: datetime) -> None:
        if self.current is None and self.fault_at is None:
            self.fault_at = ts

    def close(self, ts: datetime) -> bool:
        """End the current incident (alerts gone, or the network was reset)."""
        self.fault_at = None
        if self.current is None:
            return False
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
            self._mark(ts, "detect")
            changed = True
        if hypotheses and inc.diagnosed_at is None:
            inc.diagnosed_at, inc.status = ts, "diagnosing"
            self._mark(ts, "diagnose", hypotheses[0].id)
            changed = True

        for kind, payload in events:
            changed = True
            if kind == "proposed":
                inc.status = "healing"
                self._mark(ts, "decide")
            elif kind == "applied":
                self._mark(ts, "heal", payload.id)
            elif kind == "result" and payload.verified:
                inc.status, inc.healed_at = "resolved", ts
                inc.mttr_s = (ts - inc.opened_at).total_seconds()
                self._mark(ts, "verify", payload.action_id)
            elif kind == "result":
                self._mark(ts, "rollback", payload.action_id)
            elif kind == "escalated":
                inc.status = "failed"
            elif kind == "no_action":
                inc.status = "resolved"
        if not active:  # after the events, so a fix that ends the incident is recorded
            self.close(ts)
            changed = True
        return changed

    def _mark(self, ts: datetime, stage: str, ref_id: str | None = None) -> None:
        self.current.timeline.append(TimelineEvent(ts=ts, stage=stage, ref_id=ref_id))
