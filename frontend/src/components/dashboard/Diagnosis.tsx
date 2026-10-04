"use client";

import { Cable, Cpu, Search, Shuffle, Stethoscope, TrafficCone, Unplug, ZapOff } from "lucide-react";
import { type Hypothesis, useLive } from "@/lib/live";
import { useEntityName } from "@/lib/names";

export const CAUSES: Record<Hypothesis["cause"], { label: string; text: string; icon: typeof Unplug }> = {
  link_failure: { label: "Link failure", text: "The connection is completely down.", icon: Unplug },
  gray_failure: { label: "Gray failure", text: "The link looks up but is silently dropping packets.", icon: Cable },
  congestion: { label: "Congestion", text: "More traffic than the link can carry.", icon: TrafficCone },
  node_overload: { label: "Device overload", text: "A switch or router is running out of CPU.", icon: Cpu },
  misconfig: { label: "Misconfiguration", text: "A forwarding rule is sending this traffic nowhere.", icon: Shuffle },
  flapping: { label: "Flapping link", text: "The link keeps going up and down.", icon: ZapOff },
};

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-fg-muted">
        <span>{label}</span>
        <span className="tabular-nums">{Math.round(value * 100)}%</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--glass-border)]">
        <div className="h-full bg-accent-2 transition-[width] duration-500" style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}

export function Diagnosis() {
  const diagnosis = useLive((s) => s.diagnosis);
  const name = useEntityName();
  const [top, ...others] = diagnosis;

  if (!top) {
    return (
      <div className="glass flex min-h-40 flex-col items-center justify-center p-6 text-center">
        <Stethoscope className="size-8 text-fg-muted" />
        <p className="mt-2 font-semibold">No active incident</p>
        <p className="text-sm text-fg-muted">When alerts appear, NetHeal works out the single most likely root cause here.</p>
      </div>
    );
  }

  const cause = CAUSES[top.cause];
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="glass p-6" style={{ borderColor: "var(--critical)" }}>
        <p className="text-xs tracking-wider text-fg-muted uppercase">Most likely root cause</p>
        <div className="mt-3 flex items-start gap-4">
          <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-critical/20">
            <cause.icon className="size-7 text-critical" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-2xl font-semibold">{cause.label}</h3>
            <p className="text-lg">{name(top.target)}</p>
            <p className="mt-1 text-sm text-fg-muted">{cause.text}</p>
          </div>
          <div className="text-right">
            <p className="text-4xl font-semibold tabular-nums">{Math.round(top.confidence * 100)}%</p>
            <p className="text-xs text-fg-muted">confidence</p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium">Evidence</p>
            <ul className="space-y-2 text-sm">
              {top.evidence.map((e) => (
                <li key={e.description} className="flex gap-2">
                  <Search className="mt-0.5 size-4 shrink-0 text-fg-muted" /> {e.description}
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-3">
            <p className="text-sm font-medium">How sure each method is</p>
            <Bar label="Fault signature (telemetry pattern)" value={top.method_scores.signature ?? 0} />
            <Bar label="Flow voting (007): affected flows crossing it" value={top.method_scores.voting ?? 0} />
          </div>
        </div>
      </div>

      <div className="glass p-6">
        <h3 className="font-semibold">Other candidates</h3>
        <ul className="mt-4 space-y-3 text-sm">
          {others.length === 0 && <li className="text-fg-muted">None. All evidence points to one cause.</li>}
          {others.map((h) => (
            <li key={h.id} className="flex items-center justify-between gap-3">
              <span>
                {CAUSES[h.cause].label} · <span className="text-fg-muted">{name(h.target)}</span>
              </span>
              <span className="tabular-nums text-fg-muted">{Math.round(h.confidence * 100)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
