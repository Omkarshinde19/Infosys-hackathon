"use client";

import { useLive } from "./live";

/** Human-readable names: "Distribution North A ↔ Library", "Library → Internet Gateway". */
export function useEntityName() {
  const topology = useLive((s) => s.topology);
  const node = (id: string) => topology?.nodes.find((n) => n.id === id)?.name ?? id;
  return (id: string) => {
    const link = topology?.links.find((l) => l.id === id);
    if (link) return `${node(link.a)} ↔ ${node(link.b)}`;
    const flow = topology?.flows.find((f) => f.id === id);
    if (flow) return `${node(flow.src)} → ${node(flow.dst)}`;
    return node(id);
  };
}
