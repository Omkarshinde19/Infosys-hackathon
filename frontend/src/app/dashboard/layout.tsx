"use client";

import { Sidebar } from "@/components/dashboard/Sidebar";
import { useLiveConnection } from "@/lib/live";

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  useLiveConnection();
  return (
    <div className="min-h-svh bg-[radial-gradient(ellipse_at_top_right,var(--bg-2),var(--bg)_60%)] bg-fixed">
      <Sidebar />
      <main className="ml-68 px-6 py-6 lg:px-10">{children}</main>
    </div>
  );
}
