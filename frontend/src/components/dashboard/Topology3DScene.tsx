"use client";

import { Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { Color, type Mesh, Vector3 } from "three";
import { health, nodeHealth } from "@/lib/health";
import { type Sample, type Topology, useLive } from "@/lib/live";

// "Network Strata": each network layer is a floating tier, Internet on top.
const TIERS = { edge: 3, core: 1.6, distribution: 0, access: -1.8 } as const;
const RADII = { edge: 0, core: 1.2, distribution: 2.4, access: 4 } as const;

function cssColor(name: string) {
  return new Color(getComputedStyle(document.documentElement).getPropertyValue(name).trim());
}

/** Same healthy → warning → critical blend as the 2D view, as a three.js colour. */
function statusColor(h: number) {
  const [ok, warn, bad] = ["--healthy", "--warning", "--critical"].map(cssColor);
  return h >= 0.5 ? ok.lerp(warn, (1 - h) * 2) : warn.lerp(bad, 1 - h * 2);
}

function positions(topo: Topology) {
  const byLayer = Object.groupBy(topo.nodes, (n) => n.layer);
  const pos: Record<string, Vector3> = {};
  for (const [layer, nodes] of Object.entries(byLayer)) {
    const key = layer as keyof typeof TIERS;
    nodes!.forEach((n, i) => {
      const angle = (i / nodes!.length) * Math.PI * 2 + (key === "access" ? Math.PI / 8 : 0);
      pos[n.id] = new Vector3(Math.cos(angle) * RADII[key], TIERS[key], Math.sin(angle) * RADII[key]);
    });
  }
  return pos;
}

/** A glowing packet that travels along a link; faster when the link is busier. */
function Packet({ from, to, util, color, offset }: {
  from: Vector3;
  to: Vector3;
  util: number;
  color: Color;
  offset: number;
}) {
  const ref = useRef<Mesh>(null);
  useFrame(({ clock }) => {
    const t = (clock.elapsedTime * (0.25 + util * 0.8) + offset) % 1;
    ref.current?.position.lerpVectors(from, to, t);
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.05, 12, 12]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

function Strata({ topo, latest }: { topo: Topology; latest: Record<string, Sample> }) {
  const pos = useMemo(() => positions(topo), [topo]);
  const tierLabels = { edge: "Internet", core: "Core", distribution: "Distribution", access: "Buildings" };

  return (
    <group>
      {(Object.keys(TIERS) as (keyof typeof TIERS)[]).map((layer) =>
        layer === "edge" ? null : (
          <group key={layer} position={[0, TIERS[layer] - 0.02, 0]}>
            <mesh rotation={[-Math.PI / 2, 0, 0]}>
              <ringGeometry args={[RADII[layer] - 0.6, RADII[layer] + 0.6, 64]} />
              <meshBasicMaterial color={cssColor("--accent-2")} transparent opacity={0.08} />
            </mesh>
            <Html position={[RADII[layer] + 0.9, 0, 0]} className="pointer-events-none text-[10px] tracking-widest text-fg-muted uppercase">
              {tierLabels[layer]}
            </Html>
          </group>
        ),
      )}

      {topo.links.map((l, i) => {
        const s = latest[l.id];
        const down = s?.latency_ms === null;
        const active = !down && (s?.throughput_mbps ?? 0) > 1;
        const color = statusColor(health(s));
        return (
          <group key={l.id}>
            <Line
              points={[pos[l.a], pos[l.b]]}
              color={color}
              lineWidth={active ? 1.5 + (s?.util ?? 0) * 3 : 1}
              transparent
              opacity={down || active ? 0.9 : 0.25}
              dashed={down}
              dashSize={0.15}
              gapSize={0.1}
            />
            {active && (
              <Packet from={pos[l.a]} to={pos[l.b]} util={s?.util ?? 0} color={color} offset={i / topo.links.length} />
            )}
          </group>
        );
      })}

      {topo.nodes.map((n) => (
        <group key={n.id} position={pos[n.id]}>
          <mesh>
            <sphereGeometry args={[n.layer === "edge" ? 0.35 : 0.2, 32, 32]} />
            <meshPhysicalMaterial
              color={statusColor(nodeHealth(n.id, latest, topo.flows))}
              emissive={statusColor(nodeHealth(n.id, latest, topo.flows))}
              emissiveIntensity={0.35}
              roughness={0.1}
              clearcoat={1}
              transparent
              opacity={0.9}
            />
          </mesh>
          <Html center position={[0, -0.38, 0]} className="pointer-events-none text-[10px] whitespace-nowrap text-fg">
            {n.name}
          </Html>
        </group>
      ))}
    </group>
  );
}

export default function Topology3DScene() {
  const topology = useLive((s) => s.topology);
  const latest = useLive((s) => s.latest);
  return (
    <Canvas camera={{ position: [8.5, 5, 8.5], fov: 45 }} dpr={[1, 2]}>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 8, 5]} intensity={1.5} />
      {topology && <Strata topo={topology} latest={latest} />}
      <OrbitControls target={[0, 0.3, 0]} autoRotate autoRotateSpeed={0.6} enableZoom={false} enablePan={false} />
    </Canvas>
  );
}
