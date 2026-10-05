"use client";

import { ArrowUp, Bot, Lock, ShieldCheck, Sparkles, User, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/lib/auth";
import { postJSON } from "@/lib/live";

type Evidence = Record<string, { kind: string; text: string }>;
type Answer = { answer: string; evidence: Evidence; tools: string[]; source: string; fallback_reason: string | null };
type Message = { role: "user" | "assistant"; content: string; answer?: Answer };

const SUGGESTIONS = [
  "Is the network healthy right now?",
  "What happened in the last incident?",
  "What would happen if Core Router 1 got overloaded?",
  "How does NetHeal detect problems early?",
];
const THINKING = ["Looking at live telemetry…", "Checking alerts and the diagnosis…", "Reading the docs…", "Writing a cited answer…"];

/** NetHeal mark, glowing, in the spirit of the reference design. */
function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="size-20 text-[#c1e8ff] drop-shadow-[0_0_24px_#7da0ca]" fill="none" stroke="currentColor" strokeWidth="1.6">
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

export default function CopilotPage() {
  const session = useAuth((s) => s.session);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [messages, busy]);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setStep((s) => (s + 1) % THINKING.length), 3500);
    return () => clearInterval(timer);
  }, [busy]);

  async function send(question: string) {
    if (!question.trim() || busy) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    setStep(0);
    try {
      const answer: Answer = await postJSON("/copilot", { question, history });
      setMessages((m) => [...m, { role: "assistant", content: answer.answer, answer }]);
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
      className="glass w-full max-w-2xl rounded-2xl! p-3"
    >
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(input);
          }
        }}
        rows={2}
        placeholder="Ask about the network, an incident, or a what-if…"
        className="w-full resize-none bg-transparent px-2 py-1 outline-none placeholder:text-fg-muted"
      />
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 rounded-full border border-[var(--glass-border)] px-3 py-1 text-xs text-fg-muted">
          <ShieldCheck className="size-3.5" /> Grounded · read-only
        </span>
        <button
          disabled={busy || !input.trim()}
          aria-label="Send"
          className="grid size-9 place-items-center rounded-xl bg-fg text-bg hover:opacity-90 disabled:opacity-40"
        >
          <ArrowUp className="size-4" />
        </button>
      </div>
    </form>
  );

  return (
    <div className="relative mx-auto flex min-h-[calc(100svh-3rem)] max-w-5xl flex-col overflow-hidden rounded-3xl border border-[var(--glass-border)] bg-[#021024]">
      {/* Starfield + light beam (reference design, in our palette) */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(1px_1px_at_20%_30%,#c1e8ff99,transparent),radial-gradient(1px_1px_at_70%_60%,#c1e8ff77,transparent),radial-gradient(1px_1px_at_40%_80%,#7da0ca88,transparent),radial-gradient(1px_1px_at_85%_20%,#c1e8ff66,transparent),radial-gradient(1px_1px_at_10%_70%,#7da0ca77,transparent)] bg-[length:240px_240px]" />
      <div className="pointer-events-none absolute top-0 left-1/2 h-[55%] w-40 -translate-x-1/2 bg-gradient-to-b from-[#c1e8ff66] via-[#5483b322] to-transparent blur-2xl" />
      <div className="pointer-events-none absolute -bottom-40 left-1/2 h-80 w-[120%] -translate-x-1/2 rounded-[100%] bg-[radial-gradient(ellipse_at_center,#05265999,transparent_70%)]" />

      <div className="relative z-10 flex flex-1 flex-col text-[#e6f4ff]">
        {!session ? (
          <div className="m-auto flex flex-col items-center gap-4 p-8 text-center">
            <Mark />
            <h1 className="text-3xl font-medium">Ask NetHeal</h1>
            <p className="max-w-sm text-sm text-[#7da0ca]">Sign in to ask questions. Every answer comes with the evidence behind it.</p>
            <Link href="/login" className="flex items-center gap-2 rounded-full bg-[#c1e8ff] px-5 py-2.5 font-medium text-[#021024]">
              <Lock className="size-4" /> Sign in
            </Link>
          </div>
        ) : messages.length === 0 ? (
          <div className="m-auto flex w-full flex-col items-center gap-8 p-6">
            <Mark />
            <h1 className="text-center text-4xl font-medium tracking-tight">How can I help you today?</h1>
            {composer}
            <div className="flex max-w-2xl flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} className="glass flex items-center gap-1.5 rounded-xl! px-3 py-2 text-sm hover:bg-[var(--glass-hover)]">
                  <Sparkles className="size-3.5 text-[#7da0ca]" /> {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 space-y-5 overflow-y-auto p-6 pb-4">
              {messages.map((m, i) => (
                <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
                  {m.role === "assistant" && <Bot className="mt-1 size-5 shrink-0 text-[#7da0ca]" />}
                  <div className={`glass max-w-[80%] rounded-2xl! px-4 py-3 text-sm leading-relaxed ${m.role === "user" ? "bg-[#05265999]!" : ""}`}>
                    {m.answer ? <Cited answer={m.answer} /> : m.content}
                    {m.answer && (
                      <p className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--glass-border)] pt-2 text-[11px] text-[#7da0ca]">
                        <Wrench className="size-3" /> {m.answer.tools.join(", ") || "no tools"} ·{" "}
                        {m.answer.source.startsWith("llm:")
                          ? `${m.answer.source.slice(4)} on Qualcomm Cloud AI`
                          : `offline answer (${m.answer.fallback_reason})`}{" "}
                        · {Object.keys(m.answer.evidence).length} evidence cited
                      </p>
                    )}
                  </div>
                  {m.role === "user" && <User className="mt-1 size-5 shrink-0 text-[#7da0ca]" />}
                </div>
              ))}
              {busy && (
                <div className="flex items-center gap-3 text-sm text-[#7da0ca]">
                  <Bot className="size-5 animate-pulse" /> {THINKING[step]}
                </div>
              )}
              <div ref={end} />
            </div>
            <div className="flex justify-center p-4 pt-0">{composer}</div>
          </>
        )}
      </div>
    </div>
  );
}
