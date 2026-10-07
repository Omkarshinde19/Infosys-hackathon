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
  relapsed: "The fix stopped holding: traffic broke again, planning a new fix",
  no_action_needed: "No user traffic affected; flagged for maintenance",
  escalated: "Escalated: no safe automatic fix, a human needs to step in",
  alert_only: "Comfort level 0: alerting only, no fix was planned",
  recommended: "Comfort level 1: a tested fix is recommended, a human applies it",
  awaiting_approval: "Waiting for a human to approve the fix",
  replanning: "The network changed while the fix waited for approval; planning a new one",
  rejected: "The proposed fix was rejected by a human",
  execution_failed: "The fix could not be applied; review the recorded failure",
  rollback_failed: "Rollback failed: a human must intervene",
};

/** "Reroute around Distribution North A ↔ Library · via Distribution North B → Core Router 1" */
export function describeAction(c: ActionCandidate, name: (id: string) => string): string {
  if (c.type === "rollback_config") return `Roll back forwarding rules of ${name(c.params.flow!)}`;
  const verb = c.type === "drain_node" ? "Drain" : "Reroute around";
  const via = Object.values(c.params.routes ?? {})[0]?.slice(1, -1).map(name).join(" → ");
  return `${verb} ${c.params.avoid?.[0] ? name(c.params.avoid[0]) : "affected traffic"}${via ? ` · via ${via}` : ""}`;
}

function seconds(from: string, to: string) {
  return ((new Date(to).getTime() - new Date(from).getTime()) / 1000).toFixed(1);
}

