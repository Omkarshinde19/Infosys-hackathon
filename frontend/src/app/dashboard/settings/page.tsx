"use client";

import { Bot, Brain, ClipboardCheck, Shield, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";

type Settings = {
  autonomy: { level: number; levels: Record<string, string> };
  policy: string;
  users: { username: string; role: string }[];
  llm: { model: string; configured: boolean; embeddings: string };
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
  const [s, setS] = useState<Settings | null>(null);
  const session = useAuth((st) => st.session);
  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then(setS);
  }, []);
  if (!s) return null;
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
          <p className="text-sm">Language model: <b>{s.llm.model}</b> on Qualcomm Cloud AI (Cirrascale)</p>
          <p className="text-sm">Document search: <b>{s.llm.embeddings}</b></p>
          <p className={`mt-2 text-sm ${s.llm.configured ? "text-healthy" : "text-warning"}`}>
            {s.llm.configured ? "Connected" : "No API key: using offline templates"}
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
