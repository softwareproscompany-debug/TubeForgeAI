"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, asList } from "../../../lib/api";
import type { Channel, Project } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

// Creation wizard: 7 steps per spec §3.6 —
// 1 Objective → 2 Channel/format → 3 Script → 4 Visual direction →
// 5 AI resources → 6 Production plan → 7 Execution.

const STEPS = [
  "Objective",
  "Channel & format",
  "Script",
  "Visual direction",
  "AI resources",
  "Production plan",
  "Execution",
];

interface Draft {
  objective: string;
  channel: string;
  title: string;
  format: string;
  aspect_ratio: string;
  language: string;
  target_duration_seconds: number;
  script_direction: string;
  visual_direction: string;
  model_preferences: string;
  plan_notes: string;
}

const EMPTY_DRAFT: Draft = {
  objective: "",
  channel: "",
  title: "",
  format: "LONG_FORM",
  aspect_ratio: "16:9",
  language: "en",
  target_duration_seconds: 600,
  script_direction: "",
  visual_direction: "",
  model_preferences: "",
  plan_notes: "",
};

// Backend Project.FORMAT_CHOICES — the wizard may only offer values the API accepts.
const FORMAT_OPTIONS = ["LONG_FORM", "SHORT", "DOCUMENTARY", "EXPLAINER", "CINEMATIC"];

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [creating, setCreating] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [p, c] = await Promise.all([
          api.get<Project[]>("/projects"),
          api.get<Channel[]>("/channels").catch(() => [] as Channel[]),
        ]);
        setProjects(asList(p));
        const ch = asList(c);
        setChannels(ch);
        if (ch.length > 0) setDraft((d) => ({ ...d, channel: d.channel || ch[0].id }));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load projects.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const set = (k: keyof Draft, v: string | number) => setDraft((d) => ({ ...d, [k]: v }));

  const create = async () => {
    setCreating(true);
    setWizardError(null);
    try {
      const p = await api.post<Project>("/projects", {
        channel: draft.channel,
        title: draft.title || draft.objective.slice(0, 80) || "Untitled project",
        brief: draft.objective,
        format: draft.format,
        target_duration_seconds: Number(draft.target_duration_seconds),
        aspect_ratio: draft.aspect_ratio,
        language: draft.language,
        settings: {
          script_direction: draft.script_direction,
          visual_direction: draft.visual_direction,
          model_preferences: draft.model_preferences,
          plan_notes: draft.plan_notes,
        },
      });
      setProjects((prev) => [p, ...prev]);
      setWizardOpen(false);
      setStep(0);
      setDraft(EMPTY_DRAFT);
    } catch (e) {
      setWizardError(e instanceof Error ? e.message : "Creation failed.");
    } finally {
      setCreating(false);
    }
  };

  const canNext = () => {
    if (step === 0) return draft.objective.trim().length > 0;
    if (step === 1) return !!draft.channel && !!draft.title.trim();
    return true;
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-studio-text">Projects</h1>
        <button
          onClick={() => { setWizardOpen(true); setStep(0); setWizardError(null); }}
          className="bg-accent text-black font-medium text-sm px-4 py-2 min-h-[44px] rounded-md hover:brightness-110"
        >
          + New project
        </button>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading projects…</div>}

      {!loading && projects.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">No projects yet</p>
          <p className="text-sm text-studio-muted mt-1">Create a project with the 7-step wizard, or generate one from a research idea.</p>
        </div>
      )}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {projects.map((p) => (
          <Link key={p.id} href={`/projects/${p.id}`}
            className="bg-studio-panel border border-studio-border rounded-lg p-4 hover:border-accent/50 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="font-medium text-studio-text">{p.title}</div>
              <StatusBadge status={p.status} />
            </div>
            <div className="text-sm text-studio-muted mt-1 line-clamp-2">{p.brief}</div>
            <div className="text-xs text-studio-faint mt-2">
              {p.format} · {p.aspect_ratio} · {Math.round(p.target_duration_seconds / 60)} min · {p.language}
            </div>
          </Link>
        ))}
      </div>

      {wizardOpen && (
        <div className="fixed inset-0 z-40 p-4">
          <div className="absolute inset-0 bg-black/70" onClick={() => setWizardOpen(false)} />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[calc(100vw-2rem)] sm:max-w-2xl bg-studio-panel border border-studio-border rounded-lg p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="font-semibold text-studio-text text-sm sm:text-base">New project — step {step + 1} of 7: {STEPS[step]}</h2>
              <button onClick={() => setWizardOpen(false)} className="text-studio-muted hover:text-studio-text text-xl min-h-[44px] min-w-[44px] shrink-0" aria-label="Close">×</button>
            </div>
            <div className="flex gap-1 mb-5">
              {STEPS.map((s, i) => (
                <div key={s} title={s} className={`h-1.5 flex-1 rounded ${i <= step ? "bg-accent" : "bg-studio-panel2"}`} />
              ))}
            </div>

            <div className="space-y-4 min-h-56">
              {step === 0 && (
                <label className="block text-sm">
                  <span className="text-studio-muted">Objective — what is this video for?</span>
                  <textarea value={draft.objective} onChange={(e) => set("objective", e.target.value)} rows={5}
                    placeholder="e.g. Grow the channel with a beginner-friendly explainer that ranks for 'how shipping works'"
                    className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text placeholder:text-studio-faint" />
                </label>
              )}
              {step === 1 && (
                <>
                  <label className="block text-sm">
                    <span className="text-studio-muted">Channel</span>
                    <select value={draft.channel} onChange={(e) => set("channel", e.target.value)}
                      className="mt-1 w-full bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 text-studio-text">
                      {channels.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                    </select>
                  </label>
                  <label className="block text-sm">
                    <span className="text-studio-muted">Title</span>
                    <input value={draft.title} onChange={(e) => set("title", e.target.value)}
                      className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text" />
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label className="block text-sm">
                      <span className="text-studio-muted">Format</span>
                      <select value={draft.format} onChange={(e) => set("format", e.target.value)}
                        className="mt-1 w-full bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 text-studio-text">
                        {FORMAT_OPTIONS.map((f) => (
                          <option key={f} value={f}>{f.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-sm">
                      <span className="text-studio-muted">Aspect ratio</span>
                      <select value={draft.aspect_ratio} onChange={(e) => set("aspect_ratio", e.target.value)}
                        className="mt-1 w-full bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 text-studio-text">
                        <option value="16:9">16:9</option>
                        <option value="9:16">9:16</option>
                        <option value="1:1">1:1</option>
                      </select>
                    </label>
                    <label className="block text-sm">
                      <span className="text-studio-muted">Language</span>
                      <input value={draft.language} onChange={(e) => set("language", e.target.value)}
                        className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text" />
                    </label>
                    <label className="block text-sm">
                      <span className="text-studio-muted">Target duration (seconds)</span>
                      <input type="number" min={15} value={draft.target_duration_seconds}
                        onChange={(e) => set("target_duration_seconds", Number(e.target.value))}
                        className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text" />
                    </label>
                  </div>
                </>
              )}
              {step === 2 && (
                <label className="block text-sm">
                  <span className="text-studio-muted">Script direction — tone, structure, key points</span>
                  <textarea value={draft.script_direction} onChange={(e) => set("script_direction", e.target.value)} rows={5}
                    className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text" />
                </label>
              )}
              {step === 3 && (
                <label className="block text-sm">
                  <span className="text-studio-muted">Visual direction — style, references, palette</span>
                  <textarea value={draft.visual_direction} onChange={(e) => set("visual_direction", e.target.value)} rows={5}
                    className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text" />
                </label>
              )}
              {step === 4 && (
                <label className="block text-sm">
                  <span className="text-studio-muted">AI resources — model/provider preferences (optional)</span>
                  <textarea value={draft.model_preferences} onChange={(e) => set("model_preferences", e.target.value)} rows={4}
                    placeholder="e.g. prefer local image model for storyboards, cloud for narration"
                    className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text placeholder:text-studio-faint" />
                  <p className="text-xs text-studio-faint mt-2">Budgets are enforced server-side per resource — the wizard records preferences only.</p>
                </label>
              )}
              {step === 5 && (
                <label className="block text-sm">
                  <span className="text-studio-muted">Production plan notes — stages, approvals, constraints</span>
                  <textarea value={draft.plan_notes} onChange={(e) => set("plan_notes", e.target.value)} rows={5}
                    className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text" />
                </label>
              )}
              {step === 6 && (
                <div className="text-sm space-y-2">
                  <p className="text-studio-text font-medium">Ready to create this project?</p>
                  <ul className="text-studio-muted space-y-1">
                    <li><span className="text-studio-faint">Objective:</span> {draft.objective}</li>
                    <li><span className="text-studio-faint">Title:</span> {draft.title || "(from objective)"}</li>
                    <li><span className="text-studio-faint">Format:</span> {draft.format} · {draft.aspect_ratio} · {draft.target_duration_seconds}s · {draft.language}</li>
                  </ul>
                  <p className="text-xs text-studio-faint">Creating the project drafts it only — nothing is generated or published until you start a workflow.</p>
                </div>
              )}
            </div>

            {wizardError && <div className="text-sm text-red-400 mt-3">{wizardError}</div>}

            <div className="flex justify-between gap-2 mt-6">
              <button onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}
                className="text-sm px-4 py-2 min-h-[44px] rounded-md border border-studio-border text-studio-text disabled:opacity-40">
                Back
              </button>
              {step < 6 ? (
                <button onClick={() => setStep((s) => s + 1)} disabled={!canNext()}
                  className="text-sm bg-accent text-black font-medium px-4 py-2 min-h-[44px] rounded-md disabled:opacity-50">
                  Continue
                </button>
              ) : (
                <button onClick={create} disabled={creating || !canNext()}
                  className="text-sm bg-accent text-black font-medium px-4 py-2 min-h-[44px] rounded-md disabled:opacity-50">
                  {creating ? "Creating…" : "Create project"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
