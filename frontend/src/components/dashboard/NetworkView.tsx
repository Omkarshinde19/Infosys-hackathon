"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { Topology2D } from "./Topology2D";

const Topology3D = dynamic(() => import("./Topology3DScene"), { ssr: false });

/** Network map with a 2D (layered, left → right) / 3D (strata) toggle. */
export function NetworkView() {
  const [mode, setMode] = useState<"2d" | "3d">("2d");
  const [loaded3D, setLoaded3D] = useState(false);
  // The 3D view stays mounted (hidden and paused in 2D): unmounting it made drei's <Html>
  // labels throw "removeChild ... not a child of this node".
  return (
    <div className="glass relative h-[640px] overflow-hidden">
      <div className="glass absolute top-4 right-4 z-10 flex rounded-full! p-1 text-sm">
        {(["2d", "3d"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); if (m === "3d") setLoaded3D(true); }}
            aria-pressed={mode === m}
            className={`rounded-full px-4 py-1.5 font-medium uppercase transition-colors ${
              mode === m ? "bg-fg text-bg" : "text-fg-muted hover:text-fg"
            }`}
          >
            {m}
          </button>
        ))}
      </div>
      <div className="absolute right-4 bottom-4 left-4 z-10 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
        {[["--healthy", "Healthy"], ["--warning", "Degraded"], ["--critical", "Critical"], ["--fg-muted", "Unknown / stale"]].map(([c, label]) => (
          <span key={c} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: `var(${c})` }} /> {label}
          </span>
        ))}
      </div>
      <div className={mode === "2d" ? "h-full" : "hidden"}>
        <Topology2D />
      </div>
      <div className={mode === "3d" ? "h-full" : "hidden"}>
        {loaded3D && <Topology3D active={mode === "3d"} />}
      </div>
    </div>
  );
}
