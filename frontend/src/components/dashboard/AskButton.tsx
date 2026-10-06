"use client";

import { Bot } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

/** Round shortcut to Ask NetHeal, floating on every dashboard page except the assistant itself. */
export function AskButton() {
  if (usePathname() === "/dashboard/copilot") return null;
  return (
    <Link
      href="/dashboard/copilot"
      aria-label="Ask NetHeal"
      title="Ask NetHeal"
      className="fixed right-5 bottom-5 z-40 grid size-14 place-items-center rounded-full bg-accent-2 text-white shadow-[0_0_28px_var(--accent-2)] transition hover:scale-105 hover:brightness-110 print:hidden"
    >
      <Bot className="size-6" />
    </Link>
  );
}
