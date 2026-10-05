"use client";

import { Brain, Gauge, LineChart, Network } from "lucide-react";
import { useEffect, useState } from "react";
import { CAUSES } from "@/components/dashboard/Diagnosis";
import type { Hypothesis } from "@/lib/live";

type Scores = Record<string, number>;
type Insights = {
  models: {
    rca: { all_snapshots: Scores; first_diagnosis: Scores; post_heal: Scores; test_snapshots: number };
    forecast: Record<string, number> & { shap_mean_abs: Scores };
    lstm_ae: Record<string, number>;
  };
  incidents: { total: number; healed: number; escalated: number; avg_mttd_s: number | null; avg_mttr_s: number | null; by_cause: Record<string, number> };
};

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="glass p-5">
      <p className="text-sm text-fg-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-fg-muted">{hint}</p>}
    </div>
  );
}

export default function InsightsPage() {
  const [data, setData] = useState<Insights | null>(null);
  useEffect(() => {
    fetch("/api/insights").then((r) => r.json()).then(setData);
  }, []);
  if (!data) return null;
  const { rca, forecast, lstm_ae } = data.models;
  const inc = data.incidents;
  const methods = [["voting_007_target", "007 voting alone"], ["rules", "Expert rules"], ["gnn", "Graph neural network"], ["ensemble", "Ensemble (live)"]];
  const shapTotal = Object.values(forecast.shap_mean_abs).reduce((a, b) => a + b, 0);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">Performance &amp; AI insights</h1>
        <p className="mt-1 text-sm text-fg-muted">How well NetHeal works: live incident stats and every model measured on faults it never trained on.</p>
      </header>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Gauge className="size-5" /> This session</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Incidents handled" value={String(inc.total)} hint={`${inc.healed} healed · ${inc.escalated} escalated`} />
          <Stat label="Avg time to detect" value={inc.avg_mttd_s != null ? `${inc.avg_mttd_s} s` : "-"} />
          <Stat label="Avg time to heal" value={inc.avg_mttr_s != null ? `${inc.avg_mttr_s} s` : "-"} />
          <Stat label="Most common cause" value={Object.entries(inc.by_cause).sort((a, b) => b[1] - a[1])[0]?.[0]
            ? CAUSES[Object.entries(inc.by_cause).sort((a, b) => b[1] - a[1])[0][0] as Hypothesis["cause"]].label : "-"} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Network className="size-5" /> Root-cause accuracy</h2>
        <div className="glass p-6">
          <p className="mb-4 text-sm text-fg-muted">Top-1 = cause and location exactly right, on {rca.test_snapshots} held-out snapshots from 3,000 simulated faults.</p>
          <div className="space-y-3">
            {methods.map(([key, label]) => (
              <div key={key}>
                <div className="flex justify-between text-sm"><span>{label}</span><span className="tabular-nums">{pct(rca.all_snapshots[key])}</span></div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--glass-border)]">
                  <div className="h-full rounded-full bg-accent-2" style={{ width: pct(rca.all_snapshots[key]) }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><LineChart className="size-5" /> Early warning forecaster</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Stat label="Warned before the SLA breach" value={pct(forecast.warned_before_breach_pct)} hint={`${forecast.warned_before_breach} of ${forecast.gradual_breaches} gradual faults`} />
            <Stat label="Median warning time" value={`${forecast.median_lead_time_s} s`} hint={`${forecast.test_healthy_false_warnings} false warnings on ${forecast.test_healthy_examples.toLocaleString()} healthy moments`} />
          </div>
          <div className="glass mt-4 p-6">
            <p className="mb-3 text-sm font-medium">What drives a warning (SHAP)</p>
            {Object.entries(forecast.shap_mean_abs).slice(0, 5).map(([feature, value]) => (
              <div key={feature} className="mb-2">
                <div className="flex justify-between text-xs"><span>{feature.replaceAll("_", " ")}</span><span className="tabular-nums">{pct(value / shapTotal)}</span></div>
                <div className="mt-1 h-1.5 rounded-full bg-[var(--glass-border)]"><div className="h-full rounded-full bg-healthy" style={{ width: pct(value / shapTotal) }} /></div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Brain className="size-5" /> LSTM autoencoder</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Stat label="Faults detected" value={pct(lstm_ae.fault_detection_rate)} />
            <Stat label="False positives" value={pct(lstm_ae.healthy_false_positive_rate)} hint="on held-out healthy traffic" />
          </div>
          <div className="glass mt-4 p-6 text-sm text-fg-muted">
            Learned what 10 seconds of normal behaviour looks like for every link, device and flow. Typical reconstruction error:
            healthy {lstm_ae.healthy_error_median.toExponential(1)} vs faulty {lstm_ae.fault_error_median.toFixed(2)}.
          </div>
        </div>
      </section>
    </div>
  );
}
