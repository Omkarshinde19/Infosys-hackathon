from services.storage import Journal


def test_journal_is_durable_and_deduplicates_control_events(tmp_path):
    path = tmp_path / "state.sqlite3"
    event = {"event_id": "one", "sequence": 3, "type": "action", "data": {"kind": "applied"}}
    journal = Journal(path)
    journal.append(event)
    journal.append(event)
    journal.save({"schema": 1, "incident": "pending"})
    journal.close()
    restored = Journal(path)
    assert restored.load() == {"schema": 1, "incident": "pending"}
    assert restored.pending() == [event]
    restored.delivered("one")
    restored.close()
    restored = Journal(path)
    assert restored.pending() == []
    restored.close()


def test_event_and_history_checkpoint_roll_back_together_on_invalid_data(tmp_path):
    import pytest

    journal = Journal(tmp_path / "state.sqlite3")
    event = {"event_id": "invalid", "sequence": 1, "type": "audit", "data": {}}
    with pytest.raises(ValueError):
        journal.append(event, {"invalid_number": float("nan")})
    assert journal.pending() == [] and journal.load() is None
    journal.append(event, {"sequence": 1})
    journal.close()
    restored = Journal(tmp_path / "state.sqlite3")
    assert restored.pending() == [event] and restored.load() == {"sequence": 1}
    restored.close()
