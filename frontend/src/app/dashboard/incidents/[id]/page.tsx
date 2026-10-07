"use client";

import { ArrowLeft, Search } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { QueryState } from "@/components/dashboard/QueryState";
import { CAUSES } from "@/components/dashboard/Diagnosis";
import { type Report, ReportPanel } from "@/components/dashboard/ReportPanel";
import { HealingResults, Stepper } from "@/components/dashboard/SelfHealing";
import type { ActionEvent, Anomaly, Hypothesis, Incident } from "@/lib/live";
import { useLive } from "@/lib/live";
import { useQuery } from "@/lib/query";
import { useEntityName } from "@/lib/names";

type Detail = {
  incident: Incident;
  anomalies: Anomaly[];
  diagnosis: Hypothesis[];
  actions: ActionEvent[];
  report: Report | null;
};

export default function IncidentPage() {
  const { id } = useParams<{ id: string }>();
  const version = useLive((s) => s.incident.incident?.id === id ? `${s.generation}/${s.incident.incident?.status}/${s.incident.actions.length}/${s.diagnosis[0]?.id}` : s.generation ?? "");
  const query = useQuery<Detail>(`/api/incidents/${encodeURIComponent(id)}`, version);
  const detail = query.data;
  const name = useEntityName();

  if (!detail) return <QueryState {...query} />;

  const { incident, diagnosis, anomalies, actions } = detail;
  // Why no fix was applied (nothing to fix, or no safe fix), in NetHeal's own words.
  const decision = actions.findLast((a) => a.kind === "no_action" || a.kind === "alert_only" || a.kind === "escalated")?.payload as string | undefined;
  const top = diagnosis[0];
  // A report belongs to these exact facts. Replacing evidence unmounts pending/locally generated reports.
  const reportVersion = JSON.stringify({ incident, diagnosis, actions, generated: detail.report?.generated_at });
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 pb-24">
      <Link href="/dashboard/incidents" className="flex w-fit items-center gap-1.5 pt-2 text-sm text-fg-muted hover:text-fg print:hidden">
        <ArrowLeft className="size-4" /> All incidents
      </Link>

      <header>
        <p className="text-sm text-fg-muted">
          Incident {incident.id.slice(0, 8)} · {new Date(incident.opened_at).toLocaleString()} · {incident.status}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">
          {top ? `${CAUSES[top.cause].label} · ${name(top.target)}` : "Incident"}
        </h1>
      </header>

      <div className="glass p-6 print:hidden">
        <Stepper incident={incident} />
        {decision && <p className="mt-5 text-center text-sm text-fg-muted">NetHeal decided: {decision}</p>}
      </div>

      <div className="space-y-4 print:hidden">
        <HealingResults incident={incident} actions={actions} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 print:hidden">
        <div className="glass p-6">
          <h3 className="font-semibold">Root cause evidence</h3>
          {top ? (
            <ul className="mt-3 space-y-2 text-sm">
              <li className="text-fg-muted">{Math.round(top.confidence * 100)}% heuristic ranking score · {top.supported === false ? "insufficient support" : "evidence-supported candidate"}</li>
              {top.evidence.map((e) => (
                <li key={e.description} className="flex gap-2">
                  <Search className="mt-0.5 size-4 shrink-0 text-fg-muted" /> {e.description}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-fg-muted">No diagnosis recorded.</p>
          )}
        </div>
        <div className="glass p-6">
          <h3 className="font-semibold">Alerts raised</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {anomalies.map((a) => (
              <li key={a.id} className="flex justify-between gap-3">
                <span>{name(a.entity_id)}</span>
                <span className="text-fg-muted">{a.metric === "reachability" ? "unreachable" : a.metric}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <ReportPanel key={reportVersion} incidentId={incident.id} initial={detail.report} />
    </div>
  );
}
