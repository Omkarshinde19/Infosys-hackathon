"use client";

import * as echarts from "@/lib/charts";
import { FlaskConical, HeartPulse, Search, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { QueryState } from "@/components/dashboard/QueryState";
import { useQuery } from "@/lib/query";
import { useReducedMotion } from "@/lib/motion";

const POLICIES = ["no_heal", "reactive", "guarded_reactive", "native_shortest", "twin", "predictive_twin", "rl"] as const;
type Policy = (typeof POLICIES)[number];
const LABEL: Record<Policy, string> = {
  no_heal: "No healing",
  reactive: "Reactive rules",
  twin: "NetHeal (twin)",
  predictive_twin: "NetHeal + prediction",
  rl: "NetHeal + RL policy",
  guarded_reactive: "Guarded reactive rules",
  native_shortest: "Shortest-path routing",
};
const COLOR: Record<Policy, string> = { no_heal: "#f2919f", reactive: "#f2c77b", guarded_reactive: "#eda76b", native_shortest: "#93c5fd", twin: "#7da0ca", predictive_twin: "#6fd6c4", rl: "#b8a1e3" };
const FAULT_LABEL: Record<string, string> = {
  link_down: "Link down", gray_failure: "Gray failure", congestion: "Congestion",
  flapping: "Flapping link", node_overload: "Overloaded device", misconfig: "Misconfiguration",
};

type Summary = {
  scenarios: number;
  faults: number;
  healthy: number;
  detection: {
    precision: number | null; recall: number | null; f1: number | null; false_positive_rate: number | null; median_mttd_s: number | null; median_mttd_gradual_s: number | null;
  };
  rca: { top1: number | null; top3: number | null; voting_007_top1: number | null; diagnosed_faults?: number; coverage?: number; top1_over_all_faults?: number; top1_given_diagnosis?: number };
  healing: {
    sla_impacting_faults: number; recovered_rate: number | null; median_recovery_s: number | null; healed_rate: number | null;
    median_mttr_s: number | null; rollback_rate: number | null; escalated_rate: number | null;
    applied_faults?: number; relapsed_faults?: number; collateral_breach_faults?: number; recovered_rate_ci95?: [number, number];
  };
  sla: { violation_s_total: number; median_violation_s: number | null; p95_latency_ms: number | null; median_run_p95_latency_ms?: number | null; mean_loss_pct: number | null };
};
type Run = { policy: Policy; fault: { type: string } | null; sla_impact: boolean; recovery_s: number | null; mttr_s: number | null };
type Delta = { mean: number | null; ci95: [number, number] | null; paired_scenarios: number };
type Comparison = { recovered_rate_delta: Delta; violation_s_delta: Delta; flow_violation_s_delta: Delta };
type Results = {
  meta: { scenarios: number; run_s: number; generated_at?: string; [key: string]: unknown };
  summary: { policies: Record<Policy, Summary>; by_fault: Record<string, Record<Policy, Summary>>; paired_vs_no_heal?: Partial<Record<Policy, Comparison>> };
  runs: Run[];
  stress?: { meta: Results["meta"]; summary: Results["summary"]; runs: Run[] } | null;
};

const pct = (v: number | null) => (v == null ? "n/a" : `${Math.round(v * 100)}%`);
const sec = (v: number | null) => (v == null ? "n/a" : `${v.toFixed(1)} s`);
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
function delta(value: Delta, percent: boolean) {
  const format = (number: number) => percent ? `${(number * 100).toFixed(1)} pp` : `${number.toFixed(1)} s`;
  return value.mean === null ? "n/a" : `${format(value.mean)}${value.ci95 ? ` [${format(value.ci95[0])}, ${format(value.ci95[1])}]` : " · interval unavailable"}`;
}

/** An ECharts chart in a glass card; the toolbox saves it as a PNG for slides. */
function Chart({ option, className = "h-80" }: { option: echarts.EChartsOption; className?: string }) {
  const el = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);
  const currentOption = useRef(option);
  const reducedMotion = useReducedMotion();
  useEffect(() => {
    const chart = echarts.init(el.current!, null, { renderer: "canvas" });
    instance.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(el.current!);
    const theme = new MutationObserver(() => draw(chart, currentOption.current));
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { observer.disconnect(); theme.disconnect(); chart.dispose(); instance.current = null; };
  }, []);
  useEffect(() => {
    currentOption.current = { ...option, animation: !reducedMotion };
    if (instance.current) draw(instance.current, currentOption.current);
  }, [option, reducedMotion]);
  return <div role="img" aria-label="Saved evaluation chart. Exact rates and denominator counts are available in the tables below." ref={el} className={`glass p-4 ${className}`} />;
}

