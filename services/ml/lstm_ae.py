"""LSTM autoencoder: learns what 10 s of *healthy* behaviour looks like for any entity.

Input: the last SEQ ticks of an entity's robust z-scores (padded to DIM metrics). A sequence
the model cannot reconstruct well (error above a threshold calibrated on healthy data) is
unusual over time, not just at one instant. In the detector it acts as a third, temporal
opinion: it is added to an alert's detectors when it agrees.
"""

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import torch
from torch import nn

MODEL_PATH = Path(__file__).parent / "models" / "lstm_ae.pt"
SEQ = 20  # 10 s
DIM = 3  # flow: latency, loss | link: latency, loss, util | node: cpu (zero-padded)
HIDDEN = 16
Z_CLIP = 50.0


class LSTMAutoencoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.LSTM(DIM, HIDDEN, batch_first=True)
        self.decoder = nn.LSTM(HIDDEN, HIDDEN, batch_first=True)
        self.out = nn.Linear(HIDDEN, DIM)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: (batch, SEQ, DIM)
        _, (h, _) = self.encoder(x)
        repeated = h[-1].unsqueeze(1).repeat(1, x.shape[1], 1)
        decoded, _ = self.decoder(repeated)
        return self.out(decoded)


def pad(z: np.ndarray) -> np.ndarray:
    out = np.zeros(DIM, dtype=np.float32)
    out[: len(z)] = np.clip(z, -Z_CLIP, Z_CLIP) / 10
    return out


@torch.no_grad()
def errors(model: LSTMAutoencoder, windows: np.ndarray) -> np.ndarray:
    x = torch.from_numpy(windows)
    return ((model(x) - x) ** 2).mean(dim=(1, 2)).numpy()


class SequenceScorer:
    """Keeps each entity's recent z-scores and scores them with the autoencoder."""

    def __init__(self, model: LSTMAutoencoder, threshold: float):
        self.model, self.threshold = model, threshold
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=SEQ))

    def observe(self, entity: str, z: np.ndarray) -> None:
        self.history[entity].append(pad(z))

    def unusual(self, entities: list[str]) -> set[str]:
        ready = [e for e in entities if len(self.history[e]) == SEQ]
        if not ready:
            return set()
        errs = errors(self.model, np.stack([np.stack(self.history[e]) for e in ready]))
        return {e for e, err in zip(ready, errs, strict=True) if err > self.threshold}


def load(path: Path = MODEL_PATH) -> SequenceScorer | None:
    if not path.exists():
        return None
    saved = torch.load(path, weights_only=True)
    model = LSTMAutoencoder()
    model.load_state_dict(saved["state"])
    return SequenceScorer(model.eval(), float(saved["threshold"]))
