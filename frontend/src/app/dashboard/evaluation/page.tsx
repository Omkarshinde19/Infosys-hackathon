"use client";

import * as echarts from "echarts";
import { FlaskConical, HeartPulse, Search, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

const POLICIES = ["no_heal", "reactive", "twin", "predictive_twin", "rl"] as const;
type Policy = (typeof POLICIES)[number];
const LABEL: Record<Policy, string> = {
  no_heal: "No healing",
  reactive: "Reactive rules",
  twin: "NetHeal (twin)",
  predictive_twin: "NetHeal + prediction",
  rl: "NetHeal + RL (live)",
};
const COLOR: Record<Policy, string> = { no_heal: "#f2919f", reactive: "#f2c77b", twin: "#7da0ca", predictive_twin: "#6fd6c4", rl: "#b8a1e3" };
const FAULT_LABEL: Record<string, string> = {
  link_down: "Link down", gray_failure: "Gray failure", congestion: "Congestion",
  flapping: "Flapping link", node_overload: "Overloaded device", misconfig: "Misconfiguration",
};

type Summary = {
  scenarios: number;
  faults: number;
  healthy: number;
  detection: {
    precision: number; recall: number; f1: number; false_positive_rate: number | null; median_mttd_s: number | null; median_mttd_gradual_s: number | null;
  };
  rca: { top1: number | null; top3: number | null; voting_007_top1: number | null };
  healing: {
    sla_impacting_faults: number; recovered_rate: number | null; median_recovery_s: number | null; healed_rate: number | null;
    median_mttr_s: number | null; rollback_rate: number | null; escalated_rate: number | null;
  };
  sla: { violation_s_total: number; median_violation_s: number | null; p95_latency_ms: number | null; mean_loss_pct: number | null };
};
type Run = { policy: Policy; fault: { type: string } | null; sla_impact: boolean; recovery_s: number | null; mttr_s: number | null };
type Results = {
  meta: { scenarios: number; run_s: number };
  summary: { policies: Record<Policy, Summary>; by_fault: Record<string, Record<Policy, Summary>> };
  runs: Run[];
};

const pct = (v: number | null) => (v == null ? "–" : `${Math.round(v * 100)}%`);
const sec = (v: number | null) => (v == null ? "–" : `${v.toFixed(1)} s`);
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** An ECharts chart in a glass card; the toolbox saves it as a PNG for slides. */
function Chart({ option, className = "h-80" }: { option: echarts.EChartsOption; className?: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const chart = echarts.init(el.current!, null, { renderer: "canvas" });
    const muted = css("--fg-muted");
    const axis = { axisLabel: { color: muted }, axisLine: { lineStyle: { color: muted } }, splitLine: { lineStyle: { color: css("--glass-border") } } };
    chart.setOption({
      textStyle: { color: css("--fg") },
      legend: { type: "scroll", textStyle: { color: muted }, top: 0, left: 0, right: 36 },
      grid: { left: 56, right: 16, top: 56, bottom: 40 },
      tooltip: { trigger: "axis" },
      toolbox: { right: 0, top: 0, feature: { saveAsImage: { title: "Save PNG", backgroundColor: css("--bg") || "#021024" } } },
      ...option,
      xAxis: { ...axis, ...(option.xAxis as object), axisLabel: { color: muted, interval: 0, width: 72, overflow: "break" } },
      yAxis: { ...axis, ...(option.yAxis as object) },
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(el.current!);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);
  return <div ref={el} className={`glass p-4 ${className}`} />;
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="glass p-5">
      <p className="text-sm text-fg-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-fg-muted">{hint}</p>
    </div>
  );
}

function Table({ rows, s }: { rows: [string, (x: Summary) => string][]; s: Record<Policy, Summary> }) {
  return (
    <div className="glass overflow-x-auto p-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-fg-muted">
            <th className="p-3 font-medium" />
            {POLICIES.map((p) => (
              <th key={p} className="p-3 font-medium"><span className="mr-2 inline-block size-2 rounded-full" style={{ background: COLOR[p] }} />{LABEL[p]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, f]) => (
            <tr key={label} className="border-t border-[var(--glass-border)]">
              <td className="p-3">{label}</td>
              {POLICIES.map((p) => <td key={p} className="p-3 tabular-nums">{f(s[p])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function histogram(values: number[], edges: number[]) {
  return edges.slice(0, -1).map((lo, i) => values.filter((v) => v >= lo && v < edges[i + 1]).length);
}

export default function EvaluationPage() {
  const [data, setData] = useState<Results | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/evaluation")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("No results yet: run ./netheal eval"))))
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);
  const charts = useMemo((): echarts.EChartsOption[] | null => {
    if (!data) return null; // data only arrives in the browser, so css() can read the theme
    const s = data.summary.policies;
    const types = Object.keys(data.summary.by_fault);
    const edges = [0, 5, 10, 15, 20, 30, 45, 61];
    const impact = data.runs.filter((r) => r.fault && r.sla_impact);
    return [
      {
        xAxis: { type: "category", data: types.map((t) => FAULT_LABEL[t] ?? t) },
        yAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
        tooltip: { trigger: "axis", valueFormatter: (v) => `${v}%` },
        series: POLICIES.map((p) => ({
          name: LABEL[p], type: "bar", itemStyle: { color: COLOR[p], borderRadius: [4, 4, 0, 0] },
          data: types.map((t) => Math.round((data.summary.by_fault[t][p].healing.recovered_rate ?? 0) * 100)),
        })),
      },
      {
        xAxis: { type: "category", data: POLICIES.map((p) => LABEL[p]) },
        yAxis: { type: "value", name: "seconds", nameTextStyle: { color: css("--fg-muted") } },
        legend: { show: false },
        series: [{
          type: "bar", barWidth: "45%",
          data: POLICIES.map((p) => ({ value: s[p].sla.violation_s_total, itemStyle: { color: COLOR[p], borderRadius: [4, 4, 0, 0] } })),
          label: { show: true, position: "top", color: css("--fg"), formatter: (x) => `${Math.round(Number(x.value))} s` },
        }],
      },
      {
        xAxis: { type: "category", data: edges.slice(0, -1).map((e, i) => (i === edges.length - 2 ? `${e}+ s` : `${e}–${edges[i + 1]} s`)) },
        yAxis: { type: "value", name: "faults", nameTextStyle: { color: css("--fg-muted") } },
        series: POLICIES.filter((p) => p !== "no_heal").map((p) => ({
          name: LABEL[p], type: "bar", itemStyle: { color: COLOR[p], borderRadius: [4, 4, 0, 0] },
          data: histogram(impact.filter((r) => r.policy === p && r.mttr_s != null).map((r) => r.mttr_s!), edges),
        })),
      },
    ];
  }, [data]);

  if (error) return <p className="mx-auto max-w-6xl pt-10 text-fg-muted">{error}</p>;
  if (!data || !charts) return null;
  const s = data.summary.policies;
  const ours = s.rl;
  const none = s.no_heal;
  const saved = none.sla.violation_s_total ? 1 - ours.sla.violation_s_total / none.sla.violation_s_total : null;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">Evaluation</h1>
        <p className="mt-1 max-w-3xl text-sm text-fg-muted">
          {data.meta.scenarios} faults NetHeal never trained on (and healthy controls), each replayed under five policies for {data.meta.run_s} s.
          Same network, same fault, same random seed: the only difference is how the network responds.
        </p>
      </header>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><HeartPulse className="size-5" /> Headline</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Back within SLA" value={pct(ours.healing.recovered_rate)} hint={`vs ${pct(none.healing.recovered_rate)} without healing (${ours.healing.sla_impacting_faults} faults that hurt users)`} />
          <Stat label="Median time to heal" value={sec(ours.healing.median_mttr_s)} hint="fault to verified fix, including the 3 s check" />
          <Stat label="SLA violation avoided" value={pct(saved)} hint={`${Math.round(ours.sla.violation_s_total)} s vs ${Math.round(none.sla.violation_s_total)} s without healing`} />
          <Stat label="False alarms" value={pct(ours.detection.false_positive_rate)} hint={`on ${ours.healthy} healthy runs`} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><ShieldCheck className="size-5" /> Recovered, by fault type</h2>
        <Chart option={charts[0]} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-lg font-semibold">Total time users were hurt</h2>
          <Chart option={charts[1]} />
        </div>
        <div>
          <h2 className="mb-3 text-lg font-semibold">How fast fixes land (MTTR)</h2>
          <Chart option={charts[2]} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><FlaskConical className="size-5" /> Healing</h2>
        <Table s={s} rows={[
          ["Faults that hurt users", (x) => String(x.healing.sla_impacting_faults)],
          ["Recovered (SLA met, last 10 s)", (x) => pct(x.healing.recovered_rate)],
          ["Median time to recover", (x) => sec(x.healing.median_recovery_s)],
          ["Healed by a verified fix", (x) => pct(x.healing.healed_rate)],
          ["Median MTTR", (x) => sec(x.healing.median_mttr_s)],
          ["Fixes rolled back", (x) => pct(x.healing.rollback_rate)],
          ["Escalated to a human", (x) => pct(x.healing.escalated_rate)],
          ["p95 flow latency during a fault", (x) => (x.sla.p95_latency_ms == null ? "–" : `${x.sla.p95_latency_ms} ms`)],
        ]} />
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Search className="size-5" /> Detection and diagnosis</h2>
        <Table s={s} rows={[
          ["Faults detected (recall)", (x) => pct(x.detection.recall)],
          ["Alerts that were real (precision)", (x) => pct(x.detection.precision)],
          ["False alarms on healthy runs", (x) => pct(x.detection.false_positive_rate)],
          ["Median time to detect", (x) => sec(x.detection.median_mttd_s)],
          ["Median time to detect, gradual faults", (x) => sec(x.detection.median_mttd_gradual_s)],
          ["Root cause right first time (top-1)", (x) => pct(x.rca.top1)],
          ["Root cause in top 3", (x) => pct(x.rca.top3)],
          ["007 voting alone (top-1)", (x) => pct(x.rca.voting_007_top1)],
        ]} />
        <ul className="glass mt-4 list-disc space-y-2 p-6 pl-10 text-sm text-fg-muted">
          <li>Reactive rules can recover a few more faults: they ignore the blast-radius guardrail (at most 5 flows moved automatically), for example moving every flow off a flapping internet uplink at once. NetHeal hands those to a human on purpose.</li>
          <li>An overloaded access switch has no detour (the traffic starts there), so the rules escalate it. The RL agent sometimes mitigates it instead, moving the switch&apos;s flows onto less-loaded paths further up.</li>
          <li>Without the RL agent no fix is rolled back: in the simulator every detour around the fault works. The agent&apos;s mitigations are closer calls; some pass the twin but fail the 3 s check and are rolled back, ending no worse than without it.</li>
          <li>A mitigation of a gradually worsening overload can pass its check and break later. NetHeal does not re-plan after a verified fix yet, which is why the RL policy heals more faults than it keeps recovered.</li>
          <li>Prediction detects gradual faults earlier; diagnosing that early occasionally names the wrong cause first, which is corrected before anything is applied.</li>
        </ul>
        <p className="mt-3 text-xs text-fg-muted">
          Every policy is judged on the same faults: those that broke the SLA without healing. A flow breaks its SLA when loss is above 2% or latency more than doubles. Reactive rules apply the first detour without testing it on the twin or checking the safety rules; every policy still verifies a fix and rolls it back if it fails. Regenerate with ./netheal eval.
        </p>
      </section>
    </div>
  );
}
