"use client";

import { ChevronRight, FileText } from "lucide-react";
import Link from "next/link";
import { QueryState } from "@/components/dashboard/QueryState";
import { useQuery } from "@/lib/query";
import { CAUSES } from "@/components/dashboard/Diagnosis";
import { type Hypothesis, type Incident, useLive } from "@/lib/live";
import { useEntityName } from "@/lib/names";

type Row = { incident: Incident; root_cause: Hypothesis | null };

const STATUS_COLOR: Record<string, string> = {
  resolved: "var(--healthy)",
  failed: "var(--critical)",
};

export default function IncidentsPage() {
  const name = useEntityName();
  const version = useLive((s) => `${s.generation}/${s.incident.incident?.id}/${s.incident.incident?.status}/${s.incident.actions.length}`);
  const query = useQuery<Row[]>("/api/incidents", version);
  const rows = query.data;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">Incidents</h1>
        <p className="mt-1 text-sm text-fg-muted">Every problem NetHeal handled, with its timeline, fix and a report written by AI.</p>
      </header>
      <QueryState {...query} />

      {rows?.length === 0 && (
        <div className="glass flex flex-col items-center p-10 text-center">
          <FileText className="size-8 text-fg-muted" />
          <p className="mt-2 font-semibold">No incidents yet</p>
          <p className="text-sm text-fg-muted">Inject a fault in the Fault Lab and it will show up here.</p>
        </div>
      )}

      <ul className="space-y-3">
        {rows?.map(({ incident: inc, root_cause: rc }) => (
          <li key={inc.id}>
            <Link href={`/dashboard/incidents/${inc.id}`} className="glass flex items-center gap-4 p-5 hover:bg-[var(--glass-hover)]">
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: STATUS_COLOR[inc.status] ?? "var(--warning)" }} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {rc ? CAUSES[rc.cause].label : "Investigating"} {rc && <span className="font-normal text-fg-muted">· {name(rc.target)}</span>}
                </p>
                <p className="text-xs text-fg-muted">
                  {new Date(inc.opened_at).toLocaleString()} · {inc.status}
                </p>
              </div>
              <div className="text-right text-xs text-fg-muted tabular-nums">
                <p>detect {inc.mttd_s?.toFixed(1) ?? "-"} s</p>
                <p>heal {inc.mttr_s?.toFixed(1) ?? "-"} s</p>
              </div>
              <ChevronRight className="size-4 text-fg-muted" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
