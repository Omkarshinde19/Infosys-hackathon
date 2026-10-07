"use client";

import { healthColor, healthLabel, networkHealth } from "@/lib/health";
import { useLive } from "@/lib/live";

function avg(xs: number[]) {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
}
const fmt = (value: number | null, digits = 1) => value === null ? "—" : value.toFixed(digits);

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
  const topology = useLive((s) => s.topology);
  const status = useLive((s) => s.dataStatus);
  const samples = Object.values(latest);
  const flows = samples.filter((s) => s.entity_type === "flow");
  const links = samples.filter((s) => s.entity_type === "link");

  const complete = Boolean(topology?.flows.length && topology.flows.every((flow) => latest[flow.id]));
  const score = complete ? networkHealth(flows) : null;
  const currentScore = status === "fresh" ? score : null;
  const reachable = flows.filter((f) => f.latency_ms !== null);
  const linksDown = links.filter((l) => l.latency_ms === null).length;
  const throughput = complete && flows.every((flow) => flow.throughput_mbps !== null) ? flows.reduce((t, f) => t + f.throughput_mbps!, 0) : null;
  const demand = topology?.flows.reduce((t, f) => t + f.demand_mbps, 0) ?? 0;
  const coverage = `${flows.length}/${topology?.flows.length ?? "?"} flows measured${status === "stale" ? " · stale" : ""}`;

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
            stroke={healthColor(currentScore)}
            strokeDasharray={c}
            strokeDashoffset={c * (1 - (currentScore ?? 0))}
            style={{ transition: "stroke-dashoffset 600ms, stroke 600ms" }}
          />
        </svg>
        <p className="absolute inset-0 grid place-items-center text-4xl font-semibold tabular-nums">
          {currentScore === null ? "—" : Math.round(currentScore * 100)}
        </p>
        </div>
        <p className="mt-3 text-sm text-fg-muted">Flow delivery quality · {status === "fresh" ? healthLabel(currentScore) : status === "learning" ? "Learning" : status === "stale" ? "Stale" : "Unknown"}</p>
        <p className="mt-1 text-xs text-fg-muted">{coverage}</p>
        <p className="mt-1 text-center text-[11px] text-fg-muted">Delivery heuristic from flow loss and reachability; service verification also checks latency against measured baselines.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tile label="Avg latency" value={fmt(avg(reachable.map((f) => f.latency_ms!)))} unit="ms" hint={`${reachable.length}/${topology?.flows.length ?? "?"} reachable flows${status === "stale" ? " · stale" : ""}`} />
        <Tile label="Avg packet loss" value={fmt(avg(flows.flatMap((f) => f.loss_pct === null ? [] : [f.loss_pct])), 2)} unit="%" hint={coverage} />
        <Tile
          label="Delivered throughput"
          value={fmt(throughput === null ? null : throughput / 1000, 2)}
          unit="Gbps"
          hint={demand && throughput !== null ? `${Math.round((throughput / demand) * 100)}% of demand${status === "stale" ? " · stale" : ""}` : coverage}
        />
        <Tile label="Links down" value={links.length ? String(linksDown) : "—"} hint={`${links.length}/${topology?.links.length ?? "?"} links measured${status === "stale" ? " · stale" : ""}`} />
      </div>
    </div>
  );
}
