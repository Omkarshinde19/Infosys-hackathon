"use client";

import { useLive } from "@/lib/live";

/** Data freshness is independent of whether a WebSocket is open. */
export function DataStatus() {
  const status = useLive((s) => s.dataStatus);
  const age = useLive((s) => s.ageSeconds);
  const syncing = useLive((s) => s.syncing);
  const error = useLive((s) => s.error);
  const progress = useLive((s) => s.detector.progress);
  if (status === "fresh" && !error) return null;
  const text = status === "unknown" ? "Waiting for measured network data"
    : status === "learning" ? `Learning the detection baseline · ${Math.round(progress * 100)}%`
    : `Telemetry is stale${age !== null ? ` · last received ${age}s ago` : ""}`;
  return (
    <div role="status" className="glass mb-5 flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm text-fg-muted">
      <span>{syncing ? "Synchronizing network state…" : text}{error && ` · ${error}`}</span>
      {(status === "stale" || error) && <button disabled={syncing} onClick={() => void useLive.getState().loadSnapshot()} className="underline disabled:opacity-40">Retry snapshot</button>}
    </div>
  );
}
