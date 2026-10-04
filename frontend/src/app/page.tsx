import {
  Activity,
  ArrowRight,
  Building2,
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
import { Logo } from "@/components/Logo";
import { Reveal } from "@/components/Reveal";
import { ThemeToggle } from "@/components/ThemeToggle";

const steps = [
  { icon: Radar, title: "Watch", text: "Checks every link, device and flow twice a second." },
  { icon: Activity, title: "Notice", text: "Flags trouble early, before users start complaining." },
  { icon: Search, title: "Find the cause", text: "Names what broke and where, with the evidence." },
  { icon: Wrench, title: "Fix safely", text: "Tests the fix on a digital twin, then applies it." },
  { icon: MessageSquareText, title: "Explain", text: "Writes a plain-English report with before/after proof." },
];

const features = [
  { icon: Map, title: "Live network map", text: "Every building and connection, coloured by health, in 2D and 3D." },
  { icon: Activity, title: "Early warning", text: "Several detectors must agree, so your team isn't spammed." },
  { icon: Search, title: "Root cause with evidence", text: "A confidence score and the exact signals behind it." },
  { icon: FlaskConical, title: "Test before touching", text: "Every fix is tried on a virtual copy of your network first." },
  { icon: SlidersHorizontal, title: "You stay in control", text: "Five comfort levels, from 'just tell me' to fully automatic." },
  { icon: ShieldCheck, title: "Tamper-proof audit", text: "Every decision and action is recorded and verifiable." },
];

const audiences = [
  { icon: GraduationCap, title: "Colleges", text: "Exams, labs and hostels stay online." },
  { icon: Building2, title: "Enterprises", text: "Less downtime, fewer late-night calls." },
  { icon: Hospital, title: "Hospitals", text: "Critical systems caught before they fail." },
  { icon: Network, title: "IT service providers", text: "One platform for every client network." },
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
            <p className="glass mx-auto mb-6 w-fit rounded-full! px-4 py-1.5 text-xs tracking-wide text-fg-muted">
              AI-native · Digital-twin validated · Explainable
            </p>
            <h1 className="text-5xl font-semibold tracking-tight md:text-7xl">
              Networks that
              <br />
              heal themselves.
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-lg text-fg-muted">
              NetHeal detects, diagnoses and fixes network faults in seconds, and explains every
              decision in plain English.
            </p>
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
      <section id="how" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-28">
        <Reveal>
          <h2 className="text-center text-3xl font-semibold md:text-4xl">The self-healing loop</h2>
          <p className="mx-auto mt-3 max-w-xl text-center text-fg-muted">
            Five steps, done automatically, usually before anyone notices.
          </p>
        </Reveal>
        <div className="relative mt-14 grid gap-4 md:grid-cols-5">
          <div className="absolute top-12 right-[10%] left-[10%] hidden h-px bg-gradient-to-r from-transparent via-accent-2 to-transparent md:block" />
          {steps.map((s, i) => (
            <Reveal key={s.title} delay={i * 0.1}>
              <div className="glass h-full p-5 text-center">
                <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-bg-2/60">
                  <s.icon className="size-5" />
                </div>
                <p className="text-xs text-fg-muted">Step {i + 1}</p>
                <h3 className="mt-1 font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm text-fg-muted">{s.text}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-24 bg-[radial-gradient(ellipse_at_center,var(--bg-2),transparent_70%)] px-6 py-28">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <h2 className="text-center text-3xl font-semibold md:text-4xl">Everything your network team needs</h2>
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
      <section className="mx-auto max-w-4xl px-6 py-20">
        <Reveal>
          <div className="glass p-10 text-center">
            <ShieldCheck className="mx-auto mb-4 size-8 text-healthy" />
            <h2 className="text-2xl font-semibold md:text-3xl">The AI explains. It never acts alone.</h2>
            <p className="mx-auto mt-4 max-w-2xl text-fg-muted">
              Detection, diagnosis and healing are done by a tested, rule-following engine. Every
              fix is validated on a digital twin, checked against your safety rules, and undone
              automatically if it doesn&apos;t help. The language model only explains what happened.
            </p>
          </div>
        </Reveal>
      </section>

      {/* Who it's for */}
      <section id="who" className="mx-auto max-w-6xl scroll-mt-24 px-6 py-20">
        <Reveal>
          <h2 className="text-center text-3xl font-semibold md:text-4xl">Built for networks that can&apos;t go down</h2>
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
            <p className="mt-3 text-fg-muted">Inject a fault and see NetHeal detect, diagnose and fix it live.</p>
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