function draw(chart: echarts.ECharts, option: echarts.EChartsOption) {
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
    }, { notMerge: true });
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
  const policies = POLICIES.filter((policy) => s[policy]);
  return (
    <div className="glass overflow-x-auto p-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-fg-muted">
            <th className="p-3 font-medium" />
            {policies.map((p) => (
              <th key={p} className="p-3 font-medium"><span className="mr-2 inline-block size-2 rounded-full" style={{ background: COLOR[p] }} />{LABEL[p]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, f]) => (
            <tr key={label} className="border-t border-[var(--glass-border)]">
              <td className="p-3">{label}</td>
              {policies.map((p) => <td key={p} className="p-3 tabular-nums">{f(s[p])}</td>)}
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
  const query = useQuery<Results>("/api/evaluation");
  const data = query.data;
  const charts = useMemo((): echarts.EChartsOption[] | null => {
    if (!data) return null; // data only arrives in the browser, so css() can read the theme
    const s = data.summary.policies;
    const policies = POLICIES.filter((policy) => s[policy]);
    const types = Object.keys(data.summary.by_fault);
    const edges = [0, 5, 10, 15, 20, 30, 45, Infinity];
    const impact = data.runs.filter((r) => r.fault && r.sla_impact);
    return [
      {
        xAxis: { type: "category", data: types.map((t) => FAULT_LABEL[t] ?? t) },
        yAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
        tooltip: { trigger: "axis", valueFormatter: (v) => `${v}%` },
        series: policies.map((p) => ({
          name: LABEL[p], type: "bar", itemStyle: { color: COLOR[p], borderRadius: [4, 4, 0, 0] },
          data: types.map((t) => { const rate = data.summary.by_fault[t][p].healing.recovered_rate; return rate === null ? null : Math.round(rate * 100); }),
        })),
      },
      {
        xAxis: { type: "category", data: policies.map((p) => LABEL[p]) },
        yAxis: { type: "value", name: "seconds", nameTextStyle: { color: css("--fg-muted") } },
        legend: { show: false },
        series: [{
          type: "bar", barWidth: "45%",
          data: policies.map((p) => ({ value: s[p].sla.violation_s_total, itemStyle: { color: COLOR[p], borderRadius: [4, 4, 0, 0] } })),
          label: { show: true, position: "top", color: css("--fg"), formatter: (x) => `${Math.round(Number(x.value))} s` },
        }],
      },
      {
        xAxis: { type: "category", data: edges.slice(0, -1).map((e, i) => (i === edges.length - 2 ? `${e}+ s` : `${e} to ${edges[i + 1]} s`)) },
        yAxis: { type: "value", name: "faults", nameTextStyle: { color: css("--fg-muted") } },
        series: policies.filter((p) => p !== "no_heal").map((p) => ({
          name: LABEL[p], type: "bar", itemStyle: { color: COLOR[p], borderRadius: [4, 4, 0, 0] },
          data: histogram(impact.filter((r) => r.policy === p && r.mttr_s != null).map((r) => r.mttr_s!), edges),
        })),
      },
    ];
  }, [data]);

  if (!data || !charts) return <QueryState {...query} />;
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
          {data.meta.scenarios} saved simulated scenarios, including healthy controls, each replayed under {Object.keys(data.summary.policies).length} policies for {data.meta.run_s} s.
          Same network, same fault, same random seed: the only difference is how the network responds.
        </p>
      </header>
      <details className="glass p-4 text-xs text-fg-muted"><summary className="cursor-pointer font-medium">Saved run provenance and evaluation settings</summary><pre className="mt-3 overflow-auto whitespace-pre-wrap">{JSON.stringify(data.meta, null, 2)}</pre><p className="mt-2">These scores describe this saved run. They are independent of the current dashboard state. Fields absent from the metadata are unrecorded.</p></details>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><HeartPulse className="size-5" /> Headline</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Back within SLA" value={pct(ours.healing.recovered_rate)} hint={`vs ${pct(none.healing.recovered_rate)} without healing (${ours.healing.sla_impacting_faults} faults that hurt users)${ours.healing.recovered_rate_ci95 ? ` · 95% interval ${pct(ours.healing.recovered_rate_ci95[0])}–${pct(ours.healing.recovered_rate_ci95[1])}` : " · interval unrecorded"}`} />
          <Stat label="Median time to heal" value={sec(ours.healing.median_mttr_s)} hint={`successful verified fixes only · ${data.runs.filter((run) => run.policy === "rl" && run.sla_impact && run.mttr_s !== null).length} measured impacted runs`} />
          <Stat label="SLA violation avoided" value={pct(saved)} hint={`${Math.round(ours.sla.violation_s_total)} s vs ${Math.round(none.sla.violation_s_total)} s without healing`} />
          <Stat label="False alarms" value={pct(ours.detection.false_positive_rate)} hint={`on ${ours.healthy} healthy runs`} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><ShieldCheck className="size-5" /> Recovered, by fault type</h2>
        <Chart option={charts[0]} />
        <p className="mt-2 text-xs text-fg-muted">A missing bar means no applicable measurement; it is not zero recovery. Each fault type uses its baseline SLA-impacting runs as the denominator.</p>
      </section>

      {data.summary.paired_vs_no_heal && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Paired differences versus no healing</h2>
          <p className="mb-3 text-xs text-fg-muted">Scenario-level paired bootstrap intervals. A recovery difference is in percentage points; a negative violation-time difference means fewer seconds of harm. Intervals spanning zero do not establish a directional improvement.</p>
          <div className="glass overflow-x-auto p-2"><table className="w-full text-sm"><thead className="text-left text-xs text-fg-muted"><tr><th className="p-3">Policy</th><th className="p-3">Recovery difference [95% interval]</th><th className="p-3">Violation time difference [95% interval]</th><th className="p-3">Paired scenarios</th></tr></thead><tbody>
            {POLICIES.filter((policy) => data.summary.paired_vs_no_heal?.[policy]).map((policy) => {
              const comparison = data.summary.paired_vs_no_heal![policy]!;
              return <tr key={policy} className="border-t border-[var(--glass-border)]"><td className="p-3">{LABEL[policy]}</td><td className="p-3 tabular-nums">{delta(comparison.recovered_rate_delta, true)}</td><td className="p-3 tabular-nums">{delta(comparison.violation_s_delta, false)}</td><td className="p-3 tabular-nums">{comparison.recovered_rate_delta.paired_scenarios}</td></tr>;
            })}
          </tbody></table></div>
        </section>
      )}

      <section className="grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-lg font-semibold">Total time users were hurt</h2>
          <Chart option={charts[1]} />
        </div>
        <div>
          <h2 className="mb-3 text-lg font-semibold">How fast fixes land (MTTR)</h2>
          <Chart option={charts[2]} />
          <p className="mt-2 text-xs text-fg-muted">Successful verified fixes only. Unhealed runs and missing MTTR values are excluded; the last bin includes all durations of 45 s or more.</p>
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><FlaskConical className="size-5" /> Healing</h2>
        <Table s={s} rows={[
          ["All simulated fault runs", (x) => String(x.faults)],
          ["Healthy control runs", (x) => String(x.healthy)],
          ["Faults that hurt users", (x) => String(x.healing.sla_impacting_faults)],
          ["Recovered (SLA met, last 10 s)", (x) => pct(x.healing.recovered_rate)],
          ["Median time to recover", (x) => sec(x.healing.median_recovery_s)],
          ["Healed by a verified fix", (x) => pct(x.healing.healed_rate)],
          ["Median MTTR", (x) => sec(x.healing.median_mttr_s)],
          ["Fixes rolled back", (x) => pct(x.healing.rollback_rate)],
          ["Escalated to a human", (x) => pct(x.healing.escalated_rate)],
          ["Faults with an applied fix", (x) => x.healing.applied_faults == null ? "unrecorded" : String(x.healing.applied_faults)],
          ["Relapsed after verification", (x) => x.healing.relapsed_faults == null ? "unrecorded" : String(x.healing.relapsed_faults)],
          ["Collateral service breaches", (x) => x.healing.collateral_breach_faults == null ? "unrecorded" : String(x.healing.collateral_breach_faults)],
          ["Median of each run's p95 latency", (x) => (x.sla.median_run_p95_latency_ms ?? x.sla.p95_latency_ms) == null ? "n/a" : `${x.sla.median_run_p95_latency_ms ?? x.sla.p95_latency_ms} ms`],
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
          ["Faults with a diagnosis", (x) => x.rca.diagnosed_faults == null ? "unrecorded" : String(x.rca.diagnosed_faults)],
          ["Diagnosis coverage over all faults", (x) => pct(x.rca.coverage ?? null)],
          ["Root cause right over all faults", (x) => pct(x.rca.top1_over_all_faults ?? null)],
          ["Root cause right given a diagnosis", (x) => pct(x.rca.top1_given_diagnosis ?? x.rca.top1)],
          ["Root cause in top 3", (x) => pct(x.rca.top3)],
          ["007 voting alone (top-1)", (x) => pct(x.rca.voting_007_top1)],
        ]} />
        <div className="glass mt-4 space-y-2 p-6 text-sm text-fg-muted">
          <p>These policies share one simulator. Their measured differences support comparisons within this saved experiment; they do not establish performance on physical infrastructure.</p>
          <p>Recovery, successful verification, relapse and collateral harm are separate outcomes. A successful verification can be followed by relapse; a recovery can occur without a healing action.</p>
          <p>Original training lineage is not assumed. Check the saved metadata for source and model hashes, seeds, service thresholds and the evaluator&apos;s recorded scope.</p>
        </div>
        <p className="mt-3 text-xs text-fg-muted">
          Recovery comparisons use the same scenarios that violated service objectives without healing. The saved service definition and recovery/verification windows are shown in provenance above. Old runs with no recorded definition retain that limitation. Regenerate with ./netheal eval.
        </p>
      </section>

      {data.stress && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Unmodeled plant disturbance cohort</h2>
          <p className="mb-3 text-sm text-fg-muted">A separate experiment injects observational delay that the twin does not model. Its control runs also experience disturbance, so they cannot support healthy-negative precision or false-alarm estimates. Keep this cohort separate from the nominal headline.</p>
          <Table s={data.stress.summary.policies} rows={[
            ["Baseline-impacting disturbed scenarios", (x) => String(x.healing.sla_impacting_faults)],
            ["Recovered", (x) => pct(x.healing.recovered_rate)],
            ["Applied fixes", (x) => String(x.healing.applied_faults ?? "unrecorded")],
            ["Relapses", (x) => String(x.healing.relapsed_faults ?? "unrecorded")],
            ["Collateral breaches", (x) => String(x.healing.collateral_breach_faults ?? "unrecorded")],
            ["Healthy-control false alarm estimate", (x) => pct(x.detection.false_positive_rate)],
          ]} />
          <details className="glass mt-3 p-4 text-xs text-fg-muted"><summary className="cursor-pointer">Disturbance configuration and provenance</summary><pre className="mt-3 overflow-auto whitespace-pre-wrap">{JSON.stringify(data.stress.meta, null, 2)}</pre></details>
        </section>
      )}
    </div>
  );
}
