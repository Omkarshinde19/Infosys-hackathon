"use client";

import { Environment, Lightformer, MeshDistortMaterial, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { type ComponentRef, useRef } from "react";
import { type Mesh, Vector3 } from "three";
import { useTheme } from "@/components/ThemeToggle";

const HOME = new Vector3(0, -3.2, 0);
const RADIUS = 2.6;
const REACH = 1.6; // how close (beyond the surface) the cursor must come before the blob shies away
const MAX_SHIFT = 0.6;
// The blob's centre is below the screen, so the cursor is always above it: slide mostly
// sideways and only dip a little, or it would sink out of view and could never be touched.
const DIRECTION = new Vector3(1, 0.35, 0);

/** Glossy liquid-metal blob rising from the bottom of a starfield (Dribbble reference).
 * It shies away from the cursor like a repelling magnet, and shivers while the cursor is on it. */
function Blob() {
  const light = useTheme() === "light";
  const ref = useRef<Mesh>(null);
  const material = useRef<ComponentRef<typeof MeshDistortMaterial>>(null);
  const hovered = useRef(false);
  const target = useRef(new Vector3());
  useFrame(({ clock, pointer, viewport }, delta) => {
    const mesh = ref.current;
    if (!mesh || !material.current) return;
    const t = clock.elapsedTime;
    mesh.rotation.y = t * 0.15 + pointer.x * 0.3;
    mesh.rotation.x = pointer.y * 0.15;

    // Push away from the cursor, harder the closer it gets to the surface.
    const cursor = new Vector3((pointer.x * viewport.width) / 2, (pointer.y * viewport.height) / 2, 0);
    const away = HOME.clone().sub(cursor);
    const gap = away.length() - RADIUS;
    const push = Math.max(0, 1 - gap / REACH) * MAX_SHIFT;
    target.current.copy(HOME).add(away.normalize().multiply(DIRECTION).multiplyScalar(push));
    mesh.position.lerp(target.current, 1 - Math.exp(-delta * 6));

    // Shiver on hover: stronger distortion plus a fast, small wobble.
    const shake = hovered.current ? 1 : 0;
    material.current.distort += ((hovered.current ? 0.6 : 0.35) - material.current.distort) * (1 - Math.exp(-delta * 8));
    mesh.scale.setScalar(RADIUS * (1 + shake * 0.012 * Math.sin(t * 55)));
    mesh.position.x += shake * 0.02 * Math.sin(t * 47);
  });
  return (
    <mesh
      ref={ref}
      position={HOME}
      scale={RADIUS}
      onPointerOver={() => (hovered.current = true)}
      onPointerOut={() => (hovered.current = false)}
    >
      <sphereGeometry args={[1, 128, 128]} />
      <MeshDistortMaterial
        ref={material}
        color={light ? "#8fb0d6" : "#4f77a5"}
        metalness={light ? 0.25 : 0.65} // less mirror in light mode, so the navy reflections don't darken it
        roughness={0.2}
        clearcoat={1}
        distort={0.35}
        speed={1.4}
      />
    </mesh>
  );
}

export default function HeroScene() {
  return (
    <Canvas camera={{ position: [0, 0, 6], fov: 45 }} dpr={[1, 2]}>
      <Stars radius={60} depth={40} count={2500} factor={3} fade speed={0.6} />
      <ambientLight intensity={0.4} />
      <directionalLight position={[0, 4, 5]} intensity={2.5} color="#c1e8ff" />
      <pointLight position={[-4, -1, 3]} intensity={30} color="#5483b3" />
      <Blob />
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
