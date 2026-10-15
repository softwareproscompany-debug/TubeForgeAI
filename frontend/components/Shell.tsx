// App shell: public auth routes render without the sidebar/topbar chrome.
"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

const PUBLIC_PATHS = ["/login", "/register", "/forgot-password"];

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (PUBLIC_PATHS.includes(pathname)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-10">
        {children}
      </div>
    );
  }

  return (
    <>
      <Sidebar />
      <div className="pl-60 min-h-screen flex flex-col">
        <TopBar />
        <main className="flex-1 px-6 py-6 max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </>
  );
}
