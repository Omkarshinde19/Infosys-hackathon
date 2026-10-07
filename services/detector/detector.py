"""Anomaly detection: robust z-score + IsolationForest ensemble with debounce.

1. Warm-up: learn each entity's healthy baseline (median + MAD) for WARMUP_TICKS.
2. Every tick, a metric is a candidate when it moves in the *worse* direction by more
   than Z_THRESHOLD robust standard deviations.
3. IsolationForest (trained on the warm-up z-scores) must agree, so a single noisy
   metric can't raise an alert. Unreachable links/flows are hard failures and alert
   without a vote.
4. Debounce: raise after RAISE_K of the last RAISE_N ticks are bad; clear after
   CLEAR_TICKS consecutive normal ticks. A *latency-only* anomaly (latency up while load
   and loss are normal, e.g. a CPU hiccup on an emulated host) must be sustained:
   SUSTAIN_K of the last SUSTAIN_N ticks, like a Prometheus `for:` clause.
5. Change-aware: when the healer deliberately moves traffic, the elements on the new
   path re-learn their baseline for RELEARN_TICKS instead of raising false alerts.
6. Optional forecaster (services/ml/forecast.py): flags flows predicted to breach their
   SLA within 5 s ("forecast" warnings), upgraded to a real alert once they do degrade.
7. Optional LSTM autoencoder (services/ml/lstm_ae.py): a temporal third opinion, added to
   an alert's detectors when the last 10 s also look unusual as a sequence.
8. Flow service checks also watch the healer's 1% loss / 1.1x latency thresholds.
   Sustained service degradation alerts even when its absolute z-score is small;
   a flow symptom alone does not establish an actionable root cause.
"""

from collections import defaultdict, deque
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest

from contracts.models import Anomaly, TelemetrySample

WARMUP_TICKS = 60  # 30 s at 2 ticks/s
Z_THRESHOLD = 6.0
RAISE_K, RAISE_N = 3, 4
SUSTAIN_K, SUSTAIN_N = 6, 8  # latency-only anomalies (~3-4 s)
CLEAR_TICKS = 6
RELEARN_TICKS = 20  # 10 s
RELEARN_TIMEOUT_TICKS = RELEARN_TICKS * 3
TRUSTED_LOSS_PCT = 1.0
TRUSTED_UTIL = 0.85
SERVICE_LATENCY_RATIO = 1.1

# Metrics watched per entity type; all of them are "worse when higher".
METRICS = {
    "flow": ("latency_ms", "loss_pct"),
    "link": ("latency_ms", "loss_pct", "util"),
    "node": ("cpu",),
}
# Minimum spread so near-constant metrics don't turn tiny noise into huge z-scores.
FLOORS = {"latency_ms": 0.5, "loss_pct": 0.5, "util": 0.03, "cpu": 0.03}


