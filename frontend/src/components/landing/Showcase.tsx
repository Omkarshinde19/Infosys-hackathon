import { BellRing, Check, FileText } from "lucide-react";
import { Window } from "./Window";

const STAGES = ["Detect", "Diagnose", "Decide", "Heal", "Verify"];

/** Angled backdrop shape from the reference design, in our palette. */
function Slab({ className }: { className: string }) {
  return <div className={`absolute bg-[var(--shape)] [clip-path:polygon(14%_0,100%_0,86%_100%,0_100%)] ${className}`} />;
}

/** One healed incident, told in three windows: the Control Room, the diagnosis and the report. */
export function LoopShowcase() {
  return (
    <div className="relative mx-auto h-[360px] w-full max-w-xl sm:h-[530px]">
      <Slab className="top-[14%] left-[2%] h-[72%] w-[64%]" />
      <div className="absolute top-[34%] right-[6%] size-44 rounded-full border-[26px] border-[var(--shape)]" />

      <Window title="NetHeal · Control Room" className="absolute top-0 left-0 w-full sm:top-[19%] sm:left-[6%] sm:w-[76%]">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold">Campus network</p>
          <span className="rounded-full bg-healthy/15 px-2 py-0.5 text-[11px] font-medium text-healthy">Healed in 9 s</span>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-critical/10 px-2.5 py-2 text-xs">
          <BellRing className="size-3.5 shrink-0 text-critical" />
          <span className="font-medium">Silent packet loss · CS Lab</span>
          <span className="ml-auto text-fg-muted">found in 2.5 s</span>
        </div>
        <div className="mt-4 flex items-start">
          {STAGES.map((s, i) => (
            <div key={s} className="flex flex-1 flex-col items-center gap-1">
              <div className="flex w-full items-center">
                <span className={`h-px flex-1 ${i ? "bg-healthy" : ""}`} />
                <span className="grid size-5 place-items-center rounded-full bg-healthy text-bg">
                  <Check className="size-3" strokeWidth={3} />
                </span>
                <span className={`h-px flex-1 ${i < STAGES.length - 1 ? "bg-healthy" : ""}`} />
              </div>
              <span className="text-[10px] text-fg-muted">{s}</span>
            </div>
          ))}
        </div>
        <p className="mt-4 text-[10px] text-fg-muted">Packet loss on the CS Lab flow, before and after the fix</p>
        <svg viewBox="0 0 300 60" className="mt-1 h-14 w-full" fill="none" strokeWidth="2" strokeLinecap="round">
          <path d="M0 48 L60 47 L90 46" className="stroke-accent-2" />
          <path d="M90 46 L110 14 L140 10 L165 18 L180 44" className="stroke-critical" />
          <path d="M180 44 L220 47 L300 47" className="stroke-healthy" />
        </svg>
      </Window>

      <Window title="Diagnosis" className="absolute top-0 right-0 hidden w-[42%] sm:block">
        <p className="text-sm font-semibold">Gray failure</p>
        <p className="mt-0.5 text-[11px] text-fg-muted">Distribution South A ↔ CS Lab</p>
        <div className="mt-3 h-1.5 rounded-full bg-bg-2">
          <div className="h-full w-[90%] rounded-full bg-accent-2" />
        </div>
        <p className="mt-1.5 text-[11px] text-fg-muted">Confidence 90% · rules and GNN agree</p>
      </Window>

      <Window title="Incident report" className="absolute bottom-0 left-0 hidden w-[48%] sm:block">
        <p className="flex items-center gap-1.5 text-sm font-semibold">
          <FileText className="size-3.5" /> What happened
        </p>
        <p className="mt-2 text-[11px] leading-relaxed text-fg-muted">
          The CS Lab link kept dropping packets while looking healthy. NetHeal tested a detour on
          the twin, moved the traffic via Distribution South B and checked it held.
        </p>
      </Window>
    </div>
  );
}
