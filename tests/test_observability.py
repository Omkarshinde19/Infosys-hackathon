import asyncio

from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from services import observability
from services.gateway import main
from services.stream import main as stream

STAGES = ("simulate", "detect", "diagnose", "heal")


def test_engine_exposes_loop_metrics():
    with TestClient(main.app) as client:
        asyncio.run(main.tick())
        body = client.get("/metrics").text
    for s in STAGES:
        assert f'netheal_stage_seconds_count{{stage="{s}"}}' in body
    assert "netheal_active_anomalies" in body
    assert "netheal_ws_clients" in body


def test_stream_exposes_metrics():
    client = TestClient(stream.app)  # no lifespan: no Redpanda or Redis needed
    assert "netheal_bus_messages_total" in client.get("/metrics").text


def test_tracing_is_off_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert observability.setup_tracing("engine") is False


def test_one_trace_per_tick_with_a_span_per_stage():
    exporter = InMemorySpanExporter()
    assert observability.setup_tracing("engine", exporter=exporter)
    asyncio.run(main.tick())
    trace.get_tracer_provider().force_flush()
    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert set(STAGES) | {"tick"} <= spans.keys()
    root = spans["tick"]
    assert all(spans[s].parent.span_id == root.context.span_id for s in STAGES)
    assert len({s.context.trace_id for s in spans.values()}) == 1
