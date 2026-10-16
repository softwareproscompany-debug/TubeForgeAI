"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, asList, fmtDate } from "../../../lib/api";
import type { Project, SwarmRun } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

const AGENT_ROLES = ["researcher", "writer", "editor", "publisher", "critic"];

export default function SwarmPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<SwarmRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState("");
  const [topic, setTopic] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [p, r] = await Promise.all([
          api.get<Project[]>("/projects").then(asList),
          api.get<SwarmRun[]>("/swarm/runs"),
        ]);
        setProjects(p);
        setRuns(r);
        if (p.length > 0) setProjectId(p[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function startRun(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId || !topic.trim() || starting) return;
    setStarting(true);
    setStartError(null);
    try {
      const run = await api.post<SwarmRun>("/swarm/runs", {
        project_id: projectId,
        topic: topic.trim(),
      });
      router.push(`/swarm/${run.id}`);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : "Failed to start run");
      setStarting(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-studio-muted">Loading swarm…</div>;
  }

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-studio-text">Agent Swarm</h1>
        <p className="text-studio-muted mt-1">
          Five specialist agents plan your video together — research, write,
          edit, publish, and critique — with every message between them
          recorded.
        </p>
      </div>

      {error && (
        <div className="rounded border border-red-500/40 bg-red-500/10 text-red-400 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <form
        onSubmit={startRun}
        className="rounded-xl border border-studio-border bg-studio-panel p-4 sm:p-6 space-y-4"
      >
        <h2 className="text-lg font-semibold text-studio-text">Start a new run</h2>
        <div>
          <label className="block text-sm text-studio-muted mb-1">Project</label>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="w-full text-base rounded-lg bg-studio-panel2 border border-studio-border px-3 py-2.5 text-studio-text"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-studio-muted mb-1">Topic</label>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            rows={3}
            placeholder="e.g. How to brew pour-over coffee for beginners"
            className="w-full text-base rounded-lg bg-studio-panel2 border border-studio-border px-3 py-2.5 text-studio-text placeholder:text-studio-muted/60"
          />
        </div>
        {startError && (
          <div className="rounded border border-red-500/40 bg-red-500/10 text-red-400 px-4 py-3 text-sm">
            {startError}
          </div>
        )}
        <button
          type="submit"
          disabled={starting || !projectId || !topic.trim()}
          className="w-full sm:w-auto min-h-[48px] rounded-lg bg-accent px-5 py-2.5 font-semibold text-black disabled:opacity-50 touch-manipulation"
        >
          {starting ? "Starting…" : "Start swarm run"}
        </button>
        <div className="flex flex-wrap gap-2 pt-1">
          {AGENT_ROLES.map((role) => (
            <span
              key={role}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs border bg-studio-panel2 text-studio-muted border-studio-border capitalize"
            >
              {role}
            </span>
          ))}
        </div>
      </form>

      <div>
        <h2 className="text-lg font-semibold text-studio-text mb-3">Recent runs</h2>
        {runs.length === 0 ? (
          <p className="text-studio-muted text-sm">No runs yet.</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <Link
                key={run.id}
                href={`/swarm/${run.id}`}
                className="block rounded-xl border border-studio-border bg-studio-panel px-4 py-3 hover:border-accent/50 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-studio-text font-medium truncate">
                      {run.topic}
                    </div>
                    <div className="text-xs text-studio-muted mt-0.5">
                      {run.project_title} · {fmtDate(run.started_at)} ·{" "}
                      {run.current_stage}
                    </div>
                  </div>
                  <StatusBadge status={run.status.toUpperCase()} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
