import type { Sample, Topology } from "./live";

/** 1 = perfectly healthy, 0 = down. Based on loss and utilisation. */
export function health(s: Sample | undefined): number {
  if (!s) return 1;
  if (s.entity_type !== "node" && s.latency_ms === null) return 0;
  const loss = (s.loss_pct ?? 0) / 10; // 10% loss = fully unhealthy
  const load = ((s.util ?? s.cpu ?? 0) - 0.7) / 0.3; // above 70% starts to hurt
  return 1 - Math.min(1, Math.max(0, loss, load));
}

/** Smooth blend healthy → warning → critical using the CSS status tokens. */
export function healthColor(h: number): string {
  const mix = (a: string, b: string, t: number) =>
    `color-mix(in oklab, var(${a}) ${Math.round((1 - t) * 100)}%, var(${b}))`;
  return h >= 0.5 ? mix("--healthy", "--warning", (1 - h) * 2) : mix("--warning", "--critical", 1 - h * 2);
}

export function healthLabel(h: number): string {
  return h > 0.8 ? "Healthy" : h > 0.4 ? "Degraded" : "Critical";
}

/** A node is only as healthy as the worst traffic flow starting at it. */
export function nodeHealth(id: string, latest: Record<string, Sample>, flows: Topology["flows"]): number {
  return Math.min(health(latest[id]), ...flows.filter((f) => f.src === id).map((f) => health(latest[f.id])));
}

/** Overall score: mostly the average flow, but one dead building must drag it down. */
export function networkHealth(flowSamples: Sample[]): number {
  if (!flowSamples.length) return 1;
  const hs = flowSamples.map(health);
  return 0.7 * (hs.reduce((a, b) => a + b, 0) / hs.length) + 0.3 * Math.min(...hs);
}
