import type { Sample, Topology } from "./live";

/** 1 = perfectly healthy, 0 = down. Based on loss and utilisation. */
export function health(s: Sample | undefined): number | null {
  if (!s) return null;
  if (s.entity_type !== "node" && s.latency_ms === null) return 0;
  const utilisation = s.entity_type === "node" ? s.cpu : s.entity_type === "flow" ? 0 : s.util;
  if (s.entity_type !== "node" && !Number.isFinite(s.loss_pct)) return null;
  if (utilisation === null || !Number.isFinite(utilisation)) return null;
  const loss = (s.loss_pct ?? 0) / 10; // 10% loss = fully unhealthy
  const load = (utilisation - 0.7) / 0.3; // above 70% starts to hurt
  return 1 - Math.min(1, Math.max(0, loss, load));
}

/** Smooth blend healthy → warning → critical using the CSS status tokens. */
export function healthColor(h: number | null): string {
  if (h === null) return "var(--fg-muted)";
  const mix = (a: string, b: string, t: number) =>
    `color-mix(in oklab, var(${a}) ${Math.round((1 - t) * 100)}%, var(${b}))`;
  return h >= 0.5 ? mix("--healthy", "--warning", (1 - h) * 2) : mix("--warning", "--critical", 1 - h * 2);
}

export function healthLabel(h: number | null): string {
  if (h === null) return "Unknown";
  return h > 0.8 ? "Healthy" : h > 0.4 ? "Degraded" : "Critical";
}

/** A node is only as healthy as the worst traffic flow starting at it. */
export function nodeHealth(id: string, latest: Record<string, Sample>, flows: Topology["flows"]): number | null {
  const scores = [health(latest[id]), ...flows.filter((f) => f.src === id).map((f) => health(latest[f.id]))];
  return scores.some((score) => score === null) ? null : Math.min(...scores as number[]);
}

/** Overall score: mostly the average flow, but one dead building must drag it down. */
export function networkHealth(flowSamples: Sample[]): number | null {
  if (!flowSamples.length) return null;
  const hs = flowSamples.map(health);
  if (hs.some((score) => score === null)) return null;
  const scores = hs as number[];
  return 0.7 * (scores.reduce((a, b) => a + b, 0) / scores.length) + 0.3 * Math.min(...scores);
}
