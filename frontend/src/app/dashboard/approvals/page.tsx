"use client";

import { Check, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import { describeAction } from "@/components/dashboard/SelfHealing";
import { useCan } from "@/lib/auth";
import { postJSON, useLive } from "@/lib/live";
import { useEntityName } from "@/lib/names";

type Autonomy = { level: number; levels: Record<string, string> };

export default function ApprovalsPage() {
  const [autonomy, setAutonomy] = useState<Autonomy | null>(null);
  const [error, setError] = useState("");
  const isAdmin = useCan("admin");
  const isOperator = useCan("operator");
  const { awaiting, healer_status } = useLive((s) => s.incident);
  const name = useEntityName();

  useEffect(() => {
    fetch("/api/autonomy").then((r) => r.json()).then(setAutonomy);
  }, []);

  async function act(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">Approvals &amp; comfort level</h1>
        <p className="mt-1 text-sm text-fg-muted">Decide how much NetHeal may do on its own, and sign off fixes that need a human.</p>
      </header>

      {error && <p className="glass p-4 text-sm text-critical">{error}</p>}

      <section>
        <h2 className="mb-3 text-lg font-semibold">Comfort level</h2>
        <div className="grid gap-3 md:grid-cols-5">
          {autonomy &&
            Object.entries(autonomy.levels).map(([level, text]) => {
              const active = Number(level) === autonomy.level;
              return (
                <button
                  key={level}
                  disabled={!isAdmin}
                  onClick={() => act(async () => setAutonomy(await postJSON("/autonomy", { level: Number(level) }, "PUT")))}
                  className={`glass p-4 text-left transition-colors disabled:cursor-not-allowed ${
                    active ? "border-accent-2! bg-[var(--glass-hover)]" : "enabled:hover:bg-[var(--glass-hover)]"
                  }`}
                >
                  <p className="text-xs text-fg-muted">Level {level}</p>
                  <p className="mt-1 text-sm font-medium">{text.split(":")[0]}</p>
                  <p className="mt-1 text-xs text-fg-muted">{text.split(":")[1] ?? ""}</p>
                </button>
              );
            })}
        </div>
        {!isAdmin && <p className="mt-2 text-xs text-fg-muted">Only an admin can change the comfort level.</p>}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Waiting for approval</h2>
        {awaiting ? (
          <div className="glass p-6" style={{ borderColor: "var(--warning)" }}>
            <p className="font-semibold">{describeAction(awaiting, name)}</p>
            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
              <p>Twin latency: <b>{awaiting.twin_prediction?.latency_ms.toFixed(1)} ms</b></p>
              <p>Twin loss: <b>{awaiting.twin_prediction?.loss_pct.toFixed(2)}%</b></p>
              <p>Peak link load: <b>{Math.round((awaiting.twin_prediction?.max_util ?? 0) * 100)}%</b></p>
            </div>
            <p className="mt-3 flex items-center gap-2 text-sm text-healthy">
              <ShieldCheck className="size-4" /> Tested on the digital twin and passed every safety rule
            </p>
            <div className="mt-5 flex gap-3">
              <button
                disabled={!isOperator}
                onClick={() => act(() => postJSON(`/approvals/${awaiting.id}/approve`))}
                className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-40"
              >
                <Check className="size-4" /> Approve &amp; apply
              </button>
              <button
                disabled={!isOperator}
                onClick={() => act(() => postJSON(`/approvals/${awaiting.id}/reject`))}
                className="glass flex items-center gap-2 rounded-full! px-5 py-2.5 font-medium enabled:hover:bg-[var(--glass-hover)] disabled:opacity-40"
              >
                <X className="size-4" /> Reject
              </button>
            </div>
            {!isOperator && <p className="mt-3 text-xs text-fg-muted">Sign in as an operator to approve or reject.</p>}
          </div>
        ) : (
          <div className="glass p-6 text-sm text-fg-muted">
            Nothing is waiting. {healer_status === "rejected" && "The last proposed fix was rejected."}
          </div>
        )}
      </section>
    </div>
  );
}
