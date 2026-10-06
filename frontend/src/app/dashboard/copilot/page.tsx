"use client";

import { ArrowUp, Bot, ChevronDown, Lock, ShieldCheck, Sparkles, User, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/lib/auth";
import { postJSON } from "@/lib/live";

type Evidence = Record<string, { kind: string; text: string }>;
type Answer = { answer: string; evidence: Evidence; tools: string[]; source: string; provider?: string | null; fallback_reason: string | null };
type Message = { role: "user" | "assistant"; content: string; answer?: Answer; seconds?: number };

const SUGGESTIONS = [
  "Is the network healthy right now?",
  "What happened in the last incident?",
  "What would happen if Core Router 1 got overloaded?",
  "How does NetHeal detect problems early?",
];
const THINKING = ["Looking at live telemetry…", "Checking alerts and the diagnosis…", "Reading the docs…", "Writing a cited answer…"];
const TOOL_STEPS: Record<string, string> = {
  get_network_status: "Checked the live network",
  get_active_alerts: "Looked at the active alerts",
  get_diagnosis: "Read the current diagnosis",
  list_incidents: "Listed recent incidents",
  get_incident: "Opened an incident",
  get_audit_log: "Read the audit log",
  search_docs: "Searched NetHeal's docs",
  what_if: "Simulated it on the digital twin",
};

/** NetHeal mark, glowing, in the spirit of the reference design. */
function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="size-16 text-accent drop-shadow-[0_0_24px_var(--accent-2)]" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="6" cy="16" r="3" />
      <circle cx="26" cy="7" r="3" />
      <circle cx="26" cy="25" r="3" />
      <path d="M9 16h4l2-5 3 10 2-5h2M23.5 8.5 18 12M23.5 23.5 20 21" strokeLinecap="round" />
    </svg>
  );
}

/** Turns [E3] into a hoverable evidence chip. */
function Cited({ answer }: { answer: Answer }) {
  const text = answer.answer.replace(/\[(E\d+)\]/g, (_, id) => `[${id}](#${id})`);
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          const id = href?.slice(1) ?? "";
          const ev = answer.evidence[id];
          return ev ? (
            <span
              title={`${ev.kind}: ${ev.text}`}
              className="mx-0.5 inline-flex cursor-help items-center rounded-full border border-accent-2/60 bg-accent-2/20 px-1.5 text-[11px] font-semibold text-accent align-middle"
            >
              {children}
            </span>
          ) : (
            <span>{children}</span>
          );
        },
        ul: (props) => <ul className="my-2 list-disc pl-5" {...props} />,
        p: (props) => <p className="my-1.5" {...props} />,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

/** "Thinking for 8s" while the answer is written, then "Worked for 12s · 3 tools", folded away
 * but one click from the steps it took. */
function WorkLog({ seconds, steps, live }: { seconds: number; steps: string[]; live: boolean }) {
  return (
    <details open={live} className="group mb-2 text-sm text-fg-muted">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1.5 hover:text-fg [&::-webkit-details-marker]:hidden">
        {live
          ? `Thinking for ${seconds}s`
          : steps.length
            ? `Worked for ${seconds}s · ${steps.length} ${steps.length === 1 ? "step" : "steps"}`
            : `Answered in ${seconds}s`}
        <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" />
      </summary>
      <ul className="mt-2 space-y-1.5 border-l-2 border-[var(--glass-border)] pl-4">
        {steps.map((s, i) => (
          <li key={i} className={live && i === steps.length - 1 ? "animate-pulse" : ""}>{s}</li>
        ))}
      </ul>
    </details>
  );
}