class Detector:
    def __init__(self, warmup_ticks: int = WARMUP_TICKS, forecaster=None, autoencoder=None):
        if warmup_ticks < 1:
            raise ValueError("warmup_ticks must be positive")
        self.warmup_ticks = warmup_ticks
        self.forecaster = forecaster
        self.autoencoder = autoencoder
        self.ticks_seen = 0
        self._fitted = False
        self.types: dict[str, str] = {}
        self.warmup: dict[str, list[list[float]]] = defaultdict(list)
        self.median: dict[str, np.ndarray] = {}
        self.scale: dict[str, np.ndarray] = {}
        self.forests: dict[str, IsolationForest] = {}
        self.recent: dict[str, deque[bool]] = defaultdict(lambda: deque(maxlen=SUSTAIN_N))
        self.latency_only: set[str] = set()  # this tick's candidates whose only signal is latency
        self.normal_streak: dict[str, int] = defaultdict(int)
        self.active: dict[str, Anomaly] = {}
        self.relearning: dict[str, list[list[float]]] = {}
        self.relearn_age: dict[str, int] = {}
        self.last_seen: dict[str, datetime] = {}
        self.quality_issues: dict[str, str] = {}
        self.baseline_rejected: dict[str, str] = {}

    @property
    def ready(self) -> bool:
        return self._fitted

    def relearn(self, entity_ids: list[str]) -> None:
        """An intended change (e.g. a reroute) gave these entities a new normal."""
        for e in entity_ids:
            if e in self.median:
                self.relearning[e] = []
                self.relearn_age[e] = 0

    def clear(self) -> None:
        """After a network reset: forget alerts and short-term history, restore the warm-up
        baselines (re-learned ones belonged to routes that no longer exist)."""
        self.recent.clear()
        self.normal_streak.clear()
        self.active.clear()
        self.relearning.clear()
        self.relearn_age.clear()
        self.last_seen.clear()
        self.quality_issues.clear()
        self.baseline_rejected.clear()
        if self.ready:
            self.median, self.scale = dict(self.warmup_median), dict(self.warmup_scale)
        for model in (self.forecaster, self.autoencoder):
            if model is not None:
                model.history.clear()

    def update(self, samples: list[TelemetrySample]) -> tuple[list[Anomaly], list[str]]:
        """Return raised/upgraded/updated alerts and cleared IDs; alert IDs stay stable.

        Warm-up requires a complete valid, low-loss/load window for each entity. This is
        a quality gate, not proof that an unknown steady-state network is fault free.
        """
        self._validate(samples)
        for model in (self.forecaster, self.autoencoder):
            if model is not None:
                for entity in self.quality_issues:
                    model.history.pop(entity, None)
        valid_samples = [s for s in samples if s.entity_id not in self.quality_issues]
        if not self.ready:
            self._collect(samples)
            if self.forecaster is not None:
                self.forecaster.update(valid_samples, {})  # build trusted history during warm-up
            return [], []

        service_healthy = (
            all(
                self._trusted(s)
                and s.latency_ms <= SERVICE_LATENCY_RATIO * self.median[s.entity_id][0]
                for s in samples
                if s.entity_type == "flow" and s.entity_id in self.median
            )
            and not self.quality_issues
        )
        accepted_relearning = set()
        by_id = {s.entity_id: s for s in samples}
        for entity in list(self.relearning):
            rows = self.relearning[entity]
            self.relearn_age[entity] += 1
            s = by_id.get(entity)
            if s is not None and self._trusted(s) and service_healthy:
                rows.append(self._values(s))
                accepted_relearning.add(entity)
            else:
                rows.clear()  # only consecutive trusted observations define a new normal
                self.baseline_rejected[entity] = "Unhealthy or invalid relearning sample"
            if len(rows) >= RELEARN_TICKS:
                self._baseline(entity, np.array(rows, dtype=float))
                del self.relearning[entity]
                del self.relearn_age[entity]
                self.baseline_rejected.pop(entity, None)
            elif self.relearn_age[entity] >= RELEARN_TIMEOUT_TICKS:
                del self.relearning[entity]
                del self.relearn_age[entity]
                self.baseline_rejected[entity] = "Relearning expired; previous baseline retained"
        candidates = self._candidates(samples, accepted_relearning)
        if self.forecaster is not None:
            self._add_forecasts(valid_samples, candidates)
        raised, cleared = [], []
        for e in self.types:
            bad = e in candidates
            self.recent[e].append(bad)
            if e in self.active:
                upgraded = (
                    bad and self.active[e].detectors == ["forecast"] != candidates[e].detectors
                )
                if bad:
                    old = self.active[e]
                    fresh = candidates[e].model_copy(update={"id": old.id})
                    changed = any(
                        getattr(old, key) != getattr(fresh, key)
                        for key in ("metric", "value", "score", "detectors", "severity")
                    )
                    self.active[e] = fresh
                    if upgraded or changed:
                        raised.append(fresh)
                self.normal_streak[e] = 0 if bad else self.normal_streak[e] + 1
                if self.normal_streak[e] >= CLEAR_TICKS:
                    del self.active[e]
                    cleared.append(e)
            elif bad and (
                sum(self.recent[e]) >= SUSTAIN_K
                if e in self.latency_only
                else sum(list(self.recent[e])[-RAISE_N:]) >= RAISE_K
            ):
                self.active[e] = candidates[e]
                raised.append(candidates[e])
        return raised, cleared

    # ---- training --------------------------------------------------------

    @staticmethod
    def _values(sample: TelemetrySample) -> list[float] | None:
        values = [getattr(sample, name) for name in METRICS[sample.entity_type]]
        if any(value is None or not np.isfinite(value) or value < 0 for value in values):
            return None
        if sample.loss_pct is not None and not 0 <= sample.loss_pct <= 100:
            return None
        return values

    def _validate(self, samples) -> None:
        issues, present = {}, set()
        for s in samples:
            if s.entity_id in present:
                issues[s.entity_id] = "Duplicate entity in telemetry tick"
                continue
            present.add(s.entity_id)
            previous = self.last_seen.get(s.entity_id)
            if previous is not None and s.ts <= previous:
                issues[s.entity_id] = "Repeated or out-of-order telemetry timestamp"
            else:
                self.last_seen[s.entity_id] = s.ts
            # None latency is meaningful reachability evidence, not a numeric NaN.
            if self._values(s) is None and not (
                s.entity_type != "node"
                and s.latency_ms is None
                and s.loss_pct is not None
                and np.isfinite(s.loss_pct)
                and 0 <= s.loss_pct <= 100
            ):
                issues[s.entity_id] = "Missing, non-finite or out-of-range required metric"
            for name in ("latency_ms", "loss_pct", "throughput_mbps", "util", "cpu", "queue_len"):
                value = getattr(s, name)
                if value is not None and (not np.isfinite(value) or value < 0):
                    issues[s.entity_id] = "Non-finite or negative telemetry metric"
        for e in self.types.keys() - present:
            issues[e] = "Entity missing from telemetry tick"
        self.quality_issues = issues

    def _trusted(self, sample: TelemetrySample) -> bool:
        return (
            sample.entity_id not in self.quality_issues
            and self._values(sample) is not None
            and (sample.loss_pct is None or sample.loss_pct < TRUSTED_LOSS_PCT)
            and (sample.util is None or sample.util <= TRUSTED_UTIL)
            and (sample.cpu is None or sample.cpu <= TRUSTED_UTIL)
        )

    def _collect(self, samples: list[TelemetrySample]) -> None:
        for s in samples:
            self.types[s.entity_id] = s.entity_type
            rows = self.warmup[s.entity_id]
            if self._trusted(s):
                rows.append(self._values(s))
                del rows[: -self.warmup_ticks]
            else:
                rows.clear()
                self.baseline_rejected[s.entity_id] = "Warm-up requires consecutive trusted samples"
        for e in self.quality_issues:
            self.warmup[e].clear()
        self.ticks_seen += 1
        if self.types and all(len(self.warmup[e]) >= self.warmup_ticks for e in self.types):
            self._fit()

    def _fit(self) -> None:
        z_by_type: dict[str, list[np.ndarray]] = defaultdict(list)
        for e, rows in self.warmup.items():
            x = np.array(rows, dtype=float)
            self._baseline(e, x)
            z_by_type[self.types[e]].append((x - self.median[e]) / self.scale[e])
        for t, zs in z_by_type.items():
            z = np.vstack(zs)
            # contamination="auto": anomalous when score > 0.5 (Liu et al., 2008)
            self.forests[t] = IsolationForest(n_estimators=100, random_state=0).fit(z)
        self.warmup.clear()
        self.warmup_median, self.warmup_scale = dict(self.median), dict(self.scale)
        self.baseline_rejected.clear()
        self._fitted = True

    def _add_forecasts(self, samples: list[TelemetrySample], candidates: dict) -> None:
        baseline = {e: float(m[0]) for e, m in self.median.items() if self.types[e] == "flow"}
        for flow, p in self.forecaster.update(samples, baseline).items():
            if flow not in candidates:
                s = next(x for x in samples if x.entity_id == flow)
                candidates[flow] = Anomaly(
                    ts=s.ts, entity_id=flow, metric="predicted_sla_breach", value=round(p, 3),
                    baseline=round(self.forecaster.threshold, 3), score=round(p, 3),
                    detectors=["forecast"], severity="warning",
                )  # fmt: skip

    def _baseline(self, e: str, x: np.ndarray) -> None:
        if x.ndim != 2 or not len(x) or not np.isfinite(x).all():
            raise ValueError("A baseline requires a finite, nonempty metric matrix")
        floors = np.array([FLOORS[m] for m in METRICS[self.types[e]]])
        self.median[e] = np.median(x, axis=0)
        mad = 1.4826 * np.median(np.abs(x - self.median[e]), axis=0)
        self.scale[e] = np.maximum(mad, floors)

    # ---- detection -------------------------------------------------------

    def _candidates(
        self, samples: list[TelemetrySample], accepted_relearning=()
    ) -> dict[str, Anomaly]:
        self.latency_only = set()
        out: dict[str, Anomaly] = {}
        to_vote: dict[str, list[tuple[TelemetrySample, np.ndarray]]] = defaultdict(list)
        ts = max((s.ts for s in samples), default=max(self.last_seen.values(), default=None))
        if ts is not None:
            for entity in self.quality_issues:
                if entity in self.types:
                    out[entity] = Anomaly(
                        ts=ts,
                        entity_id=entity,
                        metric="telemetry_quality",
                        value=0,
                        baseline=1,
                        score=1,
                        detectors=["telemetry_quality"],
                        severity="critical",
                    )
        for s in samples:
            if s.entity_id in self.quality_issues:
                continue
            if s.entity_type != "node" and s.latency_ms is None:
                out[s.entity_id] = Anomaly(
                    ts=s.ts, entity_id=s.entity_id, metric="reachability", value=0.0,
                    baseline=1.0, score=1.0, detectors=["reachability"], severity="critical",
                )  # fmt: skip
                continue
            if s.entity_id not in self.median:
                continue
            if s.entity_type == "flow" and (
                s.loss_pct >= TRUSTED_LOSS_PCT
                or s.latency_ms > SERVICE_LATENCY_RATIO * self.median[s.entity_id][0]
            ):
                loss = s.loss_pct >= TRUSTED_LOSS_PCT
                metric = "loss_pct" if loss else "latency_ms"
                threshold = (
                    TRUSTED_LOSS_PCT
                    if loss
                    else (SERVICE_LATENCY_RATIO * self.median[s.entity_id][0])
                )
                out[s.entity_id] = Anomaly(
                    ts=s.ts,
                    entity_id=s.entity_id,
                    metric=metric,
                    value=float(getattr(s, metric)),
                    baseline=float(threshold),
                    score=0.7,
                    detectors=["service_sla"],
                    severity="warning",
                )
                if not loss:
                    self.latency_only.add(s.entity_id)
            if s.entity_id in accepted_relearning:
                continue  # intentional healthy load changes only; hard/unsafe faults still alert
            x = np.array([getattr(s, m) for m in METRICS[s.entity_type]], dtype=float)
            z = (x - self.median[s.entity_id]) / self.scale[s.entity_id]
            if self.autoencoder is not None:
                self.autoencoder.observe(s.entity_id, z)
            if z.max() > Z_THRESHOLD:
                to_vote[s.entity_type].append((s, z))
                over = {
                    m for m, v in zip(METRICS[s.entity_type], z, strict=True) if v > Z_THRESHOLD
                }
                if over == {"latency_ms"}:
                    self.latency_only.add(s.entity_id)

        for t, items in to_vote.items():
            votes = self.forests[t].predict(np.vstack([z for _, z in items]))
            for (s, z), vote in zip(items, votes, strict=True):
                if vote != -1:
                    continue  # IsolationForest disagrees
                i = int(z.argmax())
                metric = METRICS[s.entity_type][i]
                out[s.entity_id] = Anomaly(
                    ts=s.ts, entity_id=s.entity_id, metric=metric, value=float(getattr(s, metric)),
                    baseline=float(self.median[s.entity_id][i]),
                    score=round(float(1 - np.exp(-z[i] / Z_THRESHOLD)), 3),
                    detectors=["zscore", "iforest"],
                    severity="critical" if z[i] > 3 * Z_THRESHOLD else "warning",
                )  # fmt: skip
        if self.autoencoder is not None:
            voted = [e for e, a in out.items() if a.detectors == ["zscore", "iforest"]]
            for e in self.autoencoder.unusual(voted):
                out[e].detectors.append("lstm_ae")
        return out
