"use client";

import { Activity, ArrowRight, CheckCircle2, FlaskConical, HeartPulse, Search, ShieldAlert, Stethoscope, Wrench } from "lucide-react";
import Link from "next/link";
import type { ActionCandidate, ActionEvent, ActionResult, Incident } from "@/lib/live";
import { useLive } from "@/lib/live";
import { useEntityName } from "@/lib/names";

const STAGES = [
  { id: "detect", label: "Detect", icon: Activity },
  { id: "diagnose", label: "Diagnose", icon: Stethoscope },
  { id: "decide", label: "Decide", icon: FlaskConical },
  { id: "heal", label: "Heal", icon: Wrench },
  { id: "verify", label: "Verify", icon: CheckCircle2 },
];

const STATUS: Record<string, string> = {
  idle: "Watching the network",
  verifying: "Fix applied, verifying that traffic recovers…",
  healed: "Healed: traffic is back to normal. The faulty part stays flagged until it is repaired",
  rolled_back: "Fix didn't help and was rolled back; trying the next one",
  no_action_needed: "No user traffic affected; flagged for maintenance",
  escalated: "Escalated: no safe automatic fix, a human needs to step in",
  alert_only: "Comfort level 0: alerting only, no fix was planned",
  recommended: "Comfort level 1: a tested fix is recommended, a human applies it",
  awaiting_approval: "Waiting for a human to approve the fix",
  rejected: "The proposed fix was rejected by a human",
};

/** "Reroute around Distribution North A ↔ Library · via Distribution North B → Core Router 1" */
export function describeAction(c: ActionCandidate, name: (id: string) => string): string {
  if (c.type === "rollback_config") return `Roll back forwarding rules of ${name(c.params.flow!)}`;
  const verb = c.type === "drain_node" ? "Drain" : "Reroute around";
  const via = Object.values(c.params.routes ?? {})[0]?.slice(1, -1).map(name).join(" → ");
  return `${verb} ${name(c.params.avoid![0])}${via ? ` · via ${via}` : ""}`;
}

function seconds(from: string, to: string) {
  return ((new Date(to).getTime() - new Date(from).getTime()) / 1000).toFixed(1);
}

export function Stepper({ incident }: { incident: Incident }) {
  const done = new Map(incident.timeline.map((e) => [e.stage, e.ts]));
  const current = STAGES.find((s) => !done.has(s.id))?.id;
  return (
    <ol className="grid grid-cols-5 gap-2">
      {STAGES.map((s, i) => {
        const ts = done.get(s.id);
        const active = s.id === current && incident.status !== "failed";
        return (
          <li key={s.id} className="relative flex flex-col items-center text-center">
            {i > 0 && (
              <span
                className="absolute top-6 right-1/2 h-0.5 w-full -translate-y-1/2"
                style={{ background: ts ? "var(--healthy)" : "var(--glass-border)", transition: "background 500ms" }}
              />
            )}
            <span
              className={`relative grid size-12 place-items-center rounded-full border-2 ${active ? "animate-pulse" : ""}`}
              style={{
                borderColor: ts ? "var(--healthy)" : active ? "var(--warning)" : "var(--glass-border)",
                background: ts ? "color-mix(in oklab, var(--healthy) 25%, var(--bg))" : "var(--bg)",
              }}
            >
              <s.icon className="size-5" />
            </span>
            <span className="mt-2 text-sm font-medium">{s.label}</span>
            <span className="text-xs text-fg-muted tabular-nums">{ts ? `+${seconds(incident.opened_at, ts)}s` : "…"}</span>
          </li>
        );
      })}
    </ol>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="glass p-4">
      <p className="text-xs text-fg-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="text-xs text-fg-muted">{hint}</p>}
    </div>
  );
}

function fmtLatency(v: number | undefined, loss: number | undefined) {
  if (v === undefined) return "-";
  return loss !== undefined && loss >= 99 ? "unreachable" : `${v.toFixed(1)} ms`;
}

