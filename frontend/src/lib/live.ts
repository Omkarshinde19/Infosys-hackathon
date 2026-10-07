"use client";

import { useEffect } from "react";
import { create } from "zustand";
import { authHeader, useAuth } from "./auth";
import { errorMessage, requestJSON } from "./http";

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
  confidence_kind?: "heuristic";
  supported?: boolean;
};

// Mirrors contracts/models.py (ActionCandidate, ActionResult, Incident) + GET /incident.
export type ActionCandidate = {
  id: string;
  type: string;
  params: { avoid?: string[]; routes?: Record<string, string[]>; flow?: string; planner?: "rl" };
  twin_prediction: { latency_ms: number; loss_pct: number; max_util: number; max_loss?: number; other_latency_ratio?: number; per_flow?: Record<string, Record<string, number>> } | null;
  planned_at?: string | null;
  expires_at?: string | null;
  state_fingerprint?: string | null;
  planning_version?: string | null;
  opa_decision: "allow" | "deny" | null;
  policy_reasons: string[];
  risk_score: number;
};
export type ActionResult = {
  action_id: string;
  verified: boolean;
  rolled_back: boolean;
  before: Record<string, number>;
  after: Record<string, number>;
  per_flow_before?: Record<string, Record<string, number | null>>;
  per_flow_after?: Record<string, Record<string, number | null>>;
  rollback_attempted?: boolean;
  rollback_error?: string | null;
  failure_reason?: string | null;
  verification_reasons?: string[];
  outcome?: "verified" | "rolled_back" | "execution_failed" | "rollback_failed";
};
export type ActionEvent =
  | { kind: "proposed"; payload: ActionCandidate[] }
  | { kind: "applied"; payload: ActionCandidate }
  | { kind: "result"; payload: ActionResult }
  | { kind: "recommended" | "awaiting_approval"; payload: ActionCandidate }
  | { kind: "approved" | "rejected"; payload: string }
  | { kind: "no_action" | "alert_only" | "escalated" | "replanning" | "relapsed"; payload: string };
export type Incident = {
  id: string;
  status: string;
  opened_at: string;
  mttd_s: number | null;
  mttr_s: number | null;
  timeline: { ts: string; stage: string; ref_id: string | null }[];
};
export type IncidentState = {
  incident: Incident | null;
  healer_status: string;
  awaiting: ActionCandidate | null;
  actions: ActionEvent[];
};

type AlertEvent = { time: string; kind: "raised" | "cleared"; entity: string; anomaly?: Anomaly };
export type DataStatus = "unknown" | "learning" | "fresh" | "stale";
export type Autonomy = { level: number; levels: Record<string, string> };
type Snapshot = {
  generation: string; sequence: number; topology: Topology; telemetry: Sample[];
  detector: { ready: boolean; progress: number }; anomalies: Anomaly[];
  diagnosis: Hypothesis[]; incident: IncidentState; autonomy: Autonomy; backend: { kind: string };
  observed_at?: string | null; emitted_at?: string; diagnosis_meta?: DiagnosisMeta;
};
export type DiagnosisMeta = { status: string; reason?: string | null; confidence_kind?: string };
type Envelope = { generation: string; sequence: number; type: string; data: unknown; detector?: { ready: boolean; progress: number }; emitted_at?: string; diagnosis_meta?: DiagnosisMeta };
const HISTORY = 120;
const EMPTY_INCIDENT: IncidentState = { incident: null, healer_status: "idle", awaiting: null, actions: [] };
const WS_URL = process.env.NEXT_PUBLIC_GATEWAY_WS ?? "ws://localhost:8000/ws/live";
let snapshotController: AbortController | null = null;
let snapshotRevision = 0;
let buffer: Envelope[] = [];
const retiredGenerations = new Set<string>();
let receiptAt = 0;
let observationAt = 0;

