"""Redpanda (Kafka API) event bus shared by the engine, sink and stream services."""

import os

# Envelope type -> topic (see docs/CONTRACTS.md). Each message value is the full envelope JSON.
TOPICS = {
    "telemetry": "telemetry.raw",
    "anomaly": "anomalies",
    "rca": "rca.hypotheses",
    "action": "actions",
    "incident": "incidents",
}

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP")  # unset = run without the bus (local dev, tests)
