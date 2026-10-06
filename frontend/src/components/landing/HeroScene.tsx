"use client";

import { Environment, Lightformer, MeshDistortMaterial, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { type ComponentRef, type RefObject, useMemo, useRef, useState } from "react";
import { type InstancedMesh, type Mesh, Object3D, Vector3 } from "three";
import { useTheme } from "@/components/ThemeToggle";

const HOME = new Vector3(0, -3.2, 0);
const RADIUS = 2.6;
const REACH = 1.6; // how close (beyond the surface) the cursor must come before the blob shies away
const MAX_SHIFT = 0.6;
// The blob's centre is below the screen, so the cursor is always above it: slide mostly
// sideways and only dip a little, or it would sink out of view and could never be touched.
const DIRECTION = new Vector3(1, 0.35, 0);
const HOLD_S = 2; // seconds on the blob before it bursts
const MERGE_S = 1.4;
const DROPS = 60;

type Drop = { dir: Vector3; depth: number; size: number; speed: number; wobble: number; pos: Vector3; vel: Vector3; from: Vector3 };

function makeDrops(): Drop[] {
  return Array.from({ length: DROPS }, () => ({
    // Mostly up and sideways, so the droplets fly into view rather than below the screen.
    dir: new Vector3(Math.random() * 2 - 1, 0.15 + Math.random() * 0.9, (Math.random() * 2 - 1) * 0.6).normalize(),
    depth: 0.5 + Math.random() * 0.4, // starts somewhere inside the blob, not all on its skin
    size: 0.06 + Math.random() ** 2 * 0.34, // mostly small droplets, a few big ones
    speed: 2 + Math.random() * 7,
    wobble: Math.random() * Math.PI * 2,
    pos: new Vector3(),
    vel: new Vector3(),
    from: new Vector3(),
  }));
}

const smooth = (x: number) => {
  const t = Math.min(1, Math.max(0, x));
  return t * t * (3 - 2 * t);
};

/** Glossy liquid-metal blob rising from the bottom of a starfield (Dribbble reference).
 * It shies away from the cursor like a repelling magnet and shivers while the cursor is on it.
 * Held on it for 2 s, it bursts into droplets; when the cursor leaves, they merge back. */
function Blob({ inside }: { inside: RefObject<boolean> }) {
  const light = useTheme() === "light";
  const ref = useRef<Mesh>(null);
  const material = useRef<ComponentRef<typeof MeshDistortMaterial>>(null);
  const drops = useRef<InstancedMesh>(null);
  const hovered = useRef(false);
  const target = useRef(new Vector3());
  const state = useRef({ phase: "whole" as "whole" | "burst" | "merging", hover: 0, since: 0 });
  const [data] = useState(makeDrops);
  const dummy = useMemo(() => new Object3D(), []);

  useFrame(({ clock, pointer, viewport }, delta) => {
    const mesh = ref.current;
    if (!mesh || !material.current || !drops.current) return;
    const t = clock.elapsedTime;
    const s = state.current;
    s.since += delta;
    mesh.rotation.y = t * 0.15 + pointer.x * 0.3;
    mesh.rotation.x = pointer.y * 0.15;
    const cursor = new Vector3((pointer.x * viewport.width) / 2, (pointer.y * viewport.height) / 2, 0);

    if (s.phase === "whole") {
      s.hover = hovered.current ? s.hover + delta : 0;
      if (s.hover >= HOLD_S) {
        s.phase = "burst";
        s.since = 0;
        hovered.current = false;
        for (const d of data) {
          d.pos.copy(mesh.position).addScaledVector(d.dir, RADIUS * d.depth);
          d.vel.copy(d.dir).multiplyScalar(d.speed);
        }
      }
    } else if (s.phase === "burst") {
      const onBlob = inside.current && cursor.distanceTo(HOME) < RADIUS + 0.4;
      if (!onBlob && s.since > 0.8) {
        s.phase = "merging";
        s.since = 0;
        for (const d of data) d.from.copy(d.pos);
      }
    } else if (s.since >= MERGE_S) {
      s.phase = "whole";
      s.hover = 0;
    }

    if (s.phase === "whole") {
      // Push away from the cursor, harder the closer it gets to the surface.
      const away = HOME.clone().sub(cursor);
      const gap = away.length() - RADIUS;
      const push = Math.max(0, 1 - gap / REACH) * MAX_SHIFT;
      target.current.copy(HOME).add(away.normalize().multiply(DIRECTION).multiplyScalar(push));
      mesh.position.lerp(target.current, 1 - Math.exp(-delta * 6));

      // Shiver on hover, harder as the burst gets close.
      const shake = hovered.current ? 0.012 + 0.03 * (s.hover / HOLD_S) : 0;
      material.current.distort += ((hovered.current ? 0.6 : 0.35) - material.current.distort) * (1 - Math.exp(-delta * 8));
      mesh.scale.setScalar(RADIUS * (1 + shake * Math.sin(t * 55)));
      mesh.position.x += shake * 1.6 * Math.sin(t * 47);
    } else {
      // Burst: the blob pops at once. Merging: it grows back once the droplets are close.
      mesh.position.copy(HOME);
      const grow = s.phase === "burst" ? 1 - smooth(s.since / 0.12) : smooth((s.since - MERGE_S * 0.25) / (MERGE_S * 0.75));
      mesh.scale.setScalar(Math.max(RADIUS * grow, 0.001));
    }
    mesh.visible = mesh.scale.x > 0.01;

    drops.current.visible = s.phase !== "whole";
    if (s.phase === "whole") return;
    data.forEach((d, i) => {
      let size = d.size;
      if (s.phase === "burst") {
        d.vel.multiplyScalar(Math.exp(-delta * 2.2)); // fly out, then drift to a float
        d.pos.addScaledVector(d.vel, delta);
        d.pos.y += Math.sin(t * 1.5 + d.wobble) * 0.003;
      } else {
        const k = s.since / MERGE_S;
        d.pos.lerpVectors(d.from, target.current.copy(HOME).addScaledVector(d.dir, RADIUS * 0.85), smooth(k / 0.75));
        size *= 1 - smooth((k - 0.5) / 0.5);
      }
      dummy.position.copy(d.pos);
      dummy.scale.setScalar(size);
      dummy.updateMatrix();
      drops.current!.setMatrixAt(i, dummy.matrix);
    });
    drops.current.instanceMatrix.needsUpdate = true;
  });

  const surface = {
    color: light ? "#8fb0d6" : "#4f77a5",
    metalness: light ? 0.25 : 0.65, // less mirror in light mode, so the navy reflections don't darken it
    roughness: 0.2,
    clearcoat: 1,
  };
  return (
    <>
      <mesh
        ref={ref}
        position={HOME}
        scale={RADIUS}
        onPointerOver={() => (hovered.current = true)}
        onPointerOut={() => (hovered.current = false)}
      >
        <sphereGeometry args={[1, 128, 128]} />
        <MeshDistortMaterial ref={material} {...surface} distort={0.35} speed={1.4} />
      </mesh>
      <instancedMesh ref={drops} args={[undefined, undefined, DROPS]} visible={false} frustumCulled={false}>
        <sphereGeometry args={[1, 32, 32]} />
        <MeshDistortMaterial {...surface} distort={0.3} speed={3} />
      </instancedMesh>
    </>
  );
}

export default function HeroScene() {
  const inside = useRef(false); // is the cursor over the hero at all?
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 45 }}
      dpr={[1, 2]}
      onPointerMove={() => (inside.current = true)}
      onPointerLeave={() => (inside.current = false)}
    >
      <Stars radius={60} depth={40} count={2500} factor={3} fade speed={0.6} />
      <ambientLight intensity={0.4} />
      <directionalLight position={[0, 4, 5]} intensity={2.5} color="#c1e8ff" />
      <pointLight position={[-4, -1, 3]} intensity={30} color="#5483b3" />
      <Blob inside={inside} />
      {/* Local light formers instead of an HDR download, so it works offline. */}
      <Environment resolution={256}>
        <Lightformer intensity={3} color="#c1e8ff" position={[0, 5, -5]} scale={[10, 2, 1]} />
        <Lightformer intensity={2} color="#c1e8ff" position={[0, 3, 5]} scale={[8, 1.5, 1]} />
        <Lightformer intensity={2} color="#7da0ca" position={[-5, 0, 2]} scale={[2, 8, 1]} />
        <Lightformer intensity={1.5} color="#052659" position={[5, -2, 2]} scale={[2, 8, 1]} />
      </Environment>
    </Canvas>
  );
}
