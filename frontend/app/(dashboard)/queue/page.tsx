"use client";

import { useEffect, useMemo, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { GenerationJob, Provider, WorkflowRun } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";
import JobDrawer from "../../../components/JobDrawer";

function lane(status: string): "queued" | "running" | "approval" | "done" | "failed" {
  const s = status.toUpperCase();
  if (s === "QUEUED" || s === "UPLOAD_PENDING") return "queued";
  if (["AWAITING_APPROVAL", "BLOCKED_ON_APPROVAL"].includes(s)) return "approval";
  if (["PUBLISHED", "CANCELED", "APPROVED", "READY_TO_PUBLISH"].includes(s)) return "done";
  if (["FAILED", "PERMANENT_FAILURE", "RETRYABLE_FAILURE"].includes(s)) return "failed";
  return "running";
}

const LANE_STYLE: Record<string, string> = {
  queued: "border-l-amber-400",
  running: "border-l-accent",
  approval: "border-l-purple-400",
  done: "border-l-emerald-400",
  failed: "border-l-red-400",
};

export default function QueuePage() {
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fStatus, setFStatus] = useState("");
  const [fStage, setFStage] = useState("");
  const [fProvider, setFProvider] = useState("");
  const [drawer, setDrawer] = useState<{ id: string; kind: "workflow" | "generation" } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [wf, gj, pr] = await Promise.all([
          api.get<WorkflowRun[]>("/workflows"),
          api.get<GenerationJob[]>("/generation-jobs").catch(() => [] as GenerationJob[]),
          api.get<Provider[]>("/providers").catch(() => [] as Provider[]),
        ]);
        setWorkflows(asList(wf));
        setJobs(asList(gj));
        setProviders(asList(pr));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load queue.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const statuses = useMemo(() => {
    const s = new Set<string>();
    workflows.forEach((w) => s.add(w.status));
    jobs.forEach((j) => s.add(j.status));
    return Array.from(s).sort();
  }, [workflows, jobs]);

  const filteredWorkflows = workflows.filter(
    (w) => (!fStatus || w.status === fStatus) && (!fStage || w.current_stage === fStage)
  );
  const stages = useMemo(() => Array.from(new Set(workflows.map((w) => w.current_stage).filter(Boolean) as string[])).sort(), [workflows]);
  const filteredJobs = jobs.filter(
    (j) => (!fStatus || j.status === fStatus) && (!fProvider || j.provider === fProvider)
  );

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-studio-text">Production Queue</h1>

      <div className="flex flex-wrap gap-3 bg-studio-panel border border-studio-border rounded-lg p-3">
        <Filter label="Status" value={fStatus} onChange={setFStatus} options={statuses} />
        <Filter label="Stage" value={fStage} onChange={setFStage} options={stages} />
        <Filter label="Provider" value={fProvider} onChange={setFProvider} options={providers.map((p) => p.id)} labels={Object.fromEntries(providers.map((p) => [p.id, p.name]))} />
        {(fStatus || fStage || fProvider) && (
          <button onClick={() => { setFStatus(""); setFStage(""); setFProvider(""); }} className="text-xs text-studio-muted hover:text-studio-text self-end pb-2">
            Clear filters
          </button>
        )}
        <div className="ml-auto self-end text-xs text-studio-faint pb-2">
          Queued jobs wait for capacity · <span className="text-accent">Running</span> are active · <span className="text-purple-400">Awaiting approval</span> needs you
        </div>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading queue…</div>}

      {!loading && filteredWorkflows.length === 0 && filteredJobs.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">Queue is empty</p>
          <p className="text-sm text-studio-muted mt-1">Start a production workflow from the AI Command Center.</p>
        </div>
      )}

      <div className="space-y-2">
        {filteredWorkflows.map((w) => (
          <TaskRow
            key={w.id}
            title={`${w.workflow_type} · project ${w.project.slice(0, 8)}…`}
            subtitle={w.current_stage ? `stage: ${w.current_stage.replace(/_/g, " ")}` : w.temporal_workflow_id}
            status={w.status}
            onClick={() => setDrawer({ id: w.id, kind: "workflow" })}
          />
        ))}
        {filteredJobs.map((j) => {
          const provider = providers.find((p) => p.id === j.provider);
          return (
            <TaskRow
              key={j.id}
              title={`${j.task_type} · model ${j.model_identifier}`}
              subtitle={`provider: ${provider?.name || j.provider_name || j.provider}${j.error_message ? ` · ${j.error_message}` : ""}`}
              status={j.status}
              onClick={() => setDrawer({ id: j.id, kind: "generation" })}
            />
          );
        })}
      </div>

      {drawer && (
        <JobDrawer jobId={drawer.id} kind={drawer.kind} onClose={() => setDrawer(null)} />
      )}
    </div>
  );
}

function TaskRow({
  title, subtitle, status, onClick,
}: {
  title: string; subtitle: string; status: string; onClick: () => void;
}) {
  const l = lane(status);
  return (
    <button
      onClick={onClick}
      className={`w-full text-left bg-studio-panel border border-studio-border border-l-4 ${LANE_STYLE[l]} rounded-lg px-4 py-3 hover:border-accent/40 flex items-center gap-4`}
    >
      <div className="flex-1 min-w-0">
        <div className="text-sm text-studio-text font-medium truncate">{title}</div>
        <div className="text-xs text-studio-faint truncate">{subtitle}</div>
      </div>
      <div className="shrink-0 flex items-center gap-3">
        <span className="text-[11px] text-studio-faint uppercase hidden sm:inline">
          {l === "queued" ? "queued" : l === "running" ? "running" : l === "approval" ? "awaiting approval" : l}
        </span>
        <StatusBadge status={status} />
      </div>
    </button>
  );
}

function Filter({
  label, value, onChange, options, labels,
}: {
  label: string; value: string; onChange: (v: string) => void; options: string[]; labels?: Record<string, string>;
}) {
  return (
    <label className="text-xs">
      <span className="text-studio-muted block mb-1">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="bg-studio-panel2 border border-studio-border rounded-md px-2 py-1.5 text-studio-text text-sm">
        <option value="">All</option>
        {options.map((o) => <option key={o} value={o}>{labels?.[o] || o}</option>)}
      </select>
    </label>
  );
}
