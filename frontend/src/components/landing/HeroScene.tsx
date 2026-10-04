"use client";

import { Environment, Lightformer, MeshDistortMaterial, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import type { Mesh } from "three";

/** Glossy liquid-metal blob rising from the bottom of a starfield (Dribbble reference). */
function Blob() {
  const ref = useRef<Mesh>(null);
  useFrame(({ clock, pointer }) => {
    if (!ref.current) return;
    ref.current.rotation.y = clock.elapsedTime * 0.15 + pointer.x * 0.3;
    ref.current.rotation.x = pointer.y * 0.15;
  });
  return (
    <mesh ref={ref} position={[0, -3.2, 0]} scale={2.6}>
      <sphereGeometry args={[1, 128, 128]} />
      <MeshDistortMaterial
        color="#7da0ca"
        metalness={0.6}
        roughness={0.18}
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
