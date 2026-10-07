"use client";

import { lazy, Suspense, useSyncExternalStore } from "react";
import { useReducedMotion } from "@/lib/motion";

// WebGL only exists in the browser. Render it after hydration: next/dynamic's ssr:false
// placeholder intermittently failed hydration (React #418) on repeat visits.
const HeroScene = lazy(() => import("./HeroScene"));
const noop = () => () => {};

export function HeroCanvas() {
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  const reducedMotion = useReducedMotion();
  if (reducedMotion) return <div aria-hidden className="size-full bg-[radial-gradient(ellipse_at_center,var(--bg-2),transparent_65%)]" />;
  return mounted ? (
    <Suspense fallback={null}>
      <HeroScene />
    </Suspense>
  ) : null;
}
