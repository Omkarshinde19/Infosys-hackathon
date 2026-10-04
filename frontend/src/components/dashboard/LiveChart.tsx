"use client";

import * as echarts from "echarts";
import { useEffect, useMemo, useRef } from "react";
import { type Sample, useLive } from "@/lib/live";

// Blues and soft tints that sit with the palette.
const SERIES_COLORS = ["#7da0ca", "#c1e8ff", "#5483b3", "#6fd6c4", "#a5b4fc", "#93c5fd", "#f2c77b", "#f2919f", "#b8a1e3"];

function css(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Live line chart: one series per flow for the given metric. */
export function LiveChart({ title, metric, unit }: { title: string; metric: keyof Sample; unit: string }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts>(null);
  const history = useLive((s) => s.history);
  const topology = useLive((s) => s.topology);
  const flowIds = useMemo(() => topology?.flows.map((f) => f.id), [topology]);

  useEffect(() => {
    chart.current = echarts.init(el.current!, null, { renderer: "canvas" });
    const observer = new ResizeObserver(() => chart.current?.resize());
    observer.observe(el.current!);
    return () => {
      observer.disconnect();
      chart.current?.dispose();
    };
  }, []);

  useEffect(() => {
    if (!chart.current || !flowIds) return;
    const muted = css("--fg-muted");
    const times = history.map((tick) => new Date(tick[0].ts).toLocaleTimeString());
    chart.current.setOption({
      animation: false,
      color: SERIES_COLORS,
      grid: { left: 48, right: 16, top: 40, bottom: 28 },
      title: { text: title, textStyle: { color: css("--fg"), fontSize: 14, fontWeight: 600 } },
      tooltip: { trigger: "axis", valueFormatter: (v: number) => `${v?.toFixed(2)} ${unit}` },
      legend: { type: "scroll", right: 0, top: 0, width: "65%", textStyle: { color: muted } },
      xAxis: { type: "category", data: times, axisLabel: { color: muted }, axisLine: { lineStyle: { color: muted } } },
      yAxis: {
        type: "value",
        name: unit,
        nameTextStyle: { color: muted },
        axisLabel: { color: muted },
        splitLine: { lineStyle: { color: css("--glass-border") } },
      },
      series: flowIds.map((id) => ({
        name: id,
        type: "line",
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.5 },
        data: history.map((tick) => tick.find((s) => s.entity_id === id)?.[metric] ?? null),
      })),
    });
  }, [history, flowIds, metric, title, unit]);

  return <div ref={el} className="glass h-80 p-4" />;
}
