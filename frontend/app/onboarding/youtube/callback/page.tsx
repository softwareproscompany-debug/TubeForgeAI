"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "../../../../lib/api";
import { AuthCard, FormError } from "../../../../components/AuthBits";
import ProtectedRoute from "../../../../components/ProtectedRoute";

/**
 * Handles the return from Google OAuth.
 *
 * Google redirects here with ?code=...&state=... The signed state embeds
 * the draft channel id; the channel id is also kept in sessionStorage from
 * when the flow started (the callback URL must match the channel in state).
 */
export default function YouTubeCallbackPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={<AuthCard title="Connecting YouTube…"><p className="text-sm text-studio-muted">Loading…</p></AuthCard>}>
        <CallbackHandler />
      </Suspense>
    </ProtectedRoute>
  );
}

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const oauthError = searchParams.get("error");

      if (oauthError) {
        setError(
          `Google authorization failed: ${searchParams.get("error_description") || oauthError}`
        );
        return;
      }
      if (!code || !state) {
        setError("Missing authorization code. Please try connecting again.");
        return;
      }
      const channelId = sessionStorage.getItem("tf_onboarding_channel_id");
      if (!channelId) {
        setError(
          "Lost track of which channel was being connected. Please restart the YouTube step."
        );
        return;
      }
      try {
        await api.get(
          `/channels/${channelId}/oauth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
        );
        sessionStorage.removeItem("tf_onboarding_channel_id");
        // Mark the youtube step complete so the wizard advances to channel setup.
        await api.post("/onboarding/complete-step", { step: "youtube" });
        router.replace("/onboarding");
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : "Could not complete the YouTube connection."
        );
      }
    };
    run();
  }, [router, searchParams]);

  return (
    <AuthCard title="Connecting YouTube…">
      {error ? (
        <div className="space-y-4">
          <FormError message={error} />
          <button
            onClick={() => router.replace("/onboarding")}
            className="w-full min-h-[48px] rounded-lg bg-cyan-500 py-2.5 text-sm font-medium text-black hover:bg-cyan-400 touch-manipulation"
          >
            Back to setup
          </button>
        </div>
      ) : (
        <p className="text-sm text-studio-muted">
          Finishing the connection with Google…
        </p>
      )}
    </AuthCard>
  );
}
