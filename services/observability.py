"""Self-observability: Prometheus metrics and OpenTelemetry traces for NetHeal's own services.

Metrics are always on (GET /metrics on the engine and stream, :9464 on the sink).
Traces are exported only when OTEL_EXPORTER_OTLP_ENDPOINT is set: `./netheal obs` starts
Jaeger, Prometheus and Grafana and sets it. The aiokafka instrumentation propagates
broker-operation context in message headers. Archive publication runs in a separate
task; originating tick context is not restored from the durable event envelope.
"""

import os
from contextlib import contextmanager

from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram

tracer = trace.get_tracer("netheal")

# engine
STAGE_SECONDS = Histogram(
    "netheal_stage_seconds", "Time per loop stage", ["stage"],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
)  # fmt: skip
ANOMALIES_RAISED = Counter("netheal_anomalies_raised_total", "Anomalies raised", ["severity"])
ACTIVE_ANOMALIES = Gauge("netheal_active_anomalies", "Anomalies active right now")
HEALING_EVENTS = Counter("netheal_healing_events_total", "Healing events", ["kind"])
INCIDENTS = Counter("netheal_incidents_total", "Closed incidents", ["status"])
MTTD = Histogram("netheal_mttd_seconds", "Fault to detection", buckets=(0.5, 1, 2, 3, 5, 10, 20))
MTTR = Histogram(
    "netheal_mttr_seconds", "Fault to verified fix", buckets=(2, 4, 6, 8, 10, 15, 20, 30, 60)
)
COPILOT_SECONDS = Histogram(
    "netheal_copilot_seconds", "Ask NetHeal answer time", buckets=(1, 2, 5, 10, 20, 30, 60)
)
WS_CLIENTS = Gauge("netheal_ws_clients", "Browsers connected over WebSocket", ["service"])
# stream + sink
MESSAGES = Counter("netheal_bus_messages_total", "Bus messages handled", ["service", "topic"])
BUS_ERRORS = Counter("netheal_bus_errors_total", "Failed event archive deliveries")
TICK_SECONDS = Histogram(
    "netheal_tick_seconds",
    "Complete controller tick duration",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
TICK_OVERRUNS = Counter("netheal_tick_overruns_total", "Ticks exceeding the sampling interval")
LAST_SAMPLE_UNIX = Gauge("netheal_last_sample_unixtime", "Receipt time of last complete telemetry")


@contextmanager
def stage(name: str):
    """A traced and timed stage of the engine loop."""
    with tracer.start_as_current_span(name), STAGE_SECONDS.labels(name).time():
        yield


def setup_tracing(service: str, app=None, exporter=None) -> bool:
    """Export traces for this service if an OTLP endpoint (or a test exporter) is given."""
    if exporter is None and not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    if exporter is None:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": f"netheal-{service}"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    AIOKafkaInstrumentor().instrument()
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics,health")
    return True