export default function CopilotPage() {
  const session = useAuth((s) => s.session);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Block body on purpose: scrollIntoView() now returns a Promise in Chrome, and an effect
    // must not return anything but a cleanup function.
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => {
      const elapsed = Math.round((Date.now() - started) / 1000);
      setSeconds(elapsed);
      setStep(Math.min(Math.floor(elapsed / 3.5), THINKING.length - 1));
    }, 250);
    return () => clearInterval(timer);
  }, [busy]);

  async function send(question: string) {
    if (!question.trim() || busy) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    setStep(0);
    setSeconds(0);
    const started = Date.now();
    try {
      const answer: Answer = await postJSON("/copilot", { question, history });
      const took = Math.max(1, Math.round((Date.now() - started) / 1000));
      setMessages((m) => [...m, { role: "assistant", content: answer.answer, answer, seconds: took }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `Sorry, that failed: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  }

  const composer = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send(input);
      }}
      className="glass w-full max-w-2xl rounded-[28px]! p-2 pl-5 shadow-[var(--window-shadow)]"
    >
      <textarea
        maxLength={2000}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(input);
          }
        }}
        rows={2}
        placeholder="Ask about the network, an incident, or a what if question…"
        className="w-full resize-none bg-transparent pt-2 pr-2 outline-none placeholder:text-fg-muted"
      />
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 rounded-full border border-[var(--glass-border)] px-3 py-1 text-xs text-fg-muted">
          <ShieldCheck className="size-3.5" /> Grounded · Read only
        </span>
        <button
          disabled={busy || !input.trim()}
          aria-label="Send"
          className="grid size-10 place-items-center rounded-full bg-accent-2 text-white shadow-[0_0_20px_var(--accent-2)] transition hover:brightness-110 disabled:opacity-40 disabled:shadow-none"
        >
          <ArrowUp className="size-5" />
        </button>
      </div>
    </form>
  );

  return (
    <div className="relative mx-auto flex min-h-[calc(100svh-6.5rem)] max-w-4xl flex-col md:min-h-[calc(100svh-3rem)]">
      {/* Fills the whole area behind the page (the sidebar is glass, so it shows through). */}
      <div className="sky pointer-events-none fixed inset-0 overflow-hidden">
        <div className="sky-stars-far" />
        <div className="sky-stars" />
        <div className="absolute top-0 left-1/2 h-[55%] w-48 -translate-x-1/2 bg-gradient-to-b from-[var(--beam)] to-transparent blur-2xl md:left-[calc(50%+8.5rem)]" />
        <div className="absolute -bottom-40 left-1/2 h-80 w-[120%] -translate-x-1/2 rounded-[100%] bg-[radial-gradient(ellipse_at_center,var(--horizon),transparent_70%)]" />
      </div>

      <div className="relative flex flex-1 flex-col">
        {!session ? (
          <div className="m-auto flex flex-col items-center gap-4 p-8 text-center">
            <Mark />
            <h1 className="text-3xl font-medium">Ask NetHeal</h1>
            <p className="max-w-sm text-sm text-fg-muted">Sign in to ask questions. Every answer comes with the evidence behind it.</p>
            <Link href="/login" className="flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 font-medium text-bg">
              <Lock className="size-4" /> Sign in
            </Link>
          </div>
        ) : messages.length === 0 ? (
          <div className="m-auto flex w-full flex-col items-center gap-8 p-6">
            <Mark />
            <div className="text-center">
              <h1 className="text-4xl font-medium tracking-tight">Hey, {session.username}. Ready to dive in?</h1>
              <p className="mt-3 text-fg-muted">Ask about the live network, an incident, or what would happen if something broke.</p>
            </div>
            {composer}
            <div className="flex max-w-2xl flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} className="glass flex items-center gap-1.5 rounded-full! px-4 py-2 text-sm hover:bg-[var(--glass-hover)]">
                  <Sparkles className="size-3.5 text-accent-2" /> {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 space-y-6 py-6">
              {messages.map((m, i) => (
                <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
                  {m.role === "assistant" && <Bot className="mt-1 size-5 shrink-0 text-accent-2" />}
                  <div className={m.role === "user" ? "glass max-w-[80%] rounded-3xl! bg-accent-2/25! px-4 py-2.5 text-sm" : "max-w-[85%] text-sm leading-relaxed"}>
                    {m.answer && <WorkLog seconds={m.seconds ?? 0} steps={m.answer.tools.map((t) => TOOL_STEPS[t] ?? t)} live={false} />}
                    <div className={m.role === "assistant" ? "glass rounded-2xl! px-4 py-3" : ""}>
                      {m.answer ? <Cited answer={m.answer} /> : m.content}
                      {m.answer && (
                        <p className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--glass-border)] pt-2 text-[11px] text-fg-muted">
                          <Wrench className="size-3" /> {m.answer.tools.join(", ") || "no tools"} ·{" "}
                          {m.answer.source.startsWith("llm:")
                            ? `${m.answer.source.slice(4)} · ${m.answer.provider ?? "Qualcomm Cloud AI"}`
                            : `offline answer (${m.answer.fallback_reason})`}{" "}
                          · {Object.keys(m.answer.evidence).length} evidence cited
                        </p>
                      )}
                    </div>
                  </div>
                  {m.role === "user" && <User className="mt-1 size-5 shrink-0 text-accent-2" />}
                </div>
              ))}
              {busy && (
                <div className="flex gap-3">
                  <Bot className="mt-0.5 size-5 shrink-0 animate-pulse text-accent-2" />
                  <WorkLog seconds={seconds} steps={THINKING.slice(0, step + 1)} live />
                </div>
              )}
              <div ref={end} />
            </div>
            <div className="sticky bottom-4 flex justify-center pt-2">{composer}</div>
          </>
        )}
      </div>
    </div>
  );
}
