import {
  Activity,
  ArrowRight,
  Building2,
  ChevronDown,
  FlaskConical,
  GraduationCap,
  Hospital,
  Map,
  MessageSquareText,
  Network,
  Radar,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { HeroCanvas } from "@/components/landing/HeroCanvas";
import { ApprovalShowcase, LoopShowcase } from "@/components/landing/Showcase";
import { Logo } from "@/components/Logo";
import { Reveal } from "@/components/Reveal";
import { ThemeToggle } from "@/components/ThemeToggle";

const steps = [
  { icon: Radar, title: "Watch", text: "Checks every link, device and flow twice a second." },
  { icon: Activity, title: "Notice", text: "Detects changes and service breaches in simulated telemetry." },
  { icon: Search, title: "Find the cause", text: "Ranks candidate causes against evidence and exposes uncertainty." },
  { icon: Wrench, title: "Fix safely", text: "Tests a candidate on the twin, checks policy and the selected comfort level, then verifies the result." },
  { icon: MessageSquareText, title: "Explain", text: "Writes a report from the recorded evidence and measured before / after values." },
];

const features = [
  { icon: Map, title: "Live network map", text: "Every building and connection, coloured by health, in 2D and 3D." },
  { icon: Activity, title: "Early warning", text: "Combines anomaly detectors and explicit service checks on simulated traffic." },
  { icon: Search, title: "Root cause with evidence", text: "A heuristic ranking score and the exact signals behind it." },
  { icon: FlaskConical, title: "Test before touching", text: "Healing candidates are evaluated on a copy of the simulated network." },
  { icon: SlidersHorizontal, title: "You stay in control", text: "Five comfort levels, from 'just tell me' to fully automatic." },
  { icon: ShieldCheck, title: "Tamper-evident audit", text: "Recorded decisions form a verifiable hash chain; integrity checks expose inconsistent history." },
];

const audiences = [
  { icon: GraduationCap, title: "Colleges", text: "Our campus simulator models buildings, labs and hostels." },
  { icon: Building2, title: "Enterprises", text: "A potential future use: evidence-based fault triage." },
  { icon: Hospital, title: "Hospitals", text: "A conceptual application requiring independent safety and infrastructure validation." },
  { icon: Network, title: "IT service providers", text: "A potential future use: supervised incident workflows." },
];

export default function Home() {
  return (
    <main className="relative overflow-x-clip">
      {/* Hero */}
      <section className="relative h-svh min-h-[640px] bg-[radial-gradient(ellipse_at_top,var(--bg-2),var(--bg)_65%)]">
        <div className="absolute inset-0">
          <HeroCanvas />
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-48 bg-gradient-to-b from-transparent to-bg" />

        <nav className="glass absolute inset-x-4 top-4 z-10 mx-auto flex max-w-6xl items-center justify-between rounded-full! px-5 py-2.5">
          <Logo />
          <div className="hidden items-center gap-8 text-sm text-fg-muted md:flex">
            <a href="#how" className="hover:text-fg">How it works</a>
            <a href="#features" className="hover:text-fg">Features</a>
            <a href="#who" className="hover:text-fg">Who it&apos;s for</a>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link href="/dashboard" className="rounded-full bg-fg px-4 py-2 text-sm font-medium text-bg hover:opacity-90">
              Open Control Room
            </Link>
          </div>
        </nav>

        <div className="pointer-events-none relative z-10 mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-6 pb-40 text-center">
          <Reveal>
            <h1 className="text-5xl font-semibold tracking-tight md:text-7xl">
              Networks that
              <br />
              heal themselves.
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-lg text-fg-muted">
              A campus network prototype that simulates detection, diagnosis and healing,
              then explains each recorded decision in plain English.
            </p>
            <p className="mt-3 text-xs text-fg-muted">NC-04 simulated demonstration · no live infrastructure changes · language models explain and report only</p>
            <div className="pointer-events-auto mt-8 flex justify-center gap-3">
              <Link href="/dashboard" className="flex items-center gap-2 rounded-full bg-fg px-6 py-3 font-medium text-bg hover:opacity-90">
                Open Control Room <ArrowRight className="size-4" />
              </Link>
              <a href="#how" className="glass rounded-full! px-6 py-3 font-medium hover:bg-[var(--glass-hover)]">
                See how it works
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto grid max-w-6xl scroll-mt-24 items-center gap-14 px-6 py-28 lg:grid-cols-2">
        <Reveal>
          <LoopShowcase />
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="text-3xl font-semibold md:text-4xl">The healing loop</h2>
          <p className="mt-3 max-w-md text-fg-muted">
            A measured detect → diagnose → decide → heal → verify loop, with human approval or escalation when required.
          </p>
          <div className="mt-8 space-y-3">
            {steps.map((s, i) => (
              <details key={s.title} name="loop" open={i === 0} className="glass group rounded-2xl! px-5 py-4">
                <summary className="flex cursor-pointer list-none items-center gap-3 [&::-webkit-details-marker]:hidden">
                  <s.icon className="size-5 shrink-0" />
                  <span className="text-lg font-medium">{s.title}</span>
                  <span className="ml-auto text-xs text-fg-muted">Step {i + 1}</span>
                  <ChevronDown className="size-4 text-fg-muted transition-transform group-open:rotate-180" />
                </summary>
                <p className="mt-2 pl-8 text-sm text-fg-muted">{s.text}</p>
              </details>
            ))}
          </div>
        </Reveal>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-24 bg-[radial-gradient(ellipse_at_center,var(--bg-2),transparent_70%)] px-6 py-28">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <h2 className="text-center text-3xl font-semibold md:text-4xl">Tools for understanding the healing loop</h2>
          </Reveal>
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 0.1}>
                <div className="glass h-full p-6 hover:bg-[var(--glass-hover)]">
                  <div className="mb-3 flex items-center gap-2">
                    <f.icon className="size-5" />
                    <h3 className="text-lg font-semibold">{f.title}</h3>
                  </div>
                  <p className="text-sm text-fg-muted">{f.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Safety promise */}
      <section className="mx-auto grid max-w-6xl items-center gap-14 px-6 py-20 lg:grid-cols-2">
        <Reveal>
          <ShieldCheck className="mb-4 size-8 text-healthy" />
          <h2 className="text-3xl font-semibold md:text-4xl">The language model explains. The controller follows policy.</h2>
          <p className="mt-4 max-w-lg text-fg-muted">
            The simulated controller detects, diagnoses, proposes and verifies changes according to
            safety rules and the selected comfort level. Unsuccessful changes trigger rollback;
            rollback failures are recorded and escalated. The language model only explains and reports from evidence.
          </p>
          <Link href="/dashboard/approvals" className="mt-8 inline-flex items-center gap-2 rounded-full bg-fg px-6 py-3 font-medium text-bg hover:opacity-90">
            See the approvals <ArrowRight className="size-4" />
          </Link>
        </Reveal>
        <Reveal delay={0.1}>
          <ApprovalShowcase />
        </Reveal>
      </section>

      {/* Who it's for */}
      <section id="who" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-20">
        <Reveal>
          <h2 className="text-center text-3xl font-semibold md:text-4xl">A campus prototype, with possible future applications</h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-fg-muted">The working demonstration uses simulated infrastructure. The other settings below are conceptual applications, not validated deployments.</p>
        </Reveal>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {audiences.map((a, i) => (
            <Reveal key={a.title} delay={i * 0.1}>
              <div className="glass h-full p-6">
                <a.icon className="mb-3 size-6" />
                <h3 className="font-semibold">{a.title}</h3>
                <p className="mt-1 text-sm text-fg-muted">{a.text}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 pt-10 pb-24">
        <Reveal>
          <div className="glass mx-auto max-w-4xl overflow-hidden p-12 text-center">
            <h2 className="text-3xl font-semibold md:text-4xl">Watch a network heal itself.</h2>
            <p className="mt-3 text-fg-muted">Inject a simulated fault and watch the evidence, proposed action and verified outcome update live.</p>
            <Link href="/dashboard" className="mt-8 inline-flex items-center gap-2 rounded-full bg-fg px-6 py-3 font-medium text-bg hover:opacity-90">
              Open Control Room <ArrowRight className="size-4" />
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-[var(--glass-border)] px-6 py-8 text-center text-sm text-fg-muted">
        <Logo className="mb-2 justify-center text-fg" />
        Team Syntax Cartel · Infosys ENG NEXT 2026 Hack-AI-Thon
      </footer>
    </main>
  );
}
