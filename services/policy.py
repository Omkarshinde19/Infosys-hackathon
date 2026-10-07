"""Healing guardrails written in OPA Rego (config/healing.rego), evaluated in-process
with regopy (a Rego interpreter), so no policy server is needed for the demo or tests."""

import json
import math
from pathlib import Path

from regopy import Interpreter

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "healing.rego"


class Policy:
    def __init__(self, path: Path = POLICY_PATH):
        self.source = path.read_text(encoding="utf-8")

    def evaluate(self, data: dict) -> list[str]:
        """Reasons the fix is denied; an empty list means it is allowed."""
        try:
            action, prediction = data["action"], data["prediction"]
            if action["type"] not in {"reroute", "drain_node", "rollback_config"}:
                return ["Unsupported action capability"]
            moved = action["flows_moved"]
            if (
                not isinstance(moved, list)
                or not moved
                or any(not isinstance(f, str) for f in moved)
            ):
                return ["Invalid or missing moved-flow scope"]
            required = [prediction[k] for k in ("loss_pct", "max_util", "other_loss_pct")]
            required += [
                prediction[k] for k in ("max_loss_pct", "other_latency_ratio") if k in prediction
            ]
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                for value in required
            ):
                return ["Invalid or missing safety prediction"]
            count = data["actions_last_minute"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                return ["Invalid action-rate accounting"]
            rego = Interpreter()
            rego.add_module("healing", self.source)
            rego.set_input(data)
            result = json.loads(str(rego.query("data.netheal.healing")))
            decision = result["expressions"][0]
            reasons = sorted(decision.get("deny", []))
            if not reasons and decision.get("allow") is not True:
                return ["Safety policy did not explicitly allow the action"]
            return reasons
        except Exception as error:
            return [f"Safety policy unavailable or input invalid: {type(error).__name__}: {error}"]
