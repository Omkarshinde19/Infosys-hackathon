"use client";

import { useEffect } from "react";
import { AskButton } from "@/components/dashboard/AskButton";
import { DataStatus } from "@/components/dashboard/DataStatus";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { syncSession, useAuth } from "@/lib/auth";
import { useLiveConnection } from "@/lib/live";

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  useLiveConnection();
  useEffect(() => {
    void useAuth.getState().restore();
    window.addEventListener("storage", syncSession);
    return () => window.removeEventListener("storage", syncSession);
  }, []);
  return (
    <div className="min-h-svh bg-[radial-gradient(ellipse_at_top_right,var(--bg-2),var(--bg)_60%)] bg-fixed">
      <Sidebar />
      <main id="dashboard-main" className="px-4 pt-20 pb-6 md:ml-68 md:px-6 md:pt-6 lg:px-10 print:m-0 print:p-0"><DataStatus />{children}</main>
      <div id="dashboard-assistant"><AskButton /></div>
    </div>
  );
}
