"use client";

import { FlaskConical, Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { describeAction } from "@/components/dashboard/SelfHealing";
import { type ActionCandidate, postJSON, useLive } from "@/lib/live";
import { useEntityName } from "@/lib/names";

type Result = {
  impact: { flow: string; latency_before_ms: number; latency_during_ms: number; loss_during_pct: number }[];
  candidates: ActionCandidate[];
  best: ActionCandidate | null;
  verdict: string;
};

const FAULTS = [
  ["link_down", "Link failure", "link"],
  ["gray_failure", "Gray failure", "link"],
  ["congestion", "Congestion", "link"],
  ["flapping", "Flapping link", "link"],
  ["node_overload", "Device overload", "node"],
  ["misconfig", "Misconfiguration", "flow"],
] as const;

export default function WhatIfPage() {
  const topology = useLive((s) => s.topology);
  const name = useEntityName();
  const [fault, setFault] = useState<(typeof FAULTS)[number][0]>("link_down");
  const [target, setTarget] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const kind = FAULTS.find((f) => f[0] === fault)![2];
  const targets =
    kind === "link" ? topology?.links.map((l) => l.id) : kind === "node" ? topology?.nodes.filter((n) => n.id !== "internet").map((n) => n.id) : topology?.flows.map((f) => f.id);
  const chosen = targets?.includes(target) ? target : (targets?.[0] ?? "");

  async function run() {
    setBusy(true);
    setError("");
    try {
      setResult(await postJSON("/whatif", { fault, target: chosen }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">What-If planner</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Ask &quot;what happens if X breaks?&quot;. It runs on a digital twin, so the real network is never touched.
        </p>
      </header>

      <div className="glass flex flex-wrap items-end gap-4 p-6">
        <label className="text-sm">
          <span className="text-fg-muted">If this happens…</span>
          <select value={fault} onChange={(e) => setFault(e.target.value as typeof fault)}
            className="mt-1.5 block rounded-lg border border-[var(--glass-border)] bg-[var(--glass)] px-3 py-2">
            {FAULTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-fg-muted">…on</span>
          <select value={chosen} onChange={(e) => setTarget(e.target.value)}
            className="mt-1.5 block min-w-72 rounded-lg border border-[var(--glass-border)] bg-[var(--glass)] px-3 py-2">
            {targets?.map((t) => <option key={t} value={t}>{name(t)}</option>)}
          </select>
        </label>
        <button onClick={run} disabled={busy || !chosen}
          className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-50">
          <Play className="size-4" /> {busy ? "Simulating…" : "Simulate on the twin"}
        </button>
      </div>

      {error && <p className="glass p-4 text-sm text-critical">{error}</p>}

      {result && (
        <>
          <div className="glass flex items-center gap-3 p-5 font-medium" style={{ borderColor: result.best || !result.impact.length ? "var(--healthy)" : "var(--critical)" }}>
            {result.best || !result.impact.length ? <ShieldCheck className="size-5 text-healthy" /> : <ShieldAlert className="size-5 text-critical" />}
            {result.verdict}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="glass p-6">
              <h3 className="flex items-center gap-2 font-semibold"><FlaskConical className="size-4" /> Who would suffer</h3>
              {result.impact.length === 0 ? (
                <p className="mt-3 text-sm text-fg-muted">Nobody: no traffic uses that element right now.</p>
              ) : (
                <ul className="mt-3 space-y-2 text-sm">
                  {result.impact.map((i) => (
                    <li key={i.flow} className="flex justify-between gap-3">
                      <span>{name(i.flow)}</span>
                      <span className="text-right text-fg-muted tabular-nums">
                        {i.loss_during_pct >= 99 ? "unreachable" : `${i.latency_before_ms} → ${i.latency_during_ms} ms · ${i.loss_during_pct}% loss`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="glass p-6">
              <h3 className="font-semibold">NetHeal&apos;s plan, tested on the twin</h3>
              <ul className="mt-3 space-y-3 text-sm">
                {result.candidates.length === 0 && <li className="text-fg-muted">No alternative path exists.</li>}
                {result.candidates.map((c) => (
                  <li key={c.id}>
                    <p className={c.opa_decision === "allow" ? "" : "text-fg-muted line-through"}>{describeAction(c, name)}</p>
                    <p className="text-xs text-fg-muted tabular-nums">
                      twin: {c.twin_prediction?.latency_ms.toFixed(1)} ms · {c.twin_prediction?.loss_pct.toFixed(2)}% loss · peak load{" "}
                      {Math.round((c.twin_prediction?.max_util ?? 0) * 100)}%
                    </p>
                    {c.policy_reasons.map((r) => <p key={r} className="text-xs text-critical">Blocked: {r}</p>)}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