type LiveState = {
  connected: boolean; syncing: boolean; coherent: boolean; error: string; dataStatus: DataStatus;
  generation: string | null; sequence: number; lastSampleAt: string | null; lastObservedAt: string | null; ageSeconds: number | null;
  topology: Topology | null; latest: Record<string, Sample>; history: Sample[][];
  anomalies: Record<string, Anomaly>; alertLog: AlertEvent[];
  detector: { ready: boolean; progress: number }; diagnosis: Hypothesis[]; incident: IncidentState;
  diagnosisMeta: DiagnosisMeta | null;
  autonomy: Autonomy | null; backend: string | null;
  loadSnapshot: () => Promise<void>; loadTopology: () => Promise<void>; loadAnomalies: () => Promise<void>;
};

function quality(connected: boolean, ready: boolean, latest: Record<string, Sample>, syncing: boolean, topology = useLive.getState().topology, coherent = useLive.getState().coherent): DataStatus {
  if (!Object.keys(latest).length) return "unknown";
  if (topology && [...topology.nodes, ...topology.links, ...topology.flows].some((entity) => !latest[entity.id])) return "unknown";
  if (!connected || syncing || !coherent || Date.now() - receiptAt > 3500 || Date.now() - observationAt > 3500) return "stale";
  return ready ? "fresh" : "learning";
}

export const useLive = create<LiveState>(() => ({
  connected: false, syncing: true, coherent: false, error: "", dataStatus: "unknown", generation: null, sequence: -1,
  lastSampleAt: null, lastObservedAt: null, ageSeconds: null, topology: null, latest: {}, history: [], anomalies: {}, alertLog: [],
  detector: { ready: false, progress: 0 }, diagnosis: [], diagnosisMeta: null, incident: EMPTY_INCIDENT, autonomy: null, backend: null,
  loadSnapshot, loadTopology: loadSnapshot, loadAnomalies: loadSnapshot,
}));

function telemetry(tick: Sample[], retainHistory: boolean, observedAt?: string | null) {
  receiptAt = tick.length ? Date.now() : 0;
  const parsed = observedAt ? Date.parse(observedAt) : NaN;
  observationAt = Number.isFinite(parsed) ? parsed : receiptAt;
  const latest = Object.fromEntries(tick.map((sample) => [sample.entity_id, sample]));
  const lastSampleAt = tick.map((sample) => sample.ts).sort().at(-1) ?? null;
  const state = useLive.getState();
  return {
    latest, lastSampleAt, lastObservedAt: observedAt ?? null, ageSeconds: tick.length ? Math.max(0, Math.floor((Date.now() - observationAt) / 1000)) : null,
    history: retainHistory ? state.history.at(-1)?.[0]?.ts === tick[0]?.ts ? state.history : [...state.history.slice(-(HISTORY - 1)), tick] : tick.length ? [tick] : [],
  };
}

