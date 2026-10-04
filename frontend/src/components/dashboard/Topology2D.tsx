"use client";

import {
  Background,
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Building2, Globe, Router, Server } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { health, healthColor, nodeHealth } from "@/lib/health";
import { type Topology, useLive } from "@/lib/live";

const COLUMNS = { edge: 0, core: 1, distribution: 2, access: 3 } as const;
const ICONS = { edge: Globe, core: Router, distribution: Server, access: Building2 };
const COL_GAP = 300;
const ROW_GAP = 78;

type NetNodeData = { name: string; layer: keyof typeof COLUMNS; health: number; rootCause?: boolean };

function NetNode({ data }: NodeProps<Node<NetNodeData>>) {
  const Icon = ICONS[data.layer];
  const color = healthColor(data.health);
  return (
    <div
      className="glass flex items-center gap-2 rounded-full! py-1.5 pr-4 pl-1.5 text-xs"
      style={data.rootCause ? { borderColor: "var(--critical)", boxShadow: "0 0 18px var(--critical)" } : undefined}
    >
      <span className="grid size-7 place-items-center rounded-full" style={{ background: color, transition: "background 500ms" }}>
        <Icon className="size-3.5 text-[#021024]" />
      </span>
      <span className="font-medium whitespace-nowrap">{data.name}</span>
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <Handle type="source" position={Position.Right} className="opacity-0" />
      <Handle id="top" type="target" position={Position.Top} className="opacity-0" />
      <Handle id="bottom" type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
}

const nodeTypes = { net: NetNode };

function layout(topo: Topology): Node<NetNodeData>[] {
  const byLayer = Object.groupBy(topo.nodes, (n) => n.layer);
  const tallest = Math.max(...Object.values(byLayer).map((ns) => ns!.length));
  return topo.nodes.map((n) => {
    const column = byLayer[n.layer]!;
    const offset = ((tallest - column.length) * ROW_GAP) / 2;
    return {
      id: n.id,
      type: "net",
      position: { x: COLUMNS[n.layer] * COL_GAP, y: offset + column.indexOf(n) * ROW_GAP },
      data: { name: n.name, layer: n.layer, health: 1 },
      draggable: false,
    };
  });
}

export function Topology2D() {
  const topology = useLive((s) => s.topology);
  const latest = useLive((s) => s.latest);
  const rootCause = useLive((s) => s.diagnosis[0]?.target);
  const baseNodes = useMemo(() => (topology ? layout(topology) : []), [topology]);
  const wrapper = useRef<HTMLDivElement>(null);
  const [flow, setFlow] = useState<ReactFlowInstance<Node<NetNodeData>>>();

  // Refit when the panel changes size (e.g. a projector with a different resolution).
  useEffect(() => {
    if (!flow || !wrapper.current) return;
    const observer = new ResizeObserver(() => flow.fitView({ padding: 0.18 }));
    observer.observe(wrapper.current);
    return () => observer.disconnect();
  }, [flow]);

  if (!topology) return null;

  const nodes = baseNodes.map((n) => ({
    ...n,
    data: { ...n.data, health: nodeHealth(n.id, latest, topology.flows), rootCause: n.id === rootCause },
  }));
  const layers = Object.fromEntries(topology.nodes.map((n) => [n.id, n.layer]));
  const edges: Edge[] = topology.links.map((l) => {
    const s = latest[l.id];
    const down = s?.latency_ms === null;
    const sameColumn = layers[l.a] === layers[l.b];
    return {
      id: l.id,
      source: l.a,
      target: l.b,
      sourceHandle: sameColumn ? "bottom" : undefined,
      targetHandle: sameColumn ? "top" : undefined,
      animated: !down && (s?.throughput_mbps ?? 0) > 1,
      label: l.id === rootCause ? "root cause" : undefined,
      labelStyle: { fill: "var(--critical)", fontWeight: 600 },
      labelBgStyle: { fill: "var(--bg)" },
      style: {
        stroke: healthColor(health(s)),
        strokeWidth: 1.5 + Math.min(1, s?.util ?? 0) * 4,
        strokeDasharray: down ? "4 6" : undefined,
        opacity: down || (s?.throughput_mbps ?? 0) > 1 ? 1 : 0.35,
        transition: "stroke 500ms, stroke-width 500ms",
      },
    };
  });

  return (
    <div ref={wrapper} className="size-full">
    <ReactFlow
      onInit={setFlow}
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      proOptions={{ hideAttribution: true }}
      nodesConnectable={false}
      zoomOnScroll={false}
      preventScrolling={false}
      style={{ background: "transparent" }}
    >
      <Background color="var(--glass-border)" gap={24} />
    </ReactFlow>
    </div>
  );
}
