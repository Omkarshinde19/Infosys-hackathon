"use client";

import { LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuth((s) => s.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-svh place-items-center bg-[radial-gradient(ellipse_at_top,var(--bg-2),var(--bg)_65%)] px-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <form onSubmit={submit} className="glass w-full max-w-sm p-8">
        <Logo className="text-xl" />
        <h1 className="mt-6 text-2xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Viewers can watch. Operators can inject faults and approve fixes. Admins can also change the comfort level.
        </p>
        <label className="mt-6 block text-sm">
          <span className="text-fg-muted">Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            className="mt-1.5 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--glass)] px-3 py-2"
          />
        </label>
        <label className="mt-4 block text-sm">
          <span className="text-fg-muted">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="mt-1.5 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--glass)] px-3 py-2"
          />
        </label>
        {error && <p className="mt-4 text-sm text-critical">{error}</p>}
        <button
          disabled={busy || !username || !password}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-full bg-fg py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-50"
        >
          <LogIn className="size-4" /> {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="mt-4 text-center text-xs text-fg-muted">Demo accounts: see config/DEMO_ACCOUNTS.md</p>
      </form>
    </main>
  );
}
