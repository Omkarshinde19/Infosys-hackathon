"use client";

import {
  Activity,
  BellRing,
  ClipboardCheck,
  FileText,
  FlaskConical,
  Gauge,
  HeartPulse,
  Home,
  LineChart,
  LogIn,
  LogOut,
  Network,
  ScrollText,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";
import { useLive } from "@/lib/live";

export const SECTIONS = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "alerts", label: "Alerts", icon: BellRing },
  { id: "diagnosis", label: "Diagnosis", icon: Stethoscope },
  { id: "healing", label: "Self-healing", icon: HeartPulse },
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
  const alertCount = useLive((s) => Object.keys(s.anomalies).length);
  const pathname = usePathname();
  const waiting = useLive((s) => s.incident.awaiting !== null);
  const session = useAuth((s) => s.session);
  const logout = useAuth((s) => s.logout);
  const pages = [
    { href: "/dashboard/incidents", label: "Incidents & reports", icon: FileText, badge: false },
    { href: "/dashboard/approvals", label: "Approvals", icon: ClipboardCheck, badge: waiting },
    { href: "/dashboard/audit", label: "Audit log", icon: ScrollText, badge: false },
  ];

  return (
    <aside className="glass fixed inset-y-4 left-4 z-20 flex w-60 flex-col rounded-2xl! p-4 print:hidden">
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
            href={`/dashboard#${s.id}`}
            className={`flex items-center gap-3 rounded-xl px-3 py-2 transition-colors ${
              pathname === "/dashboard" && active === s.id ? "bg-[var(--glass-hover)] text-fg" : "text-fg-muted hover:text-fg"
            }`}
          >
            <s.icon className="size-4" /> {s.label}
            {s.id === "alerts" && alertCount > 0 && (
              <span className="ml-auto rounded-full bg-critical px-2 text-xs font-semibold text-[#021024]">{alertCount}</span>
            )}
          </a>
        ))}
        <div className="mt-4" />
        {pages.map((p) => (
          <Link
            key={p.href}
            href={p.href}
            className={`flex items-center gap-3 rounded-xl px-3 py-2 transition-colors ${
              pathname.startsWith(p.href) ? "bg-[var(--glass-hover)] text-fg" : "text-fg-muted hover:text-fg"
            }`}
          >
            <p.icon className="size-4" /> {p.label}
            {p.badge && <span className="ml-auto size-2 animate-pulse rounded-full bg-warning" />}
          </Link>
        ))}
      </nav>

      <div className="mt-auto mb-3 border-t border-[var(--glass-border)] px-2 pt-3 text-xs">
        {session ? (
          <div className="flex items-center justify-between">
            <span>
              <span className="font-medium text-fg">{session.username}</span>
              <span className="text-fg-muted"> · {session.role}</span>
            </span>
            <button onClick={logout} aria-label="Sign out" className="text-fg-muted hover:text-fg">
              <LogOut className="size-4" />
            </button>
          </div>
        ) : (
          <Link href="/login" className="flex items-center gap-2 text-fg-muted hover:text-fg">
            <LogIn className="size-4" /> Sign in to take actions
          </Link>
        )}
      </div>
      <div className="flex items-center justify-between px-2">
        <span className="flex items-center gap-2 text-xs text-fg-muted">
          <span className={`size-2 rounded-full ${connected ? "bg-healthy animate-pulse" : "bg-critical"}`} />
          {connected ? "Live" : "Offline"}
        </span>
        <ThemeToggle />
      </div>
    </aside>
  );
}
