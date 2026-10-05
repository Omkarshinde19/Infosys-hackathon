from datetime import UTC, datetime

from services.ledger.ledger import Ledger

NOW = datetime(2026, 10, 7, 10, 42, tzinfo=UTC)


def ledger_with(n: int) -> Ledger:
    ledger = Ledger()
    for i in range(n):
        ledger.append(NOW, "system", "action.applied", {"action": i, "who": "healer"})
    return ledger


def test_untouched_chain_verifies():
    assert ledger_with(5).verify() == {"valid": True, "broken_at": None, "entries": 5}


def test_editing_a_past_payload_is_detected():
    ledger = ledger_with(5)
    ledger.entries[2].payload["who"] = "attacker"  # rewrite history
    assert ledger.verify()["broken_at"] == 3


def test_recomputing_the_edited_entry_hash_still_breaks_the_next_link():
    from services.ledger.ledger import _entry_hash, _payload_hash

    ledger = ledger_with(5)
    e = ledger.entries[1]
    e.payload["who"] = "attacker"
    e.payload_hash = _payload_hash(e.payload)
    e.hash = _entry_hash(e)  # a careful attacker fixes this entry...
    assert ledger.verify()["broken_at"] == 3  # ...but entry 3 still points at the old hash


def test_deleting_an_entry_is_detected():
    ledger = ledger_with(5)
    del ledger.entries[1]
    assert not ledger.verify()["valid"]


def test_user_actions_are_marked_as_user():
    ledger = Ledger()
    assert ledger.append(NOW, "omkar", "fault.injected", {}).actor == "user"
