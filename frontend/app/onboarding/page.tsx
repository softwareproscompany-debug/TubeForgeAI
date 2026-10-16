"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type {
  Channel,
  ChannelConnectResponse,
  OnboardingProgress,
  OnboardingStep,
} from "../../lib/types";
import { AuthCard, FormError, TextField } from "../../components/AuthBits";
import ProtectedRoute from "../../components/ProtectedRoute";

const STEPS: { id: OnboardingStep; label: string }[] = [
  { id: "welcome", label: "Welcome" },
  { id: "youtube", label: "Connect YouTube" },
  { id: "channel_setup", label: "Channel Setup" },
  { id: "first_project", label: "First Project" },
];

const NICHES = [
  "Tech & Gadgets",
  "Finance & Investing",
  "Health & Fitness",
  "Education",
  "Entertainment",
  "Gaming",
  "Travel",
  "Food & Cooking",
  "Business",
  "Other",
];

function stepIndex(step: OnboardingStep): number {
  return STEPS.findIndex((s) => s.id === step);
}

export default function OnboardingPage() {
  return (
    <ProtectedRoute>
      <OnboardingWizard />
    </ProtectedRoute>
  );
}

function OnboardingWizard() {
  const router = useRouter();
  const { user } = useAuth();
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Step 2 (youtube) state
  const [connecting, setConnecting] = useState(false);
  // Step 3 (channel_setup) state
  const [channel, setChannel] = useState<Channel | null>(null);
  const [niche, setNiche] = useState("");
  const [schedule, setSchedule] = useState("weekly");
  const [brandColor, setBrandColor] = useState("#00d4ff");
  // Step 4 (first_project) state
  const [projectTitle, setProjectTitle] = useState("");
  const [projectIdea, setProjectIdea] = useState("");
  const [projectFormat, setProjectFormat] = useState("tutorial");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await api.get<OnboardingProgress>("/onboarding/progress");
      setProgress(p);
      if (p.is_complete) {
        router.replace("/overview");
        return;
      }
      // Preload channel for steps 3-4 if youtube is already connected
      if (p.completed_steps.includes("youtube")) {
        try {
          const channels = await api.get<Channel[]>("/channels");
          const list = Array.isArray(channels) ? channels : [];
          const active = list.find((c) => c.is_active) ?? list[0] ?? null;
          setChannel(active);
          if (active?.brand_config) {
            const bc = active.brand_config as Record<string, unknown>;
            if (typeof bc.niche === "string") setNiche(bc.niche);
            if (typeof bc.upload_schedule === "string") setSchedule(bc.upload_schedule);
            if (typeof bc.brand_color === "string") setBrandColor(bc.brand_color);
          }
        } catch {
          // no channels yet — fine
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load onboarding.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  const completeStep = async (step: OnboardingStep) => {
    setBusy(true);
    setError(null);
    try {
      const p = await api.post<OnboardingProgress>("/onboarding/complete-step", {
        step,
      });
      setProgress(p);
      if (p.is_complete) router.replace("/overview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save progress.");
    } finally {
      setBusy(false);
    }
  };

  const skipAll = async () => {
    setBusy(true);
    try {
      await api.post("/onboarding/skip", {});
      router.replace("/overview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to skip.");
    } finally {
      setBusy(false);
    }
  };

  const startYouTubeConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      // Create a draft channel, then redirect to Google OAuth.
      const res = await api.post<ChannelConnectResponse>("/channels/connect", {
        title: user?.username ? `${user.username}'s channel` : "My YouTube channel",
      });
      sessionStorage.setItem("tf_onboarding_channel_id", res.channel_id);
      window.location.href = res.authorization_url;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not start YouTube connection."
      );
      setConnecting(false);
    }
  };

  const saveChannelSetup = async () => {
    if (!channel) {
      setError("Connect your YouTube channel first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.patch<Channel>(`/channels/${channel.id}`, {
        brand_config: {
          ...(channel.brand_config || {}),
          niche,
          upload_schedule: schedule,
          brand_color: brandColor,
        },
      });
      setChannel(updated);
      await completeStep("channel_setup");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save channel setup.");
    } finally {
      setBusy(false);
    }
  };

  const createFirstProject = async () => {
    if (!channel) {
      setError("Connect your YouTube channel first.");
      return;
    }
    if (!projectTitle.trim()) {
      setError("Give your first project a title.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/projects", {
        channel: channel.id,
        title: projectTitle.trim(),
        content_idea: projectIdea.trim() || null,
        format: projectFormat,
        brief: projectIdea.trim(),
        target_duration_seconds: 600,
        aspect_ratio: "16:9",
        language: channel.default_language || "en",
      });
      await completeStep("first_project");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project.");
    } finally {
      setBusy(false);
    }
  };

  if (loading || !progress) {
    return (
      <AuthCard title="Setting up your studio…" className="max-w-lg">
        <p className="text-sm text-studio-muted">Loading onboarding…</p>
        {error && <FormError message={error} />}
      </AuthCard>
    );
  }

  const idx = stepIndex(progress.current_step);
  const step = STEPS[idx] ?? STEPS[0];

  return (
    <AuthCard
      title="Set up TubeForge"
      subtitle={`Step ${idx + 1} of ${STEPS.length}: ${step.label}`}
      className="max-w-lg"
    >
      {/* Progress bar */}
      <div className="flex gap-1.5 mb-1">
        {STEPS.map((s, i) => (
          <div
            key={s.id}
            className={`h-1.5 flex-1 rounded-full ${
              i < idx || progress.completed_steps.includes(s.id)
                ? "bg-cyan-400"
                : i === idx
                  ? "bg-cyan-400/50"
                  : "bg-studio-border"
            }`}
          />
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-studio-faint mb-5">
        {STEPS.map((s, i) => (
          <span key={s.id} className={i === idx ? "text-cyan-300" : ""}>
            {s.label}
          </span>
        ))}
      </div>

      {error && <FormError message={error} />}

      {step.id === "welcome" && (
        <div className="space-y-4">
          <p className="text-sm text-studio-text">
            Welcome{user?.username ? `, ${user.username}` : ""}! TubeForge turns
            your ideas into published YouTube videos — research, script,
            voiceover, editing, and publishing, all driven by AI.
          </p>
          <ul className="text-sm text-studio-muted space-y-2">
            <li>🔗 <span className="text-studio-text">Connect your YouTube channel</span> — secure OAuth, we never see your password</li>
            <li>🎨 <span className="text-studio-text">Set up your channel</span> — niche, schedule, and branding</li>
            <li>🚀 <span className="text-studio-text">Create your first project</span> — we guide you through it</li>
          </ul>
          <button
            onClick={() => completeStep("welcome")}
            disabled={busy}
            className="w-full min-h-[48px] rounded-lg bg-cyan-500 py-2.5 text-sm font-medium text-black hover:bg-cyan-400 disabled:opacity-50 touch-manipulation"
          >
            {busy ? "Saving…" : "Let's go →"}
          </button>
        </div>
      )}

      {step.id === "youtube" && (
        <div className="space-y-4">
          <p className="text-sm text-studio-muted">
            Link your YouTube channel so TubeForge can upload videos on your
            behalf. You'll be taken to Google to grant permission — we only
            request the scopes needed for uploading and managing your videos.
          </p>
          <div className="rounded-lg border border-studio-border bg-studio-panel p-3 text-xs text-studio-muted">
            Requested permissions: view your channel · upload videos · manage
            videos. Tokens are encrypted at rest and you can disconnect anytime
            from Settings.
          </div>
          <button
            onClick={startYouTubeConnect}
            disabled={connecting}
            className="w-full min-h-[48px] rounded-lg bg-red-600 py-3 text-base font-medium text-white hover:bg-red-500 disabled:opacity-50 touch-manipulation"
          >
            {connecting ? "Opening Google…" : "▶ Connect with YouTube"}
          </button>
          <button
            onClick={() => completeStep("youtube")}
            disabled={busy}
            className="w-full text-xs text-studio-faint underline hover:text-studio-muted"
          >
            I'll connect later — continue without YouTube
          </button>
        </div>
      )}

      {step.id === "channel_setup" && (
        <div className="space-y-4">
          {!channel ? (
            <p className="text-sm text-studio-muted">
              No connected channel found.{" "}
              <button
                onClick={() => setProgress({ ...progress, current_step: "youtube" })}
                className="underline text-cyan-300"
              >
                Go back and connect YouTube
              </button>
            </p>
          ) : (
            <>
              <p className="text-sm text-studio-muted">
                Channel: <span className="text-studio-text font-medium">{channel.title}</span>
              </p>
              <div>
                <label className="text-xs text-studio-muted">Content niche</label>
                <select
                  value={niche}
                  onChange={(e) => setNiche(e.target.value)}
                  className="mt-1 w-full min-h-[48px] rounded-lg border border-studio-border bg-studio-panel px-3 py-2 text-base text-studio-text touch-manipulation"
                >
                  <option value="">Select a niche…</option>
                  {NICHES.map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-studio-muted">Upload schedule</label>
                <select
                  value={schedule}
                  onChange={(e) => setSchedule(e.target.value)}
                  className="mt-1 w-full min-h-[48px] rounded-lg border border-studio-border bg-studio-panel px-3 py-2 text-base text-studio-text touch-manipulation"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Every 2 weeks</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-studio-muted">Brand color</label>
                <div className="mt-1 flex items-center gap-3">
                  <input
                    type="color"
                    value={brandColor}
                    onChange={(e) => setBrandColor(e.target.value)}
                    className="h-9 w-14 cursor-pointer rounded border border-studio-border bg-studio-panel"
                  />
                  <span className="text-xs text-studio-faint font-mono">{brandColor}</span>
                </div>
              </div>
              <button
                onClick={saveChannelSetup}
                disabled={busy}
                className="w-full min-h-[48px] rounded-lg bg-cyan-500 py-2.5 text-sm font-medium text-black hover:bg-cyan-400 disabled:opacity-50 touch-manipulation"
              >
                {busy ? "Saving…" : "Save & continue →"}
              </button>
            </>
          )}
        </div>
      )}

      {step.id === "first_project" && (
        <div className="space-y-4">
          <p className="text-sm text-studio-muted">
            Let's create your first project. Give it a title and an idea —
            TubeForge's AI will research it, write the script, and build the
            video.
          </p>
          <TextField
            id="first-project-title"
            label="Video title"
            value={projectTitle}
            onChange={(e) => setProjectTitle(e.target.value)}
            placeholder="e.g. 10 AI Tools That Save Me 20 Hours a Week"
          />
          <div>
            <label className="text-xs text-studio-muted">Format</label>
            <select
              value={projectFormat}
              onChange={(e) => setProjectFormat(e.target.value)}
              className="mt-1 w-full min-h-[48px] rounded-lg border border-studio-border bg-studio-panel px-3 py-2 text-base text-studio-text touch-manipulation"
            >
              <option value="tutorial">Tutorial / How-to</option>
              <option value="listicle">Listicle / Top 10</option>
              <option value="explainer">Explainer</option>
              <option value="review">Review</option>
              <option value="vlog">Vlog-style</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-studio-muted">Your idea (optional)</label>
            <textarea
              value={projectIdea}
              onChange={(e) => setProjectIdea(e.target.value)}
              rows={3}
              placeholder="What should this video be about?"
              className="mt-1 w-full rounded-lg border border-studio-border bg-studio-panel px-3 py-2 text-base text-studio-text"
            />
          </div>
          <button
            onClick={createFirstProject}
            disabled={busy}
            className="w-full min-h-[48px] rounded-lg bg-cyan-500 py-2.5 text-sm font-medium text-black hover:bg-cyan-400 disabled:opacity-50 touch-manipulation"
          >
            {busy ? "Creating…" : "🚀 Create my first project"}
          </button>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between border-t border-studio-border pt-4">
        {idx > 0 ? (
          <button
            onClick={() =>
              setProgress({ ...progress, current_step: STEPS[idx - 1].id })
            }
            className="text-xs text-studio-muted underline hover:text-studio-text touch-manipulation py-2 px-1"
          >
            ← Back
          </button>
        ) : (
          <span />
        )}
        {!progress.is_complete && (
          <button
            onClick={skipAll}
            disabled={busy}
            className="text-xs text-studio-faint underline hover:text-studio-muted touch-manipulation py-2 px-1"
          >
            Skip setup for now
          </button>
        )}
      </div>
    </AuthCard>
  );
}