async function loadSnapshot() {
  const ticket = ++snapshotRevision;
  snapshotController?.abort();
  const controller = new AbortController();
  snapshotController = controller;
  buffer = [];
  useLive.setState((state) => ({ syncing: true, coherent: false, error: "", dataStatus: quality(state.connected, state.detector.ready, state.latest, true) }));
  try {
    const snapshot = await requestJSON<Snapshot>("/api/snapshot", { signal: controller.signal });
    if (ticket !== snapshotRevision || controller.signal.aborted) return;
    if (!snapshot || typeof snapshot.generation !== "string" || !Number.isInteger(snapshot.sequence) || !Array.isArray(snapshot.telemetry) || !snapshot.topology || !snapshot.detector || !Array.isArray(snapshot.anomalies) || !snapshot.incident) {
      throw new Error("The gateway returned an incomplete live snapshot.");
    }
    const previous = useLive.getState();
    const sameGeneration = previous.generation === snapshot.generation;
    // A later socket generation must never be replaced by a snapshot requested before it.
    const pending = buffer;
    if (pending.some((event) => event.generation !== snapshot.generation)) {
      void loadSnapshot();
      return;
    }
    if (retiredGenerations.has(snapshot.generation)) { void loadSnapshot(); return; }
    if (!sameGeneration && previous.generation) retiredGenerations.add(previous.generation);
    const measurements = telemetry(snapshot.telemetry, sameGeneration, snapshot.observed_at ?? snapshot.emitted_at);
    useLive.setState({
      ...measurements, generation: snapshot.generation, sequence: snapshot.sequence, topology: snapshot.topology,
      detector: snapshot.detector, anomalies: Object.fromEntries(snapshot.anomalies.map((a) => [a.entity_id, a])),
      diagnosis: snapshot.diagnosis, diagnosisMeta: snapshot.diagnosis_meta ?? null, incident: snapshot.incident, autonomy: snapshot.autonomy, backend: snapshot.backend.kind,
      alertLog: sameGeneration ? previous.alertLog : [], syncing: false, coherent: true, error: "",
      dataStatus: quality(previous.connected, snapshot.detector.ready, measurements.latest, false, snapshot.topology, true),
    });
    buffer = [];
    // Only events strictly newer than the coherent snapshot are replayed.
    pending.filter((event) => event.generation === snapshot.generation && event.sequence > snapshot.sequence).forEach(applyEnvelope);
  } catch (error) {
    if (ticket !== snapshotRevision || controller.signal.aborted) return;
    useLive.setState((state) => ({ syncing: false, coherent: false, error: errorMessage(error), dataStatus: quality(false, state.detector.ready, state.latest, false) }));
  } finally {
    if (ticket === snapshotRevision) snapshotController = null;
  }
}

function applyEnvelope(message: Envelope) {
  if (retiredGenerations.has(message.generation)) return;
  const state = useLive.getState();
  if (state.syncing) { buffer.push(message); if (buffer.length > 1000) buffer.shift(); return; }
  // Fresh telemetry cannot repair a missed decision. Only a complete snapshot restores coherence.
  if (!state.coherent) { void loadSnapshot(); buffer.push(message); return; }
  if (message.generation !== state.generation) {
    if (state.generation) retiredGenerations.add(state.generation);
    receiptAt = 0;
    useLive.setState({ generation: message.generation, sequence: -1, coherent: false, latest: {}, history: [], anomalies: {}, alertLog: [], diagnosis: [], diagnosisMeta: null, incident: EMPTY_INCIDENT, detector: { ready: false, progress: 0 }, dataStatus: "unknown" });
    void loadSnapshot();
    return;
  }
  if (message.sequence <= state.sequence) return;
  if (message.sequence > state.sequence + 1) {
    // Distributed topics can arrive out of order. Recover the complete control state.
    void loadSnapshot();
    buffer.push(message);
    return;
  }
  useLive.setState({ sequence: message.sequence });
  if (message.type === "telemetry" && Array.isArray(message.data)) {
    const measurements = telemetry(message.data as Sample[], true, message.emitted_at);
    const detector = message.detector ?? state.detector;
    useLive.setState({ ...measurements, detector, dataStatus: quality(state.connected, detector.ready, measurements.latest, false) });
  } else if (message.type === "detector") {
    const detector = message.data as LiveState["detector"];
    useLive.setState({ detector, dataStatus: quality(state.connected, detector.ready, state.latest, false) });
  } else if (message.type === "rca" && Array.isArray(message.data)) {
    useLive.setState({ diagnosis: message.data as Hypothesis[], diagnosisMeta: message.diagnosis_meta ?? null });
  } else if (message.type === "incident") {
    useLive.setState({ incident: message.data as IncidentState });
  } else if (message.type === "autonomy") {
    useLive.setState({ autonomy: message.data as Autonomy });
  } else if (message.type === "anomaly") {
    const { raised = [], cleared = [] } = message.data as { raised: Anomaly[]; cleared: string[] };
    const anomalies = { ...state.anomalies };
    raised.forEach((a) => { anomalies[a.entity_id] = a; });
    cleared.forEach((entity) => { delete anomalies[entity]; });
    const time = new Date().toLocaleTimeString();
    const events: AlertEvent[] = [
      ...raised.map((a) => ({ time, kind: "raised" as const, entity: a.entity_id, anomaly: a })),
      ...cleared.map((entity) => ({ time, kind: "cleared" as const, entity })),
    ];
    useLive.setState({ anomalies, alertLog: [...events, ...state.alertLog].slice(0, 100) });
  }
}

