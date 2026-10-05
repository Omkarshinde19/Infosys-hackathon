"""Train the SLA-breach forecaster, calibrate it on healthy traffic, explain it with SHAP.

Run: python -m ml.train_forecast   (needs data/scenarios.pt from ml.train_gnn; logs to MLflow)
"""

import json

import joblib
import matplotlib
import mlflow
import numpy as np
import shap
from sklearn.ensemble import HistGradientBoostingClassifier

from ml.train_gnn import load_scenarios, split
from services.ml.forecast import (
    FEATURE_NAMES,
    HORIZON,
    MODEL_PATH,
    WINDOW,
    breached,
    flow_features,
)  # fmt: skip

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

EVAL_PATH = MODEL_PATH.with_name("forecast_eval.json")
SHAP_PLOT = MODEL_PATH.with_name("forecast_shap.png")
MARGIN = 1.1  # threshold = highest healthy-traffic probability x margin
TICK_S = 0.5


def examples(scenario: dict):
    """(features, will_breach_within_horizon, is_healthy_context) for every flow and tick."""
    onset = scenario["onset"] if scenario["fault"] else len(next(iter(scenario["series"].values())))
    for flow, series in scenario["series"].items():
        base = scenario["baseline"][flow]
        bad = [breached(lat, loss, base) for lat, loss in series]
        for t in range(WINDOW, len(series) - HORIZON):
            if bad[t]:
                continue
            x = flow_features(series[: t + 1], base)
            yield x, any(bad[t + 1 : t + 1 + HORIZON]), t < onset


def dataset(scenarios: list[dict]):
    rows = [r for s in scenarios for r in examples(s)]
    return (np.array([r[0] for r in rows]), np.array([r[1] for r in rows]),
            np.array([r[2] for r in rows]))  # fmt: skip


def warns(model, threshold: float, series, baseline: float, t: int) -> bool:
    return model.predict_proba([flow_features(series[: t + 1], baseline)])[0, 1] >= threshold


def lead_times(model, threshold: float, scenarios: list[dict]) -> list[float | None]:
    """For gradual faults: seconds between the first warning and the actual SLA breach."""
    leads = []
    for s in scenarios:
        if (
            not s["fault"]
            or s["fault"][3] < 10
            or s["fault"][0] not in ("gray_failure", "congestion", "node_overload")
        ):
            continue
        for flow, series in s["series"].items():
            base = s["baseline"][flow]
            bad = [breached(lat, loss, base) for lat, loss in series]
            breach = next((t for t in range(s["onset"], len(series)) if bad[t]), None)
            if breach is None:
                continue

            warn = next(
                (t for t in range(WINDOW, breach) if warns(model, threshold, series, base, t)), None
            )
            leads.append(None if warn is None else (breach - warn) * TICK_S)
    return leads


def main() -> None:
    data = load_scenarios()
    parts = {k: [d for d in data if split(d["seed"]) == k] for k in ("train", "val", "test")}
    x_train, y_train, _ = dataset(parts["train"])
    x_val, y_val, healthy_val = dataset(parts["val"])

    mlflow.set_experiment("netheal-forecaster")
    with mlflow.start_run(run_name="hgb-sla-breach-5s"):
        model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=0)
        model.fit(x_train, y_train)
        val_probs = model.predict_proba(x_val)[:, 1]
        threshold = float(min(0.95, val_probs[healthy_val].max() * MARGIN))

        leads = lead_times(model, threshold, parts["test"])
        warned = [lead for lead in leads if lead is not None and lead > 0]
        x_test, y_test, healthy_test = dataset(parts["test"])
        test_probs = model.predict_proba(x_test)[:, 1]
        results = {
            "threshold": threshold,
            "train_examples": int(len(y_train)),
            "test_healthy_false_warnings": int((test_probs[healthy_test] >= threshold).sum()),
            "test_healthy_examples": int(healthy_test.sum()),
            "gradual_breaches": len(leads),
            "warned_before_breach": len(warned),
            "warned_before_breach_pct": len(warned) / len(leads) if leads else None,
            "median_lead_time_s": float(np.median(warned)) if warned else None,
            "precision_at_threshold": float(y_test[test_probs >= threshold].mean()),
            "recall_at_threshold": float((test_probs[y_test] >= threshold).mean()),
        }

        explainer = shap.TreeExplainer(model)
        positives = x_test[test_probs >= threshold][:500]
        values = np.abs(explainer.shap_values(positives)).mean(axis=0)
        importance = dict(sorted(zip(FEATURE_NAMES, values.round(4).tolist(), strict=True),
                                 key=lambda kv: kv[1], reverse=True))  # fmt: skip
        results["shap_mean_abs"] = importance
        plt.figure(figsize=(7, 4))
        plt.barh(list(importance)[::-1], list(importance.values())[::-1], color="#5483b3")
        plt.xlabel("mean |SHAP value| (impact on the breach prediction)")
        plt.title("What drives NetHeal's early warnings")
        plt.tight_layout()
        plt.savefig(SHAP_PLOT, dpi=120)

        joblib.dump({"model": model, "threshold": threshold}, MODEL_PATH)
        EVAL_PATH.write_text(json.dumps(results, indent=2))
        mlflow.log_params({"window_ticks": WINDOW, "horizon_ticks": HORIZON, "max_iter": 200,
                           "threshold_margin": MARGIN})  # fmt: skip
        mlflow.log_metrics({k: v for k, v in results.items() if isinstance(v, (int, float))})
        for path in (MODEL_PATH, EVAL_PATH, SHAP_PLOT):
            mlflow.log_artifact(str(path))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
