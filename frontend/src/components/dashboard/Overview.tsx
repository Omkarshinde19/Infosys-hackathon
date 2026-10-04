"use client";

import { healthColor, healthLabel, networkHealth } from "@/lib/health";
import { useLive } from "@/lib/live";

function avg(xs: number[]) {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

function Tile({ label, value, unit, hint }: { label: string; value: string; unit?: string; hint?: string }) {
  return (
    <div className="glass p-5">
      <p className="text-sm text-fg-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums">
        {value}
        {unit && <span className="ml-1 text-base font-normal text-fg-muted">{unit}</span>}
      </p>
      {hint && <p className="mt-1 text-xs text-fg-muted">{hint}</p>}
    </div>
  );
}

export function Overview() {
  const latest = useLive((s) => s.latest);
  const samples = Object.values(latest);
  const flows = samples.filter((s) => s.entity_type === "flow");
  const links = samples.filter((s) => s.entity_type === "link");

  const score = networkHealth(flows);
  const reachable = flows.filter((f) => f.latency_ms !== null);
  const linksDown = links.filter((l) => l.latency_ms === null).length;
  const throughput = flows.reduce((t, f) => t + (f.throughput_mbps ?? 0), 0);
  const demand = useLive((s) => s.topology?.flows.reduce((t, f) => t + f.demand_mbps, 0) ?? 0);

  // Ring gauge geometry
  const r = 52;
  const c = 2 * Math.PI * r;

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <div className="glass flex flex-col items-center justify-center p-6">
        <div className="relative">
        <svg viewBox="0 0 120 120" className="size-40 -rotate-90">
          <circle cx="60" cy="60" r={r} fill="none" stroke="var(--glass-border)" strokeWidth="10" />
          <circle
            cx="60" cy="60" r={r} fill="none" strokeWidth="10" strokeLinecap="round"
            stroke={healthColor(score)}
            strokeDasharray={c}
            strokeDashoffset={c * (1 - score)}
            style={{ transition: "stroke-dashoffset 600ms, stroke 600ms" }}
          />
        </svg>
        <p className="absolute inset-0 grid place-items-center text-4xl font-semibold tabular-nums">
          {Math.round(score * 100)}
        </p>
        </div>
        <p className="mt-3 text-sm text-fg-muted">Network health · {healthLabel(score)}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tile label="Avg latency" value={avg(reachable.map((f) => f.latency_ms!)).toFixed(1)} unit="ms" hint="across all flows" />
        <Tile label="Avg packet loss" value={avg(flows.map((f) => f.loss_pct ?? 0)).toFixed(2)} unit="%" hint="across all flows" />
        <Tile
          label="Delivered throughput"
          value={(throughput / 1000).toFixed(2)}
          unit="Gbps"
          hint={demand ? `${Math.round((throughput / demand) * 100)}% of demand` : undefined}
        />
        <Tile label="Links down" value={String(linksDown)} hint={`of ${links.length} links`} />
      </div>
    </div>
  );
}
