import time

import pytest

from services.policy import Policy

SAFE = {
    "action": {"type": "reroute", "target_layer": "access", "flows_moved": ["library-internet"]},
    "prediction": {"loss_pct": 0.05, "max_util": 0.4, "other_loss_pct": 0.05},
    "actions_last_minute": 0,
}


def with_(**changes):
    data = {k: dict(v) if isinstance(v, dict) else v for k, v in SAFE.items()}
    for key, value in changes.items():
        section, _, field = key.partition("__")
        if field:
            data[section][field] = value
        else:
            data[section] = value
    return data


def test_safe_fix_is_allowed():
    assert Policy().evaluate(SAFE) == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"prediction__loss_pct": 4.0}, "Doesn't restore the traffic"),
        ({"prediction__max_util": 0.92}, "Would push a link to 92% load"),
        ({"prediction__other_loss_pct": 3.0}, "Would hurt other traffic"),
        ({"action__flows_moved": ["f"] * 6}, "Moves 6 flows at once"),
        (
            {"action__type": "drain_node", "action__target_layer": "core"},
            "Never drains a core router",
        ),
        ({"actions_last_minute": 3}, "Rate limit"),
    ],
)
def test_each_guardrail_blocks_with_a_readable_reason(change, reason):
    reasons = Policy().evaluate(with_(**change))
    assert len(reasons) == 1 and reasons[0].startswith(reason)


def test_evaluation_is_fast_enough_for_the_tick_loop():
    policy = Policy()
    start = time.perf_counter()
    for _ in range(20):
        policy.evaluate(SAFE)
    assert (time.perf_counter() - start) / 20 < 0.05  # well under the 500 ms tick
