"""SLA-breach forecaster: warns that a flow is about to breach its SLA, before it does.

For every flow, the last WINDOW ticks of latency (relative to its healthy baseline) and
packet loss become trend features; a gradient-boosted classifier predicts whether the flow
will breach its SLA within the next HORIZON ticks. The threshold is calibrated on healthy
traffic so it doesn't raise false warnings.
"""

from collections import defaultdict, deque
from pathlib import Path

import joblib
import numpy as np

MODEL_PATH = Path(__file__).parent / "models" / "forecaster.joblib"
WINDOW = 10  # 5 s of history
HORIZON = 10  # predict 5 s ahead
SLA_LOSS_PCT = 2.0
SLA_LATENCY_RATIO = 2.0  # latency more than double its healthy value
UNREACHABLE_RATIO = 20.0
FEATURE_NAMES = [
    "latency_ratio", "loss_pct", "latency_change_2.5s", "loss_change_2.5s", "latency_change_5s",
    "loss_change_5s", "mean_latency_ratio", "mean_loss_pct", "max_loss_pct", "latency_ratio_std",
]  # fmt: skip


def breached(latency_ms: float | None, loss_pct: float, baseline_ms: float) -> bool:
    return (
        latency_ms is None
        or loss_pct > SLA_LOSS_PCT
        or latency_ms > SLA_LATENCY_RATIO * baseline_ms
    )


def flow_features(history, baseline_ms: float) -> np.ndarray | None:
    """history: [(latency_ms | None, loss_pct), ...] oldest first; needs WINDOW + 1 points."""
    if len(history) < WINDOW + 1:
        return None
    window = list(history)[-(WINDOW + 1) :]
    r = np.array([UNREACHABLE_RATIO if lat is None else min(lat / baseline_ms, UNREACHABLE_RATIO)
                  for lat, _ in window])  # fmt: skip
    loss = np.array([lo for _, lo in window])
    return np.array([
        r[-1], loss[-1], r[-1] - r[-6], loss[-1] - loss[-6], r[-1] - r[0], loss[-1] - loss[0],
        r.mean(), loss.mean(), loss.max(), r.std(),
    ])  # fmt: skip


class Forecaster:
    def __init__(self, model, threshold: float):
        self.model, self.threshold = model, threshold
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW + 1))

    def update(self, samples, baseline: dict[str, float]) -> dict[str, float]:
        """Feed one tick. Returns {flow: probability} for flows predicted to breach soon."""
        rows, flows = [], []
        for s in samples:
            if s.entity_type != "flow":
                continue
            self.history[s.entity_id].append((s.latency_ms, s.loss_pct))
            if s.entity_id not in baseline:
                continue  # still learning the baseline: keep history, don't predict
            if breached(s.latency_ms, s.loss_pct, baseline[s.entity_id]):
                continue  # already breaching: that's the detector's job, not a forecast
            x = flow_features(self.history[s.entity_id], baseline[s.entity_id])
            if x is not None:
                rows.append(x)
                flows.append(s.entity_id)
        if not rows:
            return {}
        probs = self.model.predict_proba(np.vstack(rows))[:, 1]
        return {f: float(p) for f, p in zip(flows, probs, strict=True) if p >= self.threshold}


def load(path: Path = MODEL_PATH) -> Forecaster | None:
    if not path.exists():
        return None
    saved = joblib.load(path)
    return Forecaster(saved["model"], saved["threshold"])
