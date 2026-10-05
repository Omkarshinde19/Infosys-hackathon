"use client";

import { useEffect } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { useAuth } from "@/lib/auth";
import { useLiveConnection } from "@/lib/live";

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  useLiveConnection();
  useEffect(() => useAuth.getState().restore(), []);
  return (
    <div className="min-h-svh bg-[radial-gradient(ellipse_at_top_right,var(--bg-2),var(--bg)_60%)] bg-fixed">
      <Sidebar />
      <main className="ml-68 px-6 py-6 lg:px-10 print:m-0 print:p-0">{children}</main>
    </div>
  );
}
