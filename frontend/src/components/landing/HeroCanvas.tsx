"use client";

import { lazy, Suspense, useSyncExternalStore } from "react";

// WebGL only exists in the browser. Render it after hydration: next/dynamic's ssr:false
// placeholder intermittently failed hydration (React #418) on repeat visits.
const HeroScene = lazy(() => import("./HeroScene"));
const noop = () => () => {};

export function HeroCanvas() {
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  return mounted ? (
    <Suspense fallback={null}>
      <HeroScene />
    </Suspense>
  ) : null;
}
