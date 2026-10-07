"use client";

import { create } from "zustand";
import { requestJSON } from "./http";

export type Role = "viewer" | "operator" | "admin";
export type Session = { token: string; username: string; role: Role };

const ROLES: Role[] = ["viewer", "operator", "admin"];
const KEY = "netheal-session";
let revision = 0;

function validSession(value: unknown): value is Session {
  if (!value || typeof value !== "object") return false;
  const session = value as Session;
  return typeof session.token === "string" && session.token.length > 0 && typeof session.username === "string" && ROLES.includes(session.role);
}

function saved(): Session | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "null");
    return validSession(value) ? value : null;
  } catch {
    return null;
  }
}

function persist(session: Session | null) {
  try {
    if (session) localStorage.setItem(KEY, JSON.stringify(session));
    else localStorage.removeItem(KEY);
  } catch { /* A session still works in memory when browser storage is unavailable. */ }
}

type AuthState = {
  session: Session | null;
  checking: boolean;
  restore: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  session: null, // filled by restore() after hydration, so server and client renders match
  checking: false,
  restore: async () => {
    const ticket = ++revision;
    const stored = saved();
    set({ session: null, checking: Boolean(stored) });
    if (!stored) return;
    try {
      const identity = await requestJSON<{ username: string; role: Role }>("/api/auth/me", { headers: { Authorization: `Bearer ${stored.token}` } });
      const session = { ...stored, ...identity };
      if (!validSession(session)) throw new Error("The server returned an invalid identity.");
      if (ticket !== revision) return;
      persist(session);
      set({ session, checking: false });
    } catch (error) {
      if (ticket !== revision) return;
      if (error && typeof error === "object" && "status" in error && error.status === 401) persist(null);
      set({ session: null, checking: false });
    }
  },
  login: async (username, password) => {
    const ticket = ++revision;
    const session = await requestJSON<Session>("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!validSession(session)) throw new Error("The server returned an invalid session.");
    if (ticket !== revision) return;
    persist(session);
    set({ session, checking: false });
  },
  logout: () => {
    ++revision;
    persist(null);
    set({ session: null, checking: false });
  },
}));

/** True when the signed-in user has at least this role. */
export function useCan(role: Role): boolean {
  const current = useAuth((s) => s.session?.role);
  return current !== undefined && ROLES.indexOf(current) >= ROLES.indexOf(role);
}

export function syncSession(event: StorageEvent) {
  if (event.key === KEY || event.key === null) void useAuth.getState().restore();
}

export function authHeader(): Record<string, string> {
  const token = useAuth.getState().session?.token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
