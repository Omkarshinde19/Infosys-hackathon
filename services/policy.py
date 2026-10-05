"""Healing guardrails written in OPA Rego (policies/healing.rego), evaluated in-process
with regopy (a Rego interpreter), so no policy server is needed for the demo or tests."""

import json
from pathlib import Path

from regopy import Interpreter

POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "healing.rego"


class Policy:
    def __init__(self, path: Path = POLICY_PATH):
        self.source = path.read_text()

    def evaluate(self, data: dict) -> list[str]:
        """Reasons the fix is denied; an empty list means it is allowed."""
        rego = Interpreter()
        rego.add_module("healing", self.source)
        rego.set_input(data)
        result = json.loads(str(rego.query("data.netheal.healing")))
        return sorted(result["expressions"][0].get("deny", []))
