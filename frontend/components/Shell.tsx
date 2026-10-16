// App shell: public auth routes render without the sidebar/topbar chrome.
"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

// /onboarding is auth-gated by its own ProtectedRoute but renders chrome-less
// like the auth pages (no sidebar during setup).
const PUBLIC_PATHS = ["/login", "/register", "/forgot-password", "/onboarding"];

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // Mobile drawer state for the sidebar (< md). Desktop keeps the static sidebar.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-10">
        {children}
      </div>
    );
  }

  return (
    <>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="md:pl-60 min-h-screen flex flex-col">
        <TopBar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 px-4 py-4 md:px-6 md:py-6 max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </>
  );
}
