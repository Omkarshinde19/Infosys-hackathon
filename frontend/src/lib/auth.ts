"use client";

import { create } from "zustand";

export type Role = "viewer" | "operator" | "admin";
export type Session = { token: string; username: string; role: Role };

const ROLES: Role[] = ["viewer", "operator", "admin"];
const KEY = "netheal-session";

function saved(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null");
  } catch {
    return null;
  }
}

type AuthState = {
  session: Session | null;
  restore: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  session: null, // filled by restore() after hydration, so server and client renders match
  restore: () => set({ session: saved() }),
  login: async (username, password) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail ?? "Login failed");
    const session: Session = await res.json();
    localStorage.setItem(KEY, JSON.stringify(session));
    set({ session });
  },
  logout: () => {
    localStorage.removeItem(KEY);
    set({ session: null });
  },
}));

/** True when the signed-in user has at least this role. */
export function useCan(role: Role): boolean {
  const current = useAuth((s) => s.session?.role);
  return current !== undefined && ROLES.indexOf(current) >= ROLES.indexOf(role);
}

export function authHeader(): Record<string, string> {
  const token = useAuth.getState().session?.token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
