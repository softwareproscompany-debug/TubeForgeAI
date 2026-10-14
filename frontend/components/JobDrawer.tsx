"use client";

import { useEffect, useState } from "react";
import { api, asList, fmtDate } from "../lib/api";
import type { GenerationJob, ResourceUsageEvent, WorkflowEvent, WorkflowRun } from "../lib/types";
import StatusBadge from "./StatusBadge";

interface JobDetail {
  workflow?: WorkflowRun;
  job?: GenerationJob;
  events: WorkflowEvent[];
  resources: ResourceUsageEvent[];
  artifacts: string[];
}

export default function JobDrawer({
  jobId,
  kind,
  onClose,
}: {
  jobId: string;
  kind: "workflow" | "generation";
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        if (kind === "workflow") {
          const [wf, events] = await Promise.all([
            api.get<WorkflowRun>(`/workflows/${jobId}`),
            api.get<WorkflowEvent[]>(`/workflows/${jobId}/events`).catch(() => [] as WorkflowEvent[]),
          ]);
          if (!alive) return;
          setDetail({ workflow: wf, events, resources: [], artifacts: [] });
        } else {
          const jobs = asList(await api.get<GenerationJob[]>("/generation-jobs"));
          const job = jobs.find((j) => j.id === jobId);
          if (!alive) return;
          if (!job) setError("Job not found.");
          else setDetail({ job, events: [], resources: [], artifacts: [] });
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load job.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [jobId, kind]);

  const control = async (action: "pause" | "resume" | "cancel" | "retry") => {
    if (kind !== "workflow") return;
    setActing(true);
    try {
      const wf = await api.post<WorkflowRun>(`/workflows/${jobId}/${action}`);
      setDetail((d) => (d && d.workflow ? { ...d, workflow: wf } : d));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed.");
    } finally {
      setActing(false);
    }
  };

  const wf = detail?.workflow;
  const job = detail?.job;

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <aside className="absolute right-0 top-0 bottom-0 w-full max-w-lg bg-studio-panel border-l border-studio-border overflow-y-auto">
        <div className="sticky top-0 bg-studio-panel border-b border-studio-border px-5 py-4 flex items-center justify-between">
          <h2 className="font-semibold text-studio-text">Job detail</h2>
          <button onClick={onClose} className="text-studio-muted hover:text-studio-text text-xl" aria-label="Close">×</button>
        </div>
        <div className="p-5">
          {loading && <div className="text-studio-muted text-sm">Loading job…</div>}
          {error && <div className="text-sm text-red-400">Error: {error}</div>}
          {wf && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <StatusBadge status={wf.status} />
                <span className="text-xs text-studio-faint">temporal: {wf.temporal_workflow_id || "—"}</span>
              </div>
              <dl className="text-sm space-y-2">
                <Row k="Workflow ID" v={wf.id} />
                <Row k="Project" v={wf.project_id} />
                <Row k="Type" v={wf.workflow_type} />
                <Row k="Current stage" v={wf.current_stage || "—"} />
                <Row k="Created" v={fmtDate(wf.created_at)} />
                <Row k="Updated" v={fmtDate(wf.updated_at)} />
              </dl>
              <div className="flex flex-wrap gap-2">
                {(["pause", "resume", "cancel", "retry"] as const).map((a) => (
                  <button
                    key={a}
                    disabled={acting}
                    onClick={() => control(a)}
                    className="text-sm px-3 py-1.5 rounded-md border border-studio-border text-studio-text hover:border-accent/60 disabled:opacity-50"
                  >
                    {a[0].toUpperCase() + a.slice(1)}
                  </button>
                ))}
              </div>
              <div>
                <h3 className="text-sm font-medium text-studio-text mb-2">Execution history</h3>
                {detail.events.length === 0 ? (
                  <p className="text-xs text-studio-faint">No events recorded yet.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {detail.events.map((e) => (
                      <li key={e.id} className="text-xs bg-studio-panel2 border border-studio-border rounded p-2">
                        <span className="text-accent font-mono">{e.event_type}</span>
                        {e.stage && <span className="text-studio-muted"> · {e.stage}</span>}
                        <div className="text-studio-faint">{fmtDate(e.occurred_at)}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
          {job && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <StatusBadge status={job.status} />
                {job.failure_reason && <span className="text-xs text-red-400">{job.failure_reason}</span>}
              </div>
              <dl className="text-sm space-y-2">
                <Row k="Job ID" v={job.id} />
                <Row k="Type" v={job.job_type} />
                <Row k="Model" v={job.model_id} />
                <Row k="Provider" v={job.provider_id} />
                <Row k="Progress" v={job.progress === null ? "—" : `${job.progress}%`} />
                <Row k="Retries" v={String(job.retry_count)} />
                <Row k="Created" v={fmtDate(job.created_at)} />
              </dl>
              <p className="text-xs text-studio-faint">
                Resource usage for this job is reported per-resource in Production Queue; no unified credit view.
              </p>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-32 shrink-0 text-studio-faint">{k}</dt>
      <dd className="text-studio-text break-all">{v}</dd>
    </div>
  );
}