export function Stepper({ incident }: { incident: Incident }) {
  const done = new Map(incident.timeline.map((e) => [e.stage, e.ts]));
  const latestIndex = (stage: string) => incident.timeline.findLastIndex((event) => event.stage === stage);
  // The history keeps earlier successes; the stepper represents the current attempt.
  if (latestIndex("decide") > latestIndex("heal")) { done.delete("heal"); done.delete("verify"); }
  if (incident.mttr_s === null || latestIndex("heal") > latestIndex("verify") || latestIndex("rollback") > latestIndex("verify")) done.delete("verify");
  const current = STAGES.find((s) => !done.has(s.id))?.id;
  // Resolved without a fix (nothing to fix) or left to a human: the rest won't happen.
  const toHuman = incident.status === "failed" || incident.status === "alerted";
  const skipped = !done.has("heal") && (incident.status === "resolved" || toHuman);
  return (
    <ol className="grid grid-cols-5 gap-2">
      {STAGES.map((s, i) => {
        const ts = done.get(s.id);
        const active = s.id === current && !skipped && !toHuman;
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
            <span className="text-xs text-fg-muted tabular-nums">
              {ts ? `+${seconds(incident.opened_at, ts)}s` : toHuman ? "to a human" : skipped ? "not needed" : "…"}
            </span>
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

function fmtLatency(v: number | null | undefined, loss: number | null | undefined) {
  if (loss != null && loss >= 99) return "unreachable";
  return v == null || !Number.isFinite(v) ? "—" : `${v.toFixed(1)} ms`;
}
const fmtLoss = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(2)}%`;

export function resultOutcome(result: ActionResult): string {
  if (result.outcome) return result.outcome.replaceAll("_", " ");
  if (result.verified) return "verified";
  if (result.rolled_back) return "rolled back";
  if (result.rollback_error) return "rollback failed";
  if (result.failure_reason) return "execution failed";
  return "unverified";
}

export function SelfHealing() {
  const { incident, healer_status, actions } = useLive((s) => s.incident);
  const status = useLive((s) => s.dataStatus);

  if (!incident) {
    return (
      <div className="glass flex min-h-40 flex-col items-center justify-center p-6 text-center">
        <HeartPulse className={`size-8 ${status === "fresh" ? "text-healthy" : "text-fg-muted"}`} />
        <p className="mt-2 font-semibold">{status === "fresh" ? STATUS.idle : "Waiting for a reliable detection baseline"}</p>
        <p className="text-sm text-fg-muted">Inject a fault in the Fault Lab to watch NetHeal detect, diagnose and heal it.</p>
      </div>
    );
  }

  // The latest decision and candidates: after a relapse or re-plan there is more than one.
  const message = actions.findLast((a) => a.kind === "escalated" || a.kind === "no_action" || a.kind === "alert_only")?.payload as string | undefined;

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
  const proposals = actions.filter((action) => action.kind === "proposed");
  const candidates = [...new Map(proposals.flatMap((action) => (action.payload as ActionCandidate[]).map((candidate) => [candidate.id, candidate] as const))).values()];
  const applied = new Set(actions.filter((a) => a.kind === "applied").map((a) => (a.payload as ActionCandidate).id));
  const results = new Map(
    actions.filter((a) => a.kind === "result").map((a) => [(a.payload as ActionResult).action_id, a.payload as ActionResult]),
  );
  const final = [...results.values()].at(-1);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Time to detect (MTTD)" value={incident.mttd_s != null ? `${incident.mttd_s.toFixed(1)} s` : "-"} hint="simulated seconds from fault start" />
        <Kpi label="Time to heal (MTTR)" value={incident.mttr_s != null ? `${incident.mttr_s.toFixed(1)} s` : "-"} hint="simulated seconds · fault start → verified fix" />
        <Kpi
          label="Latency, affected traffic"
          value={final ? `${fmtLatency(final.before.latency_ms, final.before.loss_pct)} → ${fmtLatency(final.after.latency_ms, final.after.loss_pct)}` : "—"}
          hint={final ? `Latest attempt: ${resultOutcome(final)} · baseline ${fmtLatency(final.after.baseline_latency_ms, 0)}` : undefined}
        />
        <Kpi
          label="Packet loss, affected traffic"
          value={final ? `${fmtLoss(final.before.loss_pct)} → ${fmtLoss(final.after.loss_pct)}` : "—"}
        />
      </div>

      {candidates.length > 0 && (
        <div className="glass overflow-x-auto p-6">
          <h3 className="flex items-center gap-2 font-semibold">
            <Search className="size-4" /> Candidate fixes, tested on the digital twin first
          </h3>
          <p className="mt-1 text-xs text-fg-muted">Complete history · {proposals.length} proposal rounds · {results.size} attempted fixes with recorded outcomes. Predictions describe the planned state; verification describes the measured result.</p>
          <table className="mt-4 w-full text-sm">
            <thead className="text-left text-xs text-fg-muted">
              <tr>
                <th className="w-8 pb-2 font-normal">#</th>
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
                    <td className="py-2.5 pr-3 align-top text-fg-muted">{i + 1}</td>
                    <td className="py-2.5">
                      {describeAction(c, name)}
                      {c.params.planner === "rl" && (
                        <span className="ml-2 rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[11px] text-fg-muted">
                          RL agent · moves {Object.keys(c.params.routes ?? {}).length} flow{Object.keys(c.params.routes ?? {}).length === 1 ? "" : "s"}
                        </span>
                      )}
                      {c.policy_reasons?.map((r) => (
                        <p key={r} className="text-xs text-critical">Blocked: {r}</p>
                      ))}
                      {c.planned_at && <p className="mt-1 text-xs text-fg-muted">Planned {new Date(c.planned_at).toLocaleTimeString()} · {c.id.slice(0, 8)}</p>}
                      {r?.failure_reason && <p className="text-xs text-critical">{r.failure_reason}</p>}
                      {r?.rollback_error && <p className="text-xs text-critical">Rollback error: {r.rollback_error}</p>}
                      {r?.verification_reasons?.map((reason) => <p key={reason} className="text-xs text-fg-muted">{reason}</p>)}
                      {r?.per_flow_before && (
                        <details className="mt-2 text-xs">
                          <summary className="cursor-pointer text-fg-muted">Measured before / after by service</summary>
                          <ul className="mt-1 space-y-1">
                            {Object.entries(r.per_flow_before).map(([id, before]) => {
                              const after = r.per_flow_after?.[id];
                              return <li key={id}>{name(id)}: {fmtLatency(before.latency_ms, before.loss_pct)} / {fmtLoss(before.loss_pct)} → {fmtLatency(after?.latency_ms, after?.loss_pct)} / {fmtLoss(after?.loss_pct)}</li>;
                            })}
                          </ul>
                        </details>
                      )}
                    </td>
                    <td className="py-2.5 text-right tabular-nums">{fmtLatency(c.twin_prediction?.latency_ms, c.twin_prediction?.loss_pct)}</td>
                    <td className="py-2.5 text-right tabular-nums">{fmtLoss(c.twin_prediction?.loss_pct)}</td>
                    <td className="py-2.5 text-right tabular-nums">{c.twin_prediction ? `${Math.round(c.twin_prediction.max_util * 100)}%` : "—"}</td>
                    <td className="py-2.5 text-right">
                      <span className={c.opa_decision === "allow" ? "text-healthy" : c.opa_decision === "deny" ? "text-critical" : "text-fg-muted"}>
                        {c.opa_decision === "allow" ? "passed" : c.opa_decision === "deny" ? "blocked" : "not evaluated"}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      {r ? <span className={r.verified ? "text-healthy" : r.rolled_back ? "text-warning" : "text-critical"}>{resultOutcome(r)}</span>
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
