"use client";

import { Cable, Cpu, Play, RotateCcw, Shuffle, TrafficCone, Unplug, Zap, ZapOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useCan } from "@/lib/auth";
import { postJSON, useLive } from "@/lib/live";

const FAULTS = [
  { type: "link_down", label: "Link down", icon: Unplug, target: "link", text: "A cable or port fails completely." },
  { type: "gray_failure", label: "Gray failure", icon: Cable, target: "link", text: "Link looks up but silently drops packets." },
  { type: "congestion", label: "Congestion", icon: TrafficCone, target: "link", text: "A traffic surge overloads a link." },
  { type: "flapping", label: "Flapping link", icon: ZapOff, target: "link", text: "Link keeps going up and down." },
  { type: "node_overload", label: "Node overload", icon: Cpu, target: "node", text: "A switch or router runs out of CPU." },
  { type: "misconfig", label: "Misconfiguration", icon: Shuffle, target: "flow", text: "A bad rule silently drops one flow." },
] as const;

type Event = { time: string; text: string; ok: boolean };

// Realistic one-click drills. The last one shows the safety policy blocking a risky fix.
const SCENARIOS = [
  { title: "Exam day surge at the Library", type: "congestion", target: "dist1-library", severity: 0.9, ramp_s: 10 },
  { title: "Hostel fibre cut", type: "link_down", target: "dist1-hostel_a", severity: 1, ramp_s: 0 },
  { title: "Silent packet loss at the CS Lab", type: "gray_failure", target: "dist3-lab_cs", severity: 0.5, ramp_s: 15 },
  { title: "Flaky cable to the Auditorium", type: "flapping", target: "dist3-auditorium", severity: 1, ramp_s: 0 },
  { title: "Overloaded distribution switch", type: "node_overload", target: "dist1", severity: 0.7, ramp_s: 5 },
  { title: "Bad firewall rule for Admin", type: "misconfig", target: "admin-internet", severity: 1, ramp_s: 0 },
  { title: "Core router meltdown (policy blocks the fix)", type: "node_overload", target: "core1", severity: 0.8, ramp_s: 0 },
];

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

  async function inject(body: { type: string; target: string; severity: number; ramp_s: number } = { type, target: chosen, severity, ramp_s: ramp }, label = `${fault.label.toLowerCase()} on ${chosen}`) {
    try {
      await postJSON("/fault", body);
      log(`Injected ${label}`, true);
    } catch (e) {
      log(`Failed: ${(e as Error).message}`, false);
    }
  }

  const isAdmin = useCan("admin");
  const [autoHeal, setAutoHeal] = useState<boolean | null>(null);
  useEffect(() => {
    fetch("/api/autonomy").then((r) => r.json()).then((a) => setAutoHeal(a.level > 0));
  }, []);

  async function toggleAutoHeal() {
    try {
      const a = await postJSON("/autonomy", { level: autoHeal ? 0 : 4 }, "PUT");
      setAutoHeal(a.level > 0);
      log(`Auto heal turned ${a.level > 0 ? "on (level 4)" : "off (level 0: alert only)"}`, true);
    } catch (e) {
      log(`Failed: ${(e as Error).message}`, false);
    }
  }

  async function reset() {
    await postJSON("/reset");
    await useLive.getState().loadAnomalies(); // resync: a snapshot fetched before the reset may have landed after it
    log("Network reset to healthy baseline", true);
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="glass p-6 xl:col-span-2">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-semibold">Fire drills</h3>
          <button
            onClick={toggleAutoHeal}
            disabled={!isAdmin || autoHeal === null}
            title={isAdmin ? "" : "Only an admin can switch auto heal"}
            className="flex items-center gap-2 text-sm disabled:opacity-50"
          >
            <span className="text-fg-muted">Auto heal</span>
            <span className={`relative h-6 w-11 rounded-full transition-colors ${autoHeal ? "bg-healthy" : "bg-[var(--glass-border)]"}`}>
              <span className={`absolute top-0.5 size-5 rounded-full bg-white transition-all ${autoHeal ? "left-5.5" : "left-0.5"}`} />
            </span>
          </button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {SCENARIOS.map((sc) => (
            <button
              key={sc.title}
              disabled={!isOperator}
              onClick={() => inject({ type: sc.type, target: sc.target, severity: sc.severity, ramp_s: sc.ramp_s }, `"${sc.title}"`)}
              className="flex items-start gap-2 rounded-xl border border-[var(--glass-border)] p-3 text-left text-sm enabled:hover:bg-[var(--glass-hover)] disabled:opacity-40"
            >
              <Play className="mt-0.5 size-3.5 shrink-0" /> {sc.title}
            </button>
          ))}
        </div>
      </div>

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
          <button onClick={() => inject()} disabled={!isOperator} className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-40">
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
