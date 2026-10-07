"use client";

import { Bot, Link2, ShieldAlert, ShieldCheck, User } from "lucide-react";
import { useRef, useState } from "react";
import { QueryState } from "@/components/dashboard/QueryState";
import { errorMessage, requestJSON } from "@/lib/http";
import { useQuery } from "@/lib/query";

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
  const query = useQuery<Entry[]>("/api/audit", "", 3000);
  const entries = query.data ?? [];
  const [checked, setChecked] = useState<{ verdict: Verdict; hash: string | undefined } | null>(null);
  const verdict = checked?.hash === entries[0]?.hash ? checked?.verdict : null;
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [shown, setShown] = useState(50); // a long log stays usable on a projector

  async function verify() {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try { setChecked({ verdict: await requestJSON<Verdict>("/api/audit/verify"), hash: entries[0]?.hash }); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { pending.current = false; setBusy(false); }
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
      <QueryState {...query} />
      {error && <p role="alert" className="glass p-4 text-critical">{error}</p>}

      <div className="glass flex flex-wrap items-center justify-between gap-4 p-5">
        {verdict ? (
          <p className={`flex items-center gap-2 font-medium ${verdict.valid ? "text-healthy" : "text-critical"}`}>
            {verdict.valid ? <ShieldCheck className="size-5" /> : <ShieldAlert className="size-5" />}
            {verdict.valid
              ? `Hash chain consistent across ${verdict.entries} entries at verification time`
              : `Tampering detected at entry #${verdict.broken_at}`}
          </p>
        ) : (
          <p className="text-sm text-fg-muted">The {entries.length} most recent entries, newest first.</p>
        )}
        <button onClick={verify} disabled={busy || query.loading} className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-50">
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
            {entries.slice(0, shown).map((e) => (
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
        {entries.length > shown && (
          <button onClick={() => setShown((n) => n + 50)} className="w-full p-3 text-sm text-fg-muted hover:text-fg">
            Show older entries ({entries.length - shown} more)
          </button>
        )}
      </div>
    </div>
  );
}
