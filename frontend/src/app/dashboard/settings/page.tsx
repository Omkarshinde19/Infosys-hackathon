"use client";

import { Bot, Brain, ClipboardCheck, Network, Shield, Users } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { QueryState } from "@/components/dashboard/QueryState";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth, useCan } from "@/lib/auth";
import { postJSON, useLive } from "@/lib/live";
import { useQuery } from "@/lib/query";

type Backend = { kind: "sim" | "emu"; emulab_ready: boolean };

/** Simulator vs the real-packet emulated network (Mininet + Open vSwitch). */
function BackendCard() {
  const generation = useLive((s) => s.generation ?? "");
  const query = useQuery<Backend>("/api/backend", generation);
  const b = query.data;
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const isAdmin = useCan("admin");

  async function choose(kind: Backend["kind"]) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await postJSON("/backend", { kind });
      query.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      pending.current = false;
    }
  }

  const options = [
    ["sim", "Simulated", "Fast Python digital twin of the campus"],
    ["emu", "Emulated (real packets)", "Mininet + Open vSwitch, OpenFlow routes, real pings and traffic"],
  ] as const;
  return (
    <Card icon={Network} title="Network backend">
      <QueryState {...query} />
      <div className="grid gap-2">
        {options.map(([kind, label, text]) => (
          <button
            key={kind}
            disabled={!isAdmin || busy || !b || (kind === "emu" && !b.emulab_ready)}
            aria-pressed={b?.kind === kind}
            onClick={() => choose(kind)}
            className={`rounded-xl border p-3 text-left text-sm disabled:cursor-not-allowed ${
              b?.kind === kind ? "border-accent-2 bg-[var(--glass-hover)]" : "border-[var(--glass-border)] enabled:hover:bg-[var(--glass-hover)]"
            }`}
          >
            <span className="font-medium">{label}</span>
            <span className="block text-xs text-fg-muted">{text}</span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-fg-muted">
        {b ? (b.emulab_ready ? "Emulated network is running." : "Emulated network is off. Start it with ./netheal emu.") : "Checking backend availability…"}{" "}
        Switching resets the incident and the detector relearns the new network for 30 s.
        {!isAdmin && " Only an admin can switch."}
      </p>
      {error && <p className="mt-2 text-xs text-critical">{error}</p>}
    </Card>
  );
}

type Settings = {
  autonomy: { level: number; levels: Record<string, string> };
  policy: string;
  users: { username: string; role: string }[];
  llm: { model: string; configured: boolean; embeddings: string; providers: { model: string; label: string }[] };
  detector: Record<string, string | number>;
  models_loaded: Record<string, boolean>;
};

function Card({ icon: Icon, title, children }: { icon: typeof Shield; title: string; children: React.ReactNode }) {
  return (
    <div className="glass p-6">
      <h2 className="mb-3 flex items-center gap-2 font-semibold"><Icon className="size-4" /> {title}</h2>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const version = useLive((st) => `${st.generation}/${st.autonomy?.level}`);
  const query = useQuery<Settings>("/api/settings", version);
  const s = query.data;
  const session = useAuth((st) => st.session);
  if (!s) return <QueryState {...query} />;
  const rules = [...s.policy.matchAll(/^(\w+) := (.+)$/gm)];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 pb-24">
      <header className="flex items-end justify-between pt-2">
        <div>
          <p className="text-sm text-fg-muted">Control Room</p>
          <h1 className="text-4xl font-semibold tracking-tight">Settings</h1>
        </div>
        <ThemeToggle />
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <BackendCard />
        <Card icon={ClipboardCheck} title="Comfort level">
          <p className="text-sm">Level {s.autonomy.level}: {s.autonomy.levels[String(s.autonomy.level)]}</p>
          <Link href="/dashboard/approvals" className="mt-3 inline-block text-sm underline">Change it on the Approvals page</Link>
        </Card>

        <Card icon={Users} title="Users and roles">
          <ul className="space-y-1 text-sm">
            {s.users.map((u) => (
              <li key={u.username} className="flex justify-between">
                <span>{u.username}{session?.username === u.username && " (you)"}</span><span className="text-fg-muted">{u.role}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-fg-muted">Passwords are stored only as salted PBKDF2 hashes.</p>
        </Card>

        <Card icon={Shield} title="Safety rules (OPA Rego)">
          <ul className="space-y-1 text-sm">
            {rules.map(([, key, value]) => (
              <li key={key} className="flex justify-between"><span>{key.replaceAll("_", " ")}</span><span className="text-fg-muted tabular-nums">{value}</span></li>
            ))}
          </ul>
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-fg-muted">Show the full policy</summary>
            <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-[var(--glass)] p-3 whitespace-pre-wrap">{s.policy}</pre>
          </details>
        </Card>

        <Card icon={Bot} title="AI assistant & reports">
          <ol className="space-y-1 text-sm">
            {s.llm.providers.map((p, i) => (
              <li key={p.label}>{i === 0 ? "Language model" : "If that is unreachable"}: <b>{p.model}</b> · {p.label}</li>
            ))}
          </ol>
          <p className="text-sm">Document search: <b>{s.llm.embeddings}</b></p>
          <p className={`mt-2 text-sm ${s.llm.configured ? "text-healthy" : "text-warning"}`}>
            {s.llm.configured ? "NetHeal's own templates take over if every model is unreachable" : "No AI model set up: using offline templates"}
          </p>
        </Card>

        <Card icon={Brain} title="Detection & models">
          <ul className="space-y-1 text-sm">
            {Object.entries(s.detector).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span>{k.replaceAll("_", " ")}</span><span className="text-fg-muted">{String(v)}</span></li>
            ))}
            {Object.entries(s.models_loaded).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span>{k.replaceAll("_", " ")}</span><span className={v ? "text-healthy" : "text-critical"}>{v ? "loaded" : "missing"}</span></li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
