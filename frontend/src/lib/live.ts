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

const HISTORY = 120; // ticks kept for charts (60 s at 2 ticks/s)
const WS_URL = process.env.NEXT_PUBLIC_GATEWAY_WS ?? "ws://localhost:8000/ws/live";

type LiveState = {
  connected: boolean;
  topology: Topology | null;
  latest: Record<string, Sample>;
  history: Sample[][];
  loadTopology: () => Promise<void>;
};

export const useLive = create<LiveState>((set) => ({
  connected: false,
  topology: null,
  latest: {},
  history: [],
  loadTopology: async () => set({ topology: await (await fetch("/api/topology")).json() }),
}));

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
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
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
    return () => {
      closed = true;
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
