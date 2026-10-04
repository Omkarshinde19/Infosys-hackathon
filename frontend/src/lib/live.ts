"use client";

import { useEffect } from "react";
import { create } from "zustand";

// Mirrors contracts/models.py (TelemetrySample) and the gateway's /topology response.
export type Sample = {
  ts: string;
  entity_type: "link" | "node" | "flow";
  entity_id: string;
  latency_ms: number | null;
  loss_pct: number | null;
  throughput_mbps: number | null;
  util: number | null;
  cpu: number | null;
  queue_len: number | null;
};

export type Topology = {
  nodes: { id: string; layer: "edge" | "core" | "distribution" | "access"; name: string }[];
  links: { id: string; a: string; b: string; capacity_mbps: number; base_latency_ms: number }[];
  flows: { id: string; src: string; dst: string; demand_mbps: number; route: string[] }[];
};

// Mirrors contracts/models.py (Anomaly).
export type Anomaly = {
  id: string;
  ts: string;
  entity_id: string;
  metric: string;
  value: number;
  baseline: number;
  score: number;
  detectors: string[];
  severity: "warning" | "critical";
};

// Mirrors contracts/models.py (RCAHypothesis).
export type Hypothesis = {
  id: string;
  incident_id: string;
  cause: "link_failure" | "gray_failure" | "congestion" | "node_overload" | "misconfig" | "flapping";
  target: string;
  confidence: number;
  evidence: { anomaly_id: string | null; description: string; weight: number }[];
  method_scores: Record<string, number>;
};

// Mirrors contracts/models.py (ActionCandidate, ActionResult, Incident) + GET /incident.
export type ActionCandidate = {
  id: string;
  type: string;
  params: { avoid?: string[]; routes?: Record<string, string[]>; flow?: string };
  twin_prediction: { latency_ms: number; loss_pct: number; max_util: number } | null;
  opa_decision: "allow" | "deny" | null;
  risk_score: number;
};
export type ActionResult = {
  action_id: string;
  verified: boolean;
  rolled_back: boolean;
  before: Record<string, number>;
  after: Record<string, number>;
};
export type ActionEvent =
  | { kind: "proposed"; payload: ActionCandidate[] }
  | { kind: "applied"; payload: ActionCandidate }
  | { kind: "result"; payload: ActionResult }
  | { kind: "no_action" | "escalated"; payload: string };
export type Incident = {
  id: string;
  status: string;
  opened_at: string;
  mttd_s: number | null;
  mttr_s: number | null;
  timeline: { ts: string; stage: string; ref_id: string | null }[];
};
export type IncidentState = { incident: Incident | null; healer_status: string; actions: ActionEvent[] };

export type AlertEvent = { time: string; kind: "raised" | "cleared"; entity: string; anomaly?: Anomaly };

const HISTORY = 120; // ticks kept for charts (60 s at 2 ticks/s)
const WS_URL = process.env.NEXT_PUBLIC_GATEWAY_WS ?? "ws://localhost:8000/ws/live";

type LiveState = {
  connected: boolean;
  topology: Topology | null;
  latest: Record<string, Sample>;
  history: Sample[][];
  anomalies: Record<string, Anomaly>;
  alertLog: AlertEvent[];
  detector: { ready: boolean; progress: number };
  diagnosis: Hypothesis[];
  incident: IncidentState;
  loadTopology: () => Promise<void>;
  loadAnomalies: () => Promise<void>;
};

export const useLive = create<LiveState>((set) => ({
  connected: false,
  topology: null,
  latest: {},
  history: [],
  anomalies: {},
  alertLog: [],
  detector: { ready: false, progress: 0 },
  diagnosis: [],
  incident: { incident: null, healer_status: "idle", actions: [] },
  loadTopology: async () => set({ topology: await (await fetch("/api/topology")).json() }),
  loadAnomalies: async () => {
    const body = await (await fetch("/api/anomalies")).json();
    set({
      detector: { ready: body.ready, progress: body.warmup_progress },
      anomalies: Object.fromEntries(body.active.map((a: Anomaly) => [a.entity_id, a])),
      diagnosis: await (await fetch("/api/rca")).json(),
      incident: await (await fetch("/api/incident")).json(),
    });
  },
}));

function onAnomalyEvent({ raised, cleared }: { raised: Anomaly[]; cleared: string[] }) {
  const time = new Date().toLocaleTimeString();
  useLive.setState((s) => {
    const anomalies = { ...s.anomalies };
    raised.forEach((a) => (anomalies[a.entity_id] = a));
    cleared.forEach((e) => delete anomalies[e]);
    const events: AlertEvent[] = [
      ...raised.map((a) => ({ time, kind: "raised" as const, entity: a.entity_id, anomaly: a })),
      ...cleared.map((e) => ({ time, kind: "cleared" as const, entity: e })),
    ];
    return { anomalies, alertLog: [...events, ...s.alertLog].slice(0, 30) };
  });
}

/** Opens the gateway WebSocket once and keeps it reconnecting. */
export function useLiveConnection() {
  useEffect(() => {
    let ws: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    let closed = false;

    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        useLive.setState({ connected: true });
        useLive.getState().loadTopology();
        useLive.getState().loadAnomalies();
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "anomaly") return onAnomalyEvent(msg.data);
        if (msg.type === "rca") return useLive.setState({ diagnosis: msg.data });
        if (msg.type === "incident") return useLive.setState({ incident: msg.data });
        if (msg.type !== "telemetry") return;
        const tick: Sample[] = msg.data;
        useLive.setState((s) => ({
          latest: Object.fromEntries(tick.map((x) => [x.entity_id, x])),
          history: [...s.history.slice(-(HISTORY - 1)), tick],
        }));
      };
      ws.onclose = () => {
        useLive.setState({ connected: false });
        if (!closed) retry = setTimeout(connect, 1000);
      };
    }

    connect();
    // While the detector is still learning its baseline, poll its progress.
    const warmup = setInterval(() => {
      if (useLive.getState().connected && !useLive.getState().detector.ready) {
        useLive.getState().loadAnomalies();
      }
    }, 2000);
    return () => {
      closed = true;
      clearInterval(warmup);
      clearTimeout(retry);
      ws.close();
    };
  }, []);
}

export async function postJSON(path: string, body?: unknown) {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}
