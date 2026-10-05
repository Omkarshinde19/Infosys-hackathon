"use client";

import { Bot, Link2, ShieldAlert, ShieldCheck, User } from "lucide-react";
import { useEffect, useState } from "react";

type Entry = {
  seq: number;
  ts: string;
  actor: "system" | "user";
  event_type: string;
  payload: Record<string, unknown>;
  payload_hash: string;
  prev_hash: string;
  hash: string;
};
type Verdict = { valid: boolean; broken_at: number | null; entries: number };

function detail(e: Entry): string {
  const p = e.payload;
  if (p.by) return `by ${p.by}${p.type ? ` · ${p.type} on ${p.target}` : ""}${p.to !== undefined ? ` · level ${p.from} → ${p.to}` : ""}`;
  if (p.type) return String(p.type);
  if (p.incident) return `incident ${String(p.incident).slice(0, 8)}`;
  if (p.value) return String(p.value);
  return "";
}

export default function AuditPage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);

  useEffect(() => {
    const load = () => fetch("/api/audit").then((r) => r.json()).then(setEntries);
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, []);

  async function verify() {
    setVerdict(await (await fetch("/api/audit/verify")).json());
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">Audit log</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Every decision and action, chained with SHA-256: each entry contains the hash of the one before, so history
          can&apos;t be edited without breaking the chain.
        </p>
      </header>

      <div className="glass flex flex-wrap items-center justify-between gap-4 p-5">
        {verdict ? (
          <p className={`flex items-center gap-2 font-medium ${verdict.valid ? "text-healthy" : "text-critical"}`}>
            {verdict.valid ? <ShieldCheck className="size-5" /> : <ShieldAlert className="size-5" />}
            {verdict.valid
              ? `Integrity verified: all ${verdict.entries} entries are untouched`
              : `Tampering detected at entry #${verdict.broken_at}`}
          </p>
        ) : (
          <p className="text-sm text-fg-muted">{entries.length} entries recorded.</p>
        )}
        <button onClick={verify} className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90">
          <Link2 className="size-4" /> Verify integrity
        </button>
      </div>

      <div className="glass overflow-x-auto p-2">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-fg-muted">
            <tr>
              <th className="p-3 font-normal">#</th>
              <th className="p-3 font-normal">Time</th>
              <th className="p-3 font-normal">Who</th>
              <th className="p-3 font-normal">Event</th>
              <th className="p-3 font-normal">Details</th>
              <th className="p-3 font-normal">Hash ← previous</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.seq} className="border-t border-[var(--glass-border)]">
                <td className="p-3 text-fg-muted tabular-nums">{e.seq}</td>
                <td className="p-3 whitespace-nowrap tabular-nums">{new Date(e.ts).toLocaleTimeString()}</td>
                <td className="p-3">
                  <span className="flex items-center gap-1.5">
                    {e.actor === "user" ? <User className="size-3.5" /> : <Bot className="size-3.5" />} {e.actor}
                  </span>
                </td>
                <td className="p-3 font-medium">{e.event_type}</td>
                <td className="p-3 text-fg-muted">{detail(e)}</td>
                <td className="p-3 font-mono text-xs text-fg-muted">
                  {e.hash.slice(0, 10)}… ← {e.prev_hash.slice(0, 10)}…
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
