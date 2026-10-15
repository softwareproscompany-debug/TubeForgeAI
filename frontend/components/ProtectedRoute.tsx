// Route guard for the (dashboard) group: no session → /login.
// Public routes (/login, /register, /forgot-password) stay untouched.

"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { loading, authed } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !authed) router.replace("/login");
  }, [loading, authed, router]);

  if (loading || !authed) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <p className="text-sm text-studio-muted animate-pulse">
          Checking session…
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
