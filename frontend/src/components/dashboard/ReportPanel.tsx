"use client";

import { Download, FileText, Printer, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { postJSON } from "@/lib/live";

export type Report = {
  markdown: string;
  source: string;
  fallback_reason: string | null;
  generated_at: string;
};

/** AI-written (or template) incident report with download and print-to-PDF. */
export function ReportPanel({ incidentId, initial }: { incidentId: string; initial: Report | null }) {
  const [report, setReport] = useState(initial);
  const [busy, setBusy] = useState(false);

  async function generate(refresh: boolean) {
    setBusy(true);
    try {
      setReport(await postJSON(`/incidents/${incidentId}/report${refresh ? "?refresh=true" : ""}`));
    } finally {
      setBusy(false);
    }
  }

  function download() {
    const blob = new Blob([report!.markdown], { type: "text/markdown" });
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(blob),
      download: `netheal-incident-${incidentId.slice(0, 8)}.md`,
    });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const ai = report?.source.startsWith("llm:");
  return (
    <div className="glass p-6 print:border-0 print:bg-transparent print:shadow-none">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <h3 className="flex items-center gap-2 font-semibold">
          <FileText className="size-4" /> Incident report
        </h3>
        {report && (
          <div className="flex gap-2 text-sm">
            <button onClick={() => generate(true)} disabled={busy} className="glass flex items-center gap-1.5 rounded-full! px-3 py-1.5 hover:bg-[var(--glass-hover)]">
              <RefreshCw className={`size-3.5 ${busy ? "animate-spin" : ""}`} /> Regenerate
            </button>
            <button onClick={download} className="glass flex items-center gap-1.5 rounded-full! px-3 py-1.5 hover:bg-[var(--glass-hover)]">
              <Download className="size-3.5" /> .md
            </button>
            <button onClick={() => window.print()} className="glass flex items-center gap-1.5 rounded-full! px-3 py-1.5 hover:bg-[var(--glass-hover)]">
              <Printer className="size-3.5" /> PDF
            </button>
          </div>
        )}
      </div>

      {!report && (
        <div className="flex flex-col items-center py-10 text-center">
          <Sparkles className="size-8 text-accent-2" />
          <p className="mt-2 max-w-md text-sm text-fg-muted">
            The AI writes a plain-English report from this incident&apos;s facts only. It explains; it never takes actions.
          </p>
          <button
            onClick={() => generate(false)}
            disabled={busy}
            className="mt-5 flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-60"
          >
            <Sparkles className={`size-4 ${busy ? "animate-pulse" : ""}`} />
            {busy ? "Llama-3.3-70B is writing the report… (~15 s)" : "Generate report"}
          </button>
        </div>
      )}

      {report && (
        <>
          <p className="mt-3 text-xs text-fg-muted print:hidden">
            {ai
              ? `Written by ${report.source.slice(4)} on Qualcomm Cloud AI (Cirrascale), grounded in the incident facts`
              : `Written from the built-in template: ${report.fallback_reason}`}{" "}
            · {new Date(report.generated_at).toLocaleString()}
          </p>
          <article className="report mt-4 max-w-none text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ table: (props) => <div className="overflow-x-auto"><table {...props} /></div> }}
            >
              {report.markdown}
            </ReactMarkdown>
          </article>
        </>
      )}
    </div>
  );
}
