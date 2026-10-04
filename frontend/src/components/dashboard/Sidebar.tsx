"use client";

import { Activity, FlaskConical, Gauge, Home, LineChart, Network } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useLive } from "@/lib/live";

export const SECTIONS = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "network", label: "Network", icon: Network },
  { id: "telemetry", label: "Telemetry", icon: LineChart },
  { id: "faults", label: "Fault Lab", icon: FlaskConical },
];

/** Highlights whichever section is currently in view. */
function useActiveSection() {
  const [active, setActive] = useState(SECTIONS[0].id);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: "-40% 0px -55% 0px" },
    );
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);
  return active;
}

export function Sidebar() {
  const active = useActiveSection();
  const connected = useLive((s) => s.connected);

  return (
    <aside className="glass fixed inset-y-4 left-4 z-20 flex w-60 flex-col rounded-2xl! p-4">
      <Logo className="px-2 py-1 text-lg" />

      <nav className="mt-8 flex flex-col gap-1 text-sm">
        <Link href="/" className="flex items-center gap-3 rounded-xl px-3 py-2 text-fg-muted hover:bg-[var(--glass-hover)] hover:text-fg">
          <Home className="size-4" /> Home
        </Link>
        <p className="mt-4 mb-1 flex items-center gap-2 px-3 text-xs tracking-wider text-fg-muted uppercase">
          <Activity className="size-3.5" /> Control Room
        </p>
        {SECTIONS.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className={`flex items-center gap-3 rounded-xl px-3 py-2 transition-colors ${
              active === s.id ? "bg-[var(--glass-hover)] text-fg" : "text-fg-muted hover:text-fg"
            }`}
          >
            <s.icon className="size-4" /> {s.label}
          </a>
        ))}
      </nav>

      <div className="mt-auto flex items-center justify-between px-2">
        <span className="flex items-center gap-2 text-xs text-fg-muted">
          <span className={`size-2 rounded-full ${connected ? "bg-healthy animate-pulse" : "bg-critical"}`} />
          {connected ? "Live" : "Offline"}
        </span>
        <ThemeToggle />
      </div>
    </aside>
  );
}
