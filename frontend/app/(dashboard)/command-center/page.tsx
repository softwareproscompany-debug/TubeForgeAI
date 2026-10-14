"use client";

import { useEffect, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { Channel, Plan, Project, WorkflowRun } from "../../../lib/types";
import PlanConfirmation from "../../../components/PlanConfirmation";
import StatusBadge from "../../../components/StatusBadge";

export default function CommandCenterPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [channelId, setChannelId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startedRun, setStartedRun] = useState<WorkflowRun | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const ch = asList(await api.get<Channel[]>("/channels"));
        setChannels(ch);
        if (ch.length > 0) setChannelId(ch[0].id);
        const pr = asList(await api.get<Project[]>("/projects"));
        setProjects(pr);
        if (pr.length > 0) setProjectId(pr[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load.");
      }
    })();
  }, []);

  const generatePlan = async () => {
    if (!projectId || !prompt.trim()) return;
    setLoading(true);
    setError(null);
    setPlan(null);
    setStartedRun(null);
    try {
      const p = await api.post<Plan>(`/projects/${projectId}/generate-plan`, {
        prompt: prompt.trim(),
        channel_id: channelId || undefined,
      });
      setPlan(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Plan generation failed.");
    } finally {
      setLoading(false);
    }
  };

  const start = async () => {
    if (!projectId) return;
    setStarting(true);
    setError(null);
    try {
      const run = await api.post<WorkflowRun>(`/projects/${projectId}/workflows`, {
        workflow_type: "full_production",
      });
      setStartedRun(run);
      setPlan(null);
      setPrompt("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start workflow.");
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold text-studio-text">AI Command Center</h1>
        <p className="text-sm text-studio-muted mt-1">
          Describe what you want to produce in plain language. Consequential actions always need your
          confirmation — reviewing a plan changes nothing until you press Start.
        </p>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>
      )}

      <div className="bg-studio-panel border border-studio-border rounded-lg p-5 space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <label className="block text-sm">
            <span className="text-studio-muted">Channel</span>
            <select
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              className="mt-1 w-full bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 text-studio-text"
            >
              {channels.length === 0 && <option value="">No channels connected</option>}
              {channels.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-studio-muted">Project</span>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="mt-1 w-full bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 text-studio-text"
            >
              {projects.length === 0 && <option value="">No projects — create one first</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.title}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="block text-sm">
          <span className="text-studio-muted">What should the AI produce?</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            placeholder="e.g. A 10-minute explainer on how container ships work, aimed at beginners, upbeat tone…"
            className="mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text placeholder:text-studio-faint focus:border-accent/60 outline-none"
          />
        </label>
        <button
          onClick={generatePlan}
          disabled={loading || !prompt.trim() || !projectId}
          className="bg-accent text-black font-medium px-5 py-2 rounded-md hover:brightness-110 disabled:opacity-50"
        >
          {loading ? "Generating plan…" : "Generate plan"}
        </button>
      </div>

      {plan && projectId && (
        <PlanConfirmation
          plan={plan}
          projectId={projectId}
          onStart={start}
          onDiscard={() => setPlan(null)}
          starting={starting}
        />
      )}

      {startedRun && (
        <div className="bg-studio-panel border border-emerald-500/40 rounded-lg p-4 flex items-center gap-3">
          <StatusBadge status={startedRun.status} />
          <span className="text-sm text-studio-text">
            Workflow started — track it in <a href="/queue" className="text-accent hover:underline">Production Queue</a>.
          </span>
        </div>
      )}
    </div>
  );
}
