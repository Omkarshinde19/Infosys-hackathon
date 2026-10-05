"""Train the LSTM autoencoder on healthy z-score sequences and calibrate its threshold.

Run: python -m ml.train_lstm_ae   (logs to MLflow, saves services/ml/models/lstm_ae.pt)
"""

import copy
import json

import mlflow
import numpy as np
import torch

from ml.datagen import BASE_SEEDS, base
from services.detector.detector import METRICS
from services.ml.lstm_ae import MODEL_PATH, SEQ, LSTMAutoencoder, errors, pad

HEALTHY_TICKS = 1500  # per base network (12.5 min)
STRIDE = 5
EPOCHS = 15
MARGIN = 1.5  # threshold = 99.9th percentile of healthy validation error x margin
EVAL_PATH = MODEL_PATH.with_name("lstm_ae_eval.json")
FAULTS = [("gray_failure", "dist1-library", 0.4), ("congestion", "dist3-lab_cs", 0.6),
          ("node_overload", "dist2", 0.6), ("gray_failure", "core1-dist3", 0.4)]  # fmt: skip


def z_vectors(det, samples) -> dict[str, np.ndarray]:
    out = {}
    for s in samples:
        if s.entity_type != "node" and s.latency_ms is None:
            out[s.entity_id] = pad(np.full(len(METRICS[s.entity_type]), 50.0))
            continue
        x = np.array([getattr(s, m) for m in METRICS[s.entity_type]], dtype=float)
        out[s.entity_id] = pad((x - det.median[s.entity_id]) / det.scale[s.entity_id])
    return out


def windows(series: dict[str, list]) -> np.ndarray:
    return np.stack([np.stack(seq[i : i + SEQ]) for seq in series.values()
                     for i in range(0, len(seq) - SEQ + 1, STRIDE)])  # fmt: skip


def healthy_windows(seed: int, ticks: int) -> np.ndarray:
    net, det, _ = (copy.deepcopy(x) for x in base(seed))
    series: dict[str, list] = {}
    for _ in range(ticks):
        for e, z in z_vectors(det, net.step()).items():
            series.setdefault(e, []).append(z)
    return windows(series)


def fault_windows(seed: int) -> np.ndarray:
    """Windows of the faulty entity once the fault has been active for a while."""
    out = []
    for fault, target, severity in FAULTS:
        net, det, _ = (copy.deepcopy(x) for x in base(seed))
        net.inject_fault(fault, target, severity=severity)
        seq = [z_vectors(det, net.step())[target] for _ in range(SEQ + 10)]
        out += [np.stack(seq[i : i + SEQ]) for i in range(5, 11)]
    return np.stack(out)


def main() -> None:
    torch.manual_seed(0)
    train = np.concatenate([healthy_windows(s, HEALTHY_TICKS) for s in BASE_SEEDS[:3]])
    val = healthy_windows(BASE_SEEDS[3], HEALTHY_TICKS)
    model = LSTMAutoencoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    loader = torch.utils.data.DataLoader(torch.from_numpy(train), batch_size=256, shuffle=True)

    mlflow.set_experiment("netheal-lstm-autoencoder")
    with mlflow.start_run(run_name="lstm-ae-16"):
        mlflow.log_params({"seq_ticks": SEQ, "hidden": 16, "epochs": EPOCHS,
                           "train_windows": len(train), "threshold_margin": MARGIN})  # fmt: skip
        for epoch in range(EPOCHS):
            total = 0.0
            for batch in loader:
                optimizer.zero_grad()
                loss = ((model(batch) - batch) ** 2).mean()
                loss.backward()
                optimizer.step()
                total += float(loss) * len(batch)
            mlflow.log_metric("train_mse", total / len(train), step=epoch)
            print(f"epoch {epoch:2d} mse {total / len(train):.5f}")

        model.eval()
        val_err = errors(model, val)
        threshold = float(np.percentile(val_err, 99.9) * MARGIN)
        fault_err = errors(model, fault_windows(BASE_SEEDS[3]))
        results = {
            "threshold": threshold,
            "healthy_false_positive_rate": float((val_err > threshold).mean()),
            "fault_detection_rate": float((fault_err > threshold).mean()),
            "healthy_error_median": float(np.median(val_err)),
            "fault_error_median": float(np.median(fault_err)),
        }
        torch.save({"state": model.state_dict(), "threshold": threshold}, MODEL_PATH)
        EVAL_PATH.write_text(json.dumps(results, indent=2))
        mlflow.log_metrics(results)
        mlflow.log_artifact(str(MODEL_PATH))
        mlflow.log_artifact(str(EVAL_PATH))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
