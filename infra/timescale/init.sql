-- NetHeal history store. Runs once when the TimescaleDB container is first created.
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE telemetry (
    ts              TIMESTAMPTZ NOT NULL,
    entity_type     TEXT        NOT NULL,
    entity_id       TEXT        NOT NULL,
    latency_ms      DOUBLE PRECISION,
    loss_pct        DOUBLE PRECISION,
    throughput_mbps DOUBLE PRECISION,
    util            DOUBLE PRECISION,
    cpu             DOUBLE PRECISION,
    queue_len       DOUBLE PRECISION
);
SELECT create_hypertable('telemetry', by_range('ts'));
CREATE INDEX ON telemetry (entity_id, ts DESC);

CREATE TABLE anomalies (
    id        TEXT PRIMARY KEY,
    ts        TIMESTAMPTZ NOT NULL,
    entity_id TEXT NOT NULL,
    metric    TEXT NOT NULL,
    value     DOUBLE PRECISION,
    baseline  DOUBLE PRECISION,
    score     DOUBLE PRECISION,
    severity  TEXT,
    detectors TEXT[]
);

CREATE TABLE incidents (
    id         TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    opened_at  TIMESTAMPTZ NOT NULL,
    closed_at  TIMESTAMPTZ,
    mttd_s     DOUBLE PRECISION,
    mttr_s     DOUBLE PRECISION,
    data       JSONB NOT NULL  -- full Incident incl. timeline
);

-- Diagnoses and healing actions, kept as an append-only log.
CREATE TABLE events (
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    topic       TEXT NOT NULL,
    data        JSONB NOT NULL
);
