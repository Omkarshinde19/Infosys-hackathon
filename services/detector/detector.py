"""Anomaly detection: robust z-score + IsolationForest ensemble with debounce.

1. Warm-up: learn each entity's healthy baseline (median + MAD) for WARMUP_TICKS.
2. Every tick, a metric is a candidate when it moves in the *worse* direction by more
   than Z_THRESHOLD robust standard deviations.
3. IsolationForest (trained on the warm-up z-scores) must agree, so a single noisy
   metric can't raise an alert. Unreachable links/flows are hard failures and alert
   without a vote.
4. Debounce: raise after RAISE_K of the last RAISE_N ticks are bad; clear after
   CLEAR_TICKS consecutive normal ticks.
"""

from collections import defaultdict, deque

import numpy as np
from sklearn.ensemble import IsolationForest

from contracts.models import Anomaly, TelemetrySample

WARMUP_TICKS = 60  # 30 s at 2 ticks/s
Z_THRESHOLD = 6.0
RAISE_K, RAISE_N = 3, 4
CLEAR_TICKS = 6

# Metrics watched per entity type; all of them are "worse when higher".
METRICS = {
    "flow": ("latency_ms", "loss_pct"),
    "link": ("latency_ms", "loss_pct", "util"),
    "node": ("cpu",),
}
# Minimum spread so near-constant metrics don't turn tiny noise into huge z-scores.
FLOORS = {"latency_ms": 0.2, "loss_pct": 0.5, "util": 0.03, "cpu": 0.03}


class Detector:
    def __init__(self, warmup_ticks: int = WARMUP_TICKS):
        self.warmup_ticks = warmup_ticks
        self.ticks_seen = 0
        self.types: dict[str, str] = {}
        self.warmup: dict[str, list[list[float]]] = defaultdict(list)
        self.median: dict[str, np.ndarray] = {}
        self.scale: dict[str, np.ndarray] = {}
        self.forests: dict[str, IsolationForest] = {}
        self.recent: dict[str, deque[bool]] = defaultdict(lambda: deque(maxlen=RAISE_N))
        self.normal_streak: dict[str, int] = defaultdict(int)
        self.active: dict[str, Anomaly] = {}

    @property
    def ready(self) -> bool:
        return self.ticks_seen >= self.warmup_ticks

    def clear(self) -> None:
        """Forget active alerts (e.g. after a network reset) but keep the baseline."""
        self.recent.clear()
        self.normal_streak.clear()
        self.active.clear()

    def update(self, samples: list[TelemetrySample]) -> tuple[list[Anomaly], list[str]]:
        """Feed one tick. Returns (newly raised anomalies, entity ids that cleared)."""
        if not self.ready:
            self._collect(samples)
            return [], []

        candidates = self._candidates(samples)
        raised, cleared = [], []
        for s in samples:
            e = s.entity_id
            bad = e in candidates
            self.recent[e].append(bad)
            if e in self.active:
                self.normal_streak[e] = 0 if bad else self.normal_streak[e] + 1
                if self.normal_streak[e] >= CLEAR_TICKS:
                    del self.active[e]
                    cleared.append(e)
            elif sum(self.recent[e]) >= RAISE_K and bad:
                self.active[e] = candidates[e]
                raised.append(candidates[e])
        return raised, cleared

    # ---- training --------------------------------------------------------

    def _collect(self, samples: list[TelemetrySample]) -> None:
        for s in samples:
            self.types[s.entity_id] = s.entity_type
            self.warmup[s.entity_id].append([getattr(s, m) for m in METRICS[s.entity_type]])
        self.ticks_seen += 1
        if self.ready:
            self._fit()

    def _fit(self) -> None:
        z_by_type: dict[str, list[np.ndarray]] = defaultdict(list)
        for e, rows in self.warmup.items():
            x = np.array(rows, dtype=float)
            floors = np.array([FLOORS[m] for m in METRICS[self.types[e]]])
            self.median[e] = np.median(x, axis=0)
            mad = 1.4826 * np.median(np.abs(x - self.median[e]), axis=0)
            self.scale[e] = np.maximum(mad, floors)
            z_by_type[self.types[e]].append((x - self.median[e]) / self.scale[e])
        for t, zs in z_by_type.items():
            z = np.vstack(zs)
            # contamination="auto": anomalous when score > 0.5 (Liu et al., 2008)
            self.forests[t] = IsolationForest(n_estimators=100, random_state=0).fit(z)
        self.warmup.clear()

    # ---- detection -------------------------------------------------------

    def _candidates(self, samples: list[TelemetrySample]) -> dict[str, Anomaly]:
        out: dict[str, Anomaly] = {}
        to_vote: dict[str, list[tuple[TelemetrySample, np.ndarray]]] = defaultdict(list)
        for s in samples:
            if s.entity_id not in self.median:
                continue
            if s.entity_type != "node" and s.latency_ms is None:
                out[s.entity_id] = Anomaly(
                    ts=s.ts, entity_id=s.entity_id, metric="reachability", value=0.0,
                    baseline=1.0, score=1.0, detectors=["reachability"], severity="critical",
                )  # fmt: skip
                continue
            x = np.array([getattr(s, m) for m in METRICS[s.entity_type]], dtype=float)
            z = (x - self.median[s.entity_id]) / self.scale[s.entity_id]
            if z.max() > Z_THRESHOLD:
                to_vote[s.entity_type].append((s, z))

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
        return out
