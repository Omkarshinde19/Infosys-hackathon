"""Train the root-cause GNN on simulator scenarios and compare it with the rules and 007.

Run: python -m ml.train_gnn   (logs to MLflow in ./mlruns, saves services/ml/models/rca_gnn.pt)
"""

import json
import time
from pathlib import Path

import mlflow
import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from ml.datagen import generate
from services.ml.gnn import MODEL_PATH, RootCauseGNN, ensemble, probabilities, top
from services.ml.graph import CAUSES

SCENARIOS = 3000
EPOCHS = 40
LR = 5e-3
NONE_WEIGHT = 0.05  # most vertices are "none": down-weight them
CACHE = Path("data/scenarios.pt")
EVAL_PATH = MODEL_PATH.with_name("rca_eval.json")


def split(seed: int) -> str:
    return "train" if seed % 10 < 7 else "val" if seed % 10 == 7 else "test"


def load_scenarios() -> list[dict]:
    if CACHE.exists():
        return torch.load(CACHE, weights_only=False)
    data = generate(list(range(SCENARIOS)))
    CACHE.parent.mkdir(exist_ok=True)
    torch.save(data, CACHE)
    return data


def truth(snap: dict) -> tuple[str, str]:
    return CAUSES[int(snap["y"].max())], snap["ids"][int(snap["y"].argmax())]


def accuracy(model, snaps: list[dict]) -> dict:
    """Top-1 (cause, target) accuracy for the rules, GNN and ensemble; target-only for 007."""
    hits = {"rules": 0, "gnn": 0, "ensemble": 0, "voting_007_target": 0}
    for s in snaps:
        want = truth(s)
        probs = probabilities(model, s["x"], s["edge_index"], s["kinds"])
        hits["rules"] += bool(s["rules"]) and tuple(s["rules"][0][:2]) == want
        hits["gnn"] += top(probs, s["ids"])[:2] == want
        hits["ensemble"] += ensemble(s["rules"], probs, s["ids"])[0][:2] == want
        hits["voting_007_target"] += s["voting_target"] == want[1]
    return {k: v / len(snaps) for k, v in hits.items()}


def main() -> None:
    torch.manual_seed(0)
    t0 = time.time()
    data = load_scenarios()
    snaps = {
        k: [s for d in data if split(d["seed"]) == k for s in d["rca"]]
        for k in ("train", "val", "test")
    }
    loader = DataLoader(
        [
            Data(x=s["x"], edge_index=s["edge_index"], y=torch.from_numpy(s["y"]))
            for s in snaps["train"]
        ],
        batch_size=64,
        shuffle=True,
    )
    model = RootCauseGNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    weight = torch.ones(len(CAUSES))
    weight[0] = NONE_WEIGHT
    loss_fn = torch.nn.CrossEntropyLoss(weight=weight)

    mlflow.set_experiment("netheal-rca-gnn")
    with mlflow.start_run(run_name="graphsage-3x64"):
        mlflow.log_params({
            "scenarios": len(data), "train_snapshots": len(snaps["train"]), "epochs": EPOCHS,
            "lr": LR, "hidden": 64, "layers": 3, "none_weight": NONE_WEIGHT,
            "datagen_seconds": round(time.time() - t0, 1),
        })  # fmt: skip
        for epoch in range(EPOCHS):
            model.train()
            total = 0.0
            for batch in loader:
                optimizer.zero_grad()
                loss = loss_fn(model(batch.x, batch.edge_index), batch.y)
                loss.backward()
                optimizer.step()
                total += float(loss) * batch.num_graphs
            model.eval()
            val = accuracy(model, snaps["val"])
            mlflow.log_metrics({"train_loss": total / len(snaps["train"]), "val_gnn": val["gnn"],
                                "val_ensemble": val["ensemble"]}, step=epoch)  # fmt: skip
            print(
                f"epoch {epoch:2d} loss {total / len(snaps['train']):.4f} val gnn {val['gnn']:.3f}"
            )

        results = {
            "all_snapshots": accuracy(model, snaps["test"]),
            "first_diagnosis": accuracy(model, [s for s in snaps["test"] if s["offset"] == 0]),
            "test_snapshots": len(snaps["test"]),
        }
        per_cause = {}
        for cause in CAUSES[1:]:
            subset = [s for s in snaps["test"] if truth(s)[0] == cause]
            per_cause[cause] = accuracy(model, subset) if subset else None
        results["per_cause"] = per_cause
        for scope in ("all_snapshots", "first_diagnosis"):
            mlflow.log_metrics({f"test_{scope}_{k}": v for k, v in results[scope].items()})

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), MODEL_PATH)
        EVAL_PATH.write_text(json.dumps(results, indent=2))
        mlflow.log_artifact(str(MODEL_PATH))
        mlflow.log_artifact(str(EVAL_PATH))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
