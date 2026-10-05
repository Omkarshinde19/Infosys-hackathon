import asyncio

from services.stream import main


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def set(self, key, value):
        self.data[key] = value.encode()

    async def get(self, key):
        return self.data.get(key)


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(text)


def test_messages_fan_out_and_full_state_is_cached(monkeypatch):
    fake, ws = FakeRedis(), FakeWS()
    monkeypatch.setattr(main, "cache", fake)
    monkeypatch.setattr(main, "clients", {ws})

    asyncio.run(main.on_message("telemetry.raw", '{"type":"telemetry","data":[]}'))
    asyncio.run(main.on_message("anomalies", '{"type":"anomaly","data":{}}'))
    asyncio.run(main.on_message("incidents", '{"type":"incident","data":{}}'))

    assert len(ws.sent) == 3  # everything reaches the browser
    assert set(fake.data) == {"last:telemetry", "last:incident"}  # deltas aren't cached


def test_broken_client_is_dropped(monkeypatch):
    class BrokenWS:
        async def send_text(self, text):
            raise ConnectionError

    broken = BrokenWS()
    clients = {broken}
    monkeypatch.setattr(main, "cache", FakeRedis())
    monkeypatch.setattr(main, "clients", clients)
    asyncio.run(main.on_message("anomalies", "{}"))
    assert broken not in clients
