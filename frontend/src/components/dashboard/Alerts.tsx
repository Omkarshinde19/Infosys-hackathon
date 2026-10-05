"use client";

import { BellRing, CheckCircle2, ShieldCheck } from "lucide-react";
import { type Anomaly, useLive } from "@/lib/live";
import { useEntityName } from "@/lib/names";

const METRIC = {
  latency_ms: { label: "Latency", fmt: (v: number) => `${v.toFixed(1)} ms` },
  loss_pct: { label: "Packet loss", fmt: (v: number) => `${v.toFixed(2)}%` },
  util: { label: "Utilisation", fmt: (v: number) => `${Math.round(v * 100)}%` },
  cpu: { label: "CPU", fmt: (v: number) => `${Math.round(v * 100)}%` },
} as Record<string, { label: string; fmt: (v: number) => string }>;

const DETECTOR_NAMES: Record<string, string> = {
  zscore: "Robust z-score",
  iforest: "IsolationForest",
  reachability: "Reachability",
  lstm_ae: "LSTM autoencoder",
  forecast: "Forecaster",
};

function describe(a: Anomaly) {
  if (a.metric === "reachability") return "Unreachable: traffic can't get through";
  if (a.metric === "predicted_sla_breach") return `SLA breach predicted within 5 s (${Math.round(a.value * 100)}% risk)`;
  const m = METRIC[a.metric];
  return `${m.label} ${m.fmt(a.value)} (normal ${m.fmt(a.baseline)})`;
}

function AlertCard({ a, name }: { a: Anomaly; name: string }) {
  const color = a.severity === "critical" ? "var(--critical)" : "var(--warning)";
  return (
    <div className="glass p-4" style={{ borderColor: color }}>
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 font-semibold">
          <span className="size-2.5 animate-pulse rounded-full" style={{ background: color }} />
          {name}
        </p>
        <span className="text-xs text-fg-muted uppercase">{a.severity}</span>
      </div>
      <p className="mt-2 text-sm">{describe(a)}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
        {a.detectors.map((d) => (
          <span key={d} className="rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-fg-muted">
            {DETECTOR_NAMES[d] ?? d}
          </span>
        ))}
        <span className="ml-auto text-fg-muted tabular-nums">since {new Date(a.ts).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}

export function Alerts() {
  const anomalies = Object.values(useLive((s) => s.anomalies));
  const log = useLive((s) => s.alertLog);
  const detector = useLive((s) => s.detector);
  const name = useEntityName();

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="glass min-h-48 p-6">
        {!detector.ready ? (
          <div className="flex h-full flex-col justify-center">
            <p className="flex items-center gap-2 font-semibold">
              <ShieldCheck className="size-5" /> Learning what &quot;healthy&quot; looks like…
            </p>
            <p className="mt-1 text-sm text-fg-muted">
              The detector watches the network for 30 seconds to learn each link&apos;s normal behaviour.
            </p>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--glass-border)]">
              <div className="h-full bg-accent-2 transition-[width] duration-500" style={{ width: `${detector.progress * 100}%` }} />
            </div>
          </div>
        ) : anomalies.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <CheckCircle2 className="size-8 text-healthy" />
            <p className="mt-2 font-semibold">All clear</p>
            <p className="text-sm text-fg-muted">No anomalies. Every link, device and flow is within its normal range.</p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {anomalies
              .sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "critical" ? -1 : 1))
              .map((a) => <AlertCard key={a.entity_id} a={a} name={name(a.entity_id)} />)}
          </div>
        )}
      </div>

      <div className="glass p-6">
        <h3 className="flex items-center gap-2 font-semibold">
          <BellRing className="size-4" /> Alert timeline
        </h3>
        <ul className="mt-4 max-h-72 space-y-3 overflow-y-auto text-sm">
          {log.length === 0 && <li className="text-fg-muted">Nothing yet.</li>}
          {log.map((e, i) => (
            <li key={i} className="flex gap-3">
              <span className={`mt-1.5 size-2 shrink-0 rounded-full ${e.kind === "raised" ? "bg-critical" : "bg-healthy"}`} />
              <span>
                <span className="text-fg-muted tabular-nums">{e.time}</span> · {name(e.entity)}{" "}
                {e.kind === "raised" ? "flagged" : "back to normal"}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
