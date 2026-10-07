"use client";

import {
  Activity,
  BarChart3,
  BellRing,
  ClipboardCheck,
  FlaskRound,
  MessageSquareText,
  Settings,
  FileText,
  FlaskConical,
  Gauge,
  HeartPulse,
  Home,
  LineChart,
  LogIn,
  LogOut,
  Menu,
  Network,
  ScrollText,
  Scale,
  Stethoscope,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";
import { useLive } from "@/lib/live";

const SECTIONS = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "alerts", label: "Alerts", icon: BellRing },
  { id: "diagnosis", label: "Diagnosis", icon: Stethoscope },
  { id: "healing", label: "Healing", icon: HeartPulse },
  { id: "network", label: "Network", icon: Network },
  { id: "telemetry", label: "Telemetry", icon: LineChart },
  { id: "faults", label: "Fault Lab", icon: FlaskConical },
];

/** Highlights whichever section is currently in view. */
function useActiveSection(pathname: string) {
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
  }, [pathname]);
  return active;
}

function subscribeDesktop(listener: () => void) {
  const media = window.matchMedia("(min-width: 768px)");
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}
const desktopSnapshot = () => window.matchMedia("(min-width: 768px)").matches;
const serverSnapshot = () => false;

export function Sidebar() {
  const pathname = usePathname();
  const active = useActiveSection(pathname);
  const status = useLive((s) => s.dataStatus);
  const alertCount = useLive((s) => Object.keys(s.anomalies).length);
  const backend = useLive((s) => s.backend);
  const desktop = useSyncExternalStore(subscribeDesktop, desktopSnapshot, serverSnapshot);
  const panel = useRef<HTMLElement>(null);
  const waiting = useLive((s) => s.incident.awaiting !== null);
  const [open, setOpen] = useState(false); // phones: the sidebar slides in from the left
  const [shownFor, setShownFor] = useState(pathname);
  if (shownFor !== pathname) {  // navigated: close the menu
    setShownFor(pathname);
    setOpen(false);
  }
  const session = useAuth((s) => s.session);
  const logout = useAuth((s) => s.logout);
  const checking = useAuth((s) => s.checking);
  useEffect(() => {
    if (!open || desktop) return;
    const previous = document.activeElement as HTMLElement | null;
    const main = document.getElementById("dashboard-main");
    const assistant = document.getElementById("dashboard-assistant");
    const assistantVisibility = assistant?.style.visibility ?? "";
    const previousOverflow = document.body.style.overflow;
    if (main) main.inert = true;
    if (assistant) { assistant.inert = true; assistant.style.visibility = "hidden"; }
    document.body.style.overflow = "hidden";
    const focusable = () => [...(panel.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), select, input, [tabindex="0"]') ?? [])].filter((element) => element.getClientRects().length);
    focusable()[0]?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); setOpen(false); }
      if (event.key !== "Tab") return;
      const elements = focusable();
      const first = elements[0]; const last = elements.at(-1);
      if (event.shiftKey && (document.activeElement === first || !panel.current?.contains(document.activeElement))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !panel.current?.contains(document.activeElement))) { event.preventDefault(); first?.focus(); }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      if (main) main.inert = false;
      if (assistant) { assistant.inert = false; assistant.style.visibility = assistantVisibility; }
      document.body.style.overflow = previousOverflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [open, desktop]);
  const pages = [
    { href: "/dashboard/copilot", label: "Ask NetHeal", icon: MessageSquareText, badge: false },
    { href: "/dashboard/whatif", label: "What If planner", icon: FlaskRound, badge: false },
    { href: "/dashboard/incidents", label: "Incidents & reports", icon: FileText, badge: false },
    { href: "/dashboard/approvals", label: "Approvals", icon: ClipboardCheck, badge: waiting },
    { href: "/dashboard/insights", label: "Insights", icon: BarChart3, badge: false },
    { href: "/dashboard/evaluation", label: "Evaluation", icon: Scale, badge: false },
    { href: "/dashboard/audit", label: "Audit log", icon: ScrollText, badge: false },
    { href: "/dashboard/settings", label: "Settings", icon: Settings, badge: false },
  ];

  return (
    <>
    <header className="glass fixed inset-x-3 top-3 z-20 flex items-center justify-between rounded-2xl! px-4 py-2 md:hidden print:hidden">
      <Logo className="text-base" />
      <button onClick={() => setOpen(true)} aria-label="Open menu" aria-expanded={open} aria-controls="dashboard-navigation" className="grid size-9 place-items-center rounded-full hover:bg-[var(--glass-hover)]">
        <Menu className="size-5" />
      </button>
    </header>
    {open && <div onClick={() => setOpen(false)} className="fixed inset-0 z-20 bg-black/50 md:hidden" />}
    <aside id="dashboard-navigation" ref={panel} inert={!desktop && !open} role={!desktop && open ? "dialog" : undefined} aria-modal={!desktop && open ? true : undefined} aria-label="Dashboard navigation" className={`glass fixed inset-y-4 left-4 z-30 flex w-60 flex-col overflow-y-auto rounded-2xl! p-4 transition-transform md:translate-x-0 print:hidden ${open ? "translate-x-0 visible" : "-translate-x-[110%] invisible md:visible"}`}>
      <button onClick={() => setOpen(false)} aria-label="Close menu" className="absolute top-4 right-3 text-fg-muted hover:text-fg md:hidden">
        <X className="size-5" />
      </button>
      <Logo className="px-2 py-1 text-lg" />
      {backend && (
        <Link href="/dashboard/settings" className="mx-2 mt-2 w-fit rounded-full border border-[var(--glass-border)] px-2.5 py-0.5 text-[11px] text-fg-muted hover:text-fg">
          {backend === "emu" ? "Emulated · real packets" : "Simulated network"}
        </Link>
      )}

      <nav onClick={() => setOpen(false)} className="mt-8 flex flex-col gap-1 text-sm">
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
            <LogIn className="size-4" /> {checking ? "Checking saved session…" : "Sign in to take actions"}
          </Link>
        )}
      </div>
      <div className="flex items-center justify-between px-2">
        <span className="flex items-center gap-2 text-xs text-fg-muted">
          <span className={`size-2 rounded-full ${status === "fresh" ? "bg-healthy animate-pulse" : status === "learning" ? "bg-warning" : "bg-fg-muted"}`} />
          {status === "fresh" ? "Live · fresh" : status === "learning" ? "Learning baseline" : status === "stale" ? "Stale data" : "No data yet"}
        </span>
        <ThemeToggle />
      </div>
    </aside>
    </>
  );
}
