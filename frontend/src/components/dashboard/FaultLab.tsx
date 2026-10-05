"use client";

import { Cable, Cpu, RotateCcw, Shuffle, TrafficCone, Unplug, Zap, ZapOff } from "lucide-react";
import { useState } from "react";
import { useCan } from "@/lib/auth";
import { postJSON, useLive } from "@/lib/live";

const FAULTS = [
  { type: "link_down", label: "Link down", icon: Unplug, target: "link", text: "A cable or port fails completely." },
  { type: "gray_failure", label: "Gray failure", icon: Cable, target: "link", text: "Link looks up but silently drops packets." },
  { type: "congestion", label: "Congestion", icon: TrafficCone, target: "link", text: "A traffic surge overloads a link." },
  { type: "flapping", label: "Flapping link", icon: ZapOff, target: "link", text: "Link keeps going up and down." },
  { type: "node_overload", label: "Node overload", icon: Cpu, target: "node", text: "A switch or router runs out of CPU." },
  { type: "misconfig", label: "Misconfiguration", icon: Shuffle, target: "flow", text: "A bad rule black-holes one flow." },
] as const;

type Event = { time: string; text: string; ok: boolean };

export function FaultLab() {
  const topology = useLive((s) => s.topology);
  const isOperator = useCan("operator");
  const [type, setType] = useState<(typeof FAULTS)[number]["type"]>("link_down");
  const [target, setTarget] = useState("");
  const [severity, setSeverity] = useState(1);
  const [ramp, setRamp] = useState(0);
  const [events, setEvents] = useState<Event[]>([]);

  const fault = FAULTS.find((f) => f.type === type)!;
  const targets =
    fault.target === "link"
      ? topology?.links.map((l) => l.id)
      : fault.target === "node"
        ? topology?.nodes.map((n) => n.id)
        : topology?.flows.map((f) => f.id);
  const chosen = targets?.includes(target) ? target : (targets?.[0] ?? "");

  function log(text: string, ok: boolean) {
    setEvents((e) => [{ time: new Date().toLocaleTimeString(), text, ok }, ...e].slice(0, 8));
  }

  async function inject() {
    try {
      await postJSON("/fault", { type, target: chosen, severity, ramp_s: ramp });
      log(`Injected ${fault.label.toLowerCase()} on ${chosen}`, true);
    } catch (e) {
      log(`Failed: ${(e as Error).message}`, false);
    }
  }

  async function reset() {
    await postJSON("/reset");
    log("Network reset to healthy baseline", true);
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="glass p-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FAULTS.map((f) => (
            <button
              key={f.type}
              onClick={() => setType(f.type)}
              className={`rounded-xl border p-4 text-left transition-colors ${
                type === f.type
                  ? "border-accent-2 bg-[var(--glass-hover)]"
                  : "border-[var(--glass-border)] hover:bg-[var(--glass-hover)]"
              }`}
            >
              <f.icon className="mb-2 size-5" />
              <p className="font-medium">{f.label}</p>
              <p className="mt-1 text-xs text-fg-muted">{f.text}</p>
            </button>
          ))}
        </div>

        <div className="mt-6 grid gap-5 md:grid-cols-3">
          <label className="text-sm">
            <span className="text-fg-muted">Target {fault.target}</span>
            <select
              value={chosen}
              onChange={(e) => setTarget(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--glass)] px-3 py-2"
            >
              {targets?.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-fg-muted">Severity · {Math.round(severity * 100)}%</span>
            <input type="range" min={0.1} max={1} step={0.05} value={severity}
              onChange={(e) => setSeverity(+e.target.value)} className="mt-3 w-full accent-[var(--accent-2)]" />
          </label>
          <label className="text-sm">
            <span className="text-fg-muted">Gradual onset · {ramp}s</span>
            <input type="range" min={0} max={30} step={1} value={ramp}
              onChange={(e) => setRamp(+e.target.value)} className="mt-3 w-full accent-[var(--accent-2)]" />
          </label>
        </div>

        <div className="mt-6 flex gap-3">
          <button onClick={inject} disabled={!isOperator} className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-40">
            <Zap className="size-4" /> Inject fault
          </button>
          <button onClick={reset} disabled={!isOperator} className="glass flex items-center gap-2 rounded-full! px-5 py-2.5 font-medium enabled:hover:bg-[var(--glass-hover)] disabled:opacity-40">
            <RotateCcw className="size-4" /> Reset network
          </button>
        </div>
        {!isOperator && (
          <p className="mt-3 text-sm text-fg-muted">
            <a href="/login" className="underline">Sign in as an operator</a> to break the network.
          </p>
        )}
      </div>

      <div className="glass p-6">
        <h3 className="font-semibold">Event log</h3>
        <ul className="mt-4 space-y-3 text-sm">
          {events.length === 0 && <li className="text-fg-muted">No faults injected yet.</li>}
          {events.map((e, i) => (
            <li key={i} className="flex gap-3">
              <span className={`mt-1.5 size-2 shrink-0 rounded-full ${e.ok ? "bg-warning" : "bg-critical"}`} />
              <span>
                <span className="text-fg-muted tabular-nums">{e.time}</span> · {e.text}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