/** One socket, one coherent bootstrap, bounded retry, and complete unmount cleanup. */
export function useLiveConnection() {
  useEffect(() => {
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    let failures = 0;
    function connect() {
      if (stopped) return;
      socket = new WebSocket(WS_URL);
      socket.onopen = () => {
        if (stopped) { socket?.close(); return; }
        failures = 0;
        useLive.setState({ connected: true });
        void loadSnapshot();
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as Envelope;
          if (typeof message.generation !== "string" || !Number.isInteger(message.sequence)) throw new Error("Unsupported live message.");
          applyEnvelope(message);
        } catch { useLive.setState({ error: "A live update was invalid. Resynchronizing…" }); void loadSnapshot(); }
      };
      socket.onclose = () => {
        useLive.setState((state) => ({ connected: false, coherent: false, dataStatus: quality(false, state.detector.ready, state.latest, state.syncing) }));
        if (!stopped) retry = setTimeout(connect, Math.min(10000, 500 * 2 ** failures++) + Math.random() * 300);
      };
      socket.onerror = () => socket?.close();
    }
    connect();
    const ageTimer = setInterval(() => {
      const state = useLive.getState();
      const ageSeconds = receiptAt ? Math.max(0, Math.floor(Math.max(Date.now() - receiptAt, Date.now() - observationAt) / 1000)) : null;
      const dataStatus = quality(state.connected, state.detector.ready, state.latest, state.syncing);
      if (ageSeconds !== state.ageSeconds || dataStatus !== state.dataStatus) useLive.setState({ ageSeconds, dataStatus });
    }, 1000);
    return () => {
      stopped = true;
      clearInterval(ageTimer); clearTimeout(retry);
      ++snapshotRevision; snapshotController?.abort(); snapshotController = null; buffer = [];
      if (socket) {
        socket.onmessage = null; socket.onclose = null; socket.onerror = null;
        if (socket.readyState === WebSocket.CONNECTING) socket.onopen = () => socket?.close();
        else { socket.onopen = null; socket.close(); }
      }
      useLive.setState({ connected: false, syncing: false, coherent: false, dataStatus: "stale" });
    };
  }, []);
}

export async function postJSON<T = Record<string, unknown>>(path: string, body?: unknown, method = "POST"): Promise<T> {
  try {
    const result = await requestJSON<T>(`/api${path}`, {
      method, headers: { "content-type": "application/json", ...authHeader() }, body: JSON.stringify(body ?? {}),
    }, /copilot|\/report/.test(path) ? 90000 : 15000);
    if (path === "/reset" || path === "/backend") {
      // Invalidate reads immediately, then replace all generation-bound data atomically.
      ++snapshotRevision; snapshotController?.abort(); receiptAt = 0;
      const boundary = result as { generation?: string; sequence?: number };
      const previous = useLive.getState();
      if (boundary.generation && previous.generation && boundary.generation !== previous.generation) retiredGenerations.add(previous.generation);
      useLive.setState({ generation: boundary.generation ?? previous.generation, sequence: boundary.sequence ?? previous.sequence, coherent: false, latest: {}, history: [], anomalies: {}, diagnosis: [], diagnosisMeta: null, incident: EMPTY_INCIDENT, alertLog: [], detector: { ready: false, progress: 0 }, dataStatus: "unknown" });
      await loadSnapshot();
    } else if (path === "/autonomy") useLive.setState({ autonomy: result as Autonomy });
    return result;
  } catch (error) {
    if (error && typeof error === "object" && "status" in error && error.status === 401) useAuth.getState().logout();
    throw error;
  }
}
