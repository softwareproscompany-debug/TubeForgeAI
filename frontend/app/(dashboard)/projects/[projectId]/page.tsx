"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, asList, fmtDate } from "../../../../lib/api";
import type { Project, Scene, ScriptVersion, WorkflowRun } from "../../../../lib/types";
import StatusBadge from "../../../../components/StatusBadge";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [project, setProject] = useState<Project | null>(null);
  const [scripts, setScripts] = useState<ScriptVersion[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, sc, sn, wf] = await Promise.all([
        api.get<Project>(`/projects/${projectId}`),
        api.get<ScriptVersion[]>(`/projects/${projectId}/scripts`).catch(() => [] as ScriptVersion[]),
        api.get<Scene[]>(`/projects/${projectId}/scenes`).catch(() => [] as Scene[]),
        api.get<WorkflowRun[]>(`/workflows?project_id=${projectId}`).catch(() => [] as WorkflowRun[]),
      ]);
      setProject(p);
      // Backend ScriptVersion uses `version_number`; Scene uses `position`.
      setScripts(asList(sc).sort((a, b) => b.version_number - a.version_number));
      setScenes(asList(sn).sort((a, b) => a.position - b.position));
      setWorkflows(asList(wf));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [projectId]);

  const approveScript = async (sid: string) => {
    setMsg(null);
    try {
      await api.post(`/projects/${projectId}/scripts/${sid}/approve`);
      setMsg("Script approved.");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Approval failed.");
    }
  };

  const del = async () => {
    if (!window.confirm("Delete this project? This cannot be undone.")) return;
    try {
      await api.del(`/projects/${projectId}`);
      window.location.href = "/projects";
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Delete failed.");
    }
  };

  if (loading) return <div className="text-studio-muted text-sm">Loading project…</div>;
  if (error || !project)
    return <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 text-sm text-red-300">{error || "Project not found."}</div>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link href="/projects" className="text-xs text-accent hover:underline min-h-[44px] inline-flex items-center">← Projects</Link>
          <h1 className="text-xl font-semibold text-studio-text mt-1 break-words">{project.title}</h1>
          <div className="text-xs text-studio-faint mt-1">
            {project.format} · {project.aspect_ratio} · {Math.round(project.target_duration_seconds / 60)} min · {project.language}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={project.status} />
          <button onClick={del} className="text-xs text-red-400 hover:underline min-h-[44px] inline-flex items-center">Delete</button>
        </div>
      </div>

      {msg && <div className="text-sm text-studio-muted bg-studio-panel border border-studio-border rounded p-3">{msg}</div>}

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-2">Brief</h2>
        <p className="text-sm text-studio-muted whitespace-pre-wrap">{project.brief || "No brief."}</p>
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <h2 className="font-medium text-studio-text mb-3">Script versions</h2>
        {scripts.length === 0 ? (
          <p className="text-sm text-studio-faint">No script versions yet. Scripts are generated when a scripting workflow runs.</p>
        ) : (
          <ul className="space-y-2">
            {scripts.map((s) => (
              <li key={s.id} className="bg-studio-panel2 border border-studio-border rounded p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-sm text-studio-text font-medium">v{s.version_number} — {s.fact_check_status}</div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={s.approval_status} />
                    {s.approval_status.toUpperCase() !== "APPROVED" && (
                      <button onClick={() => approveScript(s.id)} className="text-xs text-accent hover:underline min-h-[44px] inline-flex items-center">Approve</button>
                    )}
                  </div>
                </div>
                <div className="text-xs text-studio-faint mt-1">{fmtDate(s.created_at)}</div>
                <p className="text-xs text-studio-muted mt-2 whitespace-pre-wrap line-clamp-4">{s.rendered_text}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-studio-text">Scenes</h2>
          <Link href="/editor" className="text-xs text-accent hover:underline">Open in editor →</Link>
        </div>
        {scenes.length === 0 ? (
          <p className="text-sm text-studio-faint">No scenes yet. Scenes appear after storyboarding runs.</p>
        ) : (
          <ol className="space-y-2">
            {scenes.map((sc) => (
              <li key={sc.id} className="bg-studio-panel2 border border-studio-border rounded p-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm text-studio-text"><span className="text-accent font-mono mr-2">{String(sc.position).padStart(2, "0")}</span>{sc.visual_prompt || "(untitled scene)"}</div>
                  <div className="text-xs text-studio-muted mt-1">{sc.script_segment}</div>
                </div>
                <StatusBadge status={sc.status} />
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-studio-text">Workflow runs</h2>
          <Link href="/queue" className="text-xs text-accent hover:underline">Production Queue →</Link>
        </div>
        {workflows.length === 0 ? (
          <p className="text-sm text-studio-faint">
            No workflow runs. Start production from the <a href="/command-center" className="text-accent hover:underline">AI Command Center</a>.
          </p>
        ) : (
          <ul className="space-y-2">
            {workflows.map((w) => (
              <li key={w.id} className="flex flex-wrap items-center justify-between text-sm gap-3">
                <span className="text-studio-text font-mono text-xs">{w.id.slice(0, 12)}… · {w.workflow_type}</span>
                <StatusBadge status={w.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
