"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { OnboardingProgress } from "../lib/types";

/**
 * Redirects authenticated users with incomplete onboarding to /onboarding,
 * unless they're already there. Users who skipped or finished pass through.
 */
export default function OnboardingGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { authed, loading } = useAuth();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (loading || !authed) return;
    if (pathname.startsWith("/onboarding")) {
      setChecked(true);
      return;
    }
    let cancelled = false;
    api
      .get<OnboardingProgress>("/onboarding/progress")
      .then((p) => {
        if (cancelled) return;
        if (!p.is_complete) {
          router.replace("/onboarding");
        } else {
          setChecked(true);
        }
      })
      .catch(() => {
        // If the progress endpoint fails, don't block the dashboard.
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [loading, authed, pathname, router]);

  if (loading || !authed || !checked) {
    return (
      <div className="text-studio-muted text-sm animate-pulse">
        Checking setup…
      </div>
    );
  }
  return <>{children}</>;
}
