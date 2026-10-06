"""Where training runs are tracked: data/mlflow (SQLite + artifacts), out of the repo root."""

from pathlib import Path

import mlflow

DIR = Path(__file__).resolve().parents[1] / "data" / "mlflow"
URI = f"sqlite:///{DIR / 'mlflow.db'}"


def experiment(name: str) -> None:
    """Log the following runs to this experiment."""
    DIR.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(URI)
    if mlflow.get_experiment_by_name(name) is None:
        mlflow.create_experiment(name, artifact_location=(DIR / "mlruns" / name).as_uri())
    mlflow.set_experiment(name)