export function SelfHealing() {
  const { incident, healer_status, actions } = useLive((s) => s.incident);

  if (!incident) {
    return (
      <div className="glass flex min-h-40 flex-col items-center justify-center p-6 text-center">
        <HeartPulse className="size-8 text-healthy" />
        <p className="mt-2 font-semibold">{STATUS.idle}</p>
        <p className="text-sm text-fg-muted">Inject a fault in the Fault Lab to watch NetHeal detect, diagnose and heal it.</p>
      </div>
    );
  }

  const message = actions.find((a) => a.kind === "escalated" || a.kind === "no_action")?.payload as string | undefined;

  return (
    <div className="space-y-4">
      <div className="glass p-6">
        <div className="mb-6 flex items-center justify-between gap-4">
          <p className="flex items-center gap-2 font-semibold">
            {healer_status === "escalated" ? <ShieldAlert className="size-5 text-critical" /> : <HeartPulse className="size-5 text-healthy" />}
            {STATUS[healer_status] ?? healer_status}
          </p>
          <Link href={`/dashboard/incidents/${incident.id}`} className="flex items-center gap-1 text-sm text-fg-muted hover:text-fg">
            Incident {incident.status} · report <ArrowRight className="size-3.5" />
          </Link>
        </div>
        <Stepper incident={incident} />
        {message && <p className="mt-6 text-sm text-fg-muted">{message}</p>}
        {healer_status === "awaiting_approval" && (
          <Link href="/dashboard/approvals" className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-fg px-4 py-2 text-sm font-medium text-bg">
            Review the fix on the Approvals page <ArrowRight className="size-3.5" />
          </Link>
        )}
      </div>

      <HealingResults incident={incident} actions={actions} />
    </div>
  );
}

/** MTTD/MTTR, before → after, and the twin-ranked candidate fixes of one incident. */
export function HealingResults({ incident, actions }: { incident: Incident; actions: ActionEvent[] }) {
  const name = useEntityName();
  const candidates = (actions.find((a) => a.kind === "proposed")?.payload ?? []) as ActionCandidate[];
  const applied = new Set(actions.filter((a) => a.kind === "applied").map((a) => (a.payload as ActionCandidate).id));
  const results = new Map(
    actions.filter((a) => a.kind === "result").map((a) => [(a.payload as ActionResult).action_id, a.payload as ActionResult]),
  );
  const final = [...results.values()].at(-1);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Time to detect (MTTD)" value={incident.mttd_s != null ? `${incident.mttd_s.toFixed(1)} s` : "-"} hint="from the moment the fault began" />
        <Kpi label="Time to heal (MTTR)" value={incident.mttr_s != null ? `${incident.mttr_s.toFixed(1)} s` : "-"} hint="fault start → verified fix" />
        <Kpi
          label="Latency, affected traffic"
          value={final ? `${fmtLatency(final.before.latency_ms, final.before.loss_pct)} → ${final.after.latency_ms.toFixed(1)} ms` : "-"}
          hint={final ? `normal ${final.after.baseline_latency_ms.toFixed(1)} ms` : undefined}
        />
        <Kpi
          label="Packet loss, affected traffic"
          value={final ? `${final.before.loss_pct.toFixed(1)}% → ${final.after.loss_pct.toFixed(2)}%` : "-"}
        />
      </div>

      {candidates.length > 0 && (
        <div className="glass overflow-x-auto p-6">
          <h3 className="flex items-center gap-2 font-semibold">
            <Search className="size-4" /> Candidate fixes, tested on the digital twin first
          </h3>
          <table className="mt-4 w-full text-sm">
            <thead className="text-left text-xs text-fg-muted">
              <tr>
                <th className="pb-2 font-normal">#</th>
                <th className="pb-2 font-normal">Action</th>
                <th className="pb-2 text-right font-normal">Twin: latency</th>
                <th className="pb-2 text-right font-normal">Twin: loss</th>
                <th className="pb-2 text-right font-normal">Twin: peak load</th>
                <th className="pb-2 text-right font-normal">Safety check</th>
                <th className="pb-2 text-right font-normal">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => {
                const r = results.get(c.id);
                return (
                  <tr key={c.id} className="border-t border-[var(--glass-border)]">
                    <td className="py-2.5 text-fg-muted">{i + 1}</td>
                    <td className="py-2.5">
                      {describeAction(c, name)}
                      {c.policy_reasons?.map((r) => (
                        <p key={r} className="text-xs text-critical">Blocked: {r}</p>
                      ))}
                    </td>
                    <td className="py-2.5 text-right tabular-nums">{c.twin_prediction?.latency_ms.toFixed(1)} ms</td>
                    <td className="py-2.5 text-right tabular-nums">{c.twin_prediction?.loss_pct.toFixed(2)}%</td>
                    <td className="py-2.5 text-right tabular-nums">{Math.round((c.twin_prediction?.max_util ?? 0) * 100)}%</td>
                    <td className="py-2.5 text-right">
                      <span className={c.opa_decision === "allow" ? "text-healthy" : "text-critical"}>
                        {c.opa_decision === "allow" ? "passed" : "blocked"}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      {r ? (r.verified ? <span className="text-healthy">✓ verified</span> : <span className="text-warning">↩ rolled back</span>)
                        : applied.has(c.id) ? <span className="text-fg-muted">verifying…</span> : <span className="text-fg-muted">-</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
