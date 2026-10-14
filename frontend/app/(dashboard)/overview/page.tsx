"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, asList, fmtDate, fmtUsd } from "../../../lib/api";
import type {
  Channel, PublicationJob, ResourceUsageEvent, WorkflowRun,
} from "../../../lib/types";
import KpiCard from "../../../components/KpiCard";
import StatusBadge from "../../../components/StatusBadge";
import ResourceMeters from "../../../components/ResourceMeters";

function Err({ e, retry }: { e: Error; retry: () => void }) {
  return (
    <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 text-sm text-red-300">
      <div className="font-medium">Could not load data</div>
      <div className="mt-1 text-red-300/80">{e.message}</div>
      {"correlation_id" in e && (
        <div className="mt-1 text-xs text-red-300/60">
          correlation_id: {(e as unknown as { correlation_id: string }).correlation_id}
        </div>
      )}
      <button onClick={retry} className="mt-2 text-xs underline hover:text-red-200">Retry</button>
    </div>
  );
}

export default function OverviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [publications, setPublications] = useState<PublicationJob[]>([]);
  const [usage, setUsage] = useState<ResourceUsageEvent[]>([]);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [ch, wf, pub, res] = await Promise.all([
          api.get<Channel[]>("/channels").catch(() => [] as Channel[]),
          api.get<WorkflowRun[]>("/workflows").catch(() => [] as WorkflowRun[]),
          api.get<PublicationJob[]>("/publications").catch(() => [] as PublicationJob[]),
          api.get<ResourceUsageEvent[]>("/resource-usage").catch(() => [] as ResourceUsageEvent[]),
        ]);
        if (!alive) return;
        setChannels(asList(ch));
        setWorkflows(asList(wf));
        setPublications(asList(pub));
        setUsage(asList(res));
      } catch (e) {
        if (alive) setError(e instanceof Error ? e : new Error("Unknown error"));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  if (loading) return <div className="text-studio-muted text-sm">Loading overview…</div>;
  if (error) return <Err e={error} retry={() => setNonce((n) => n + 1)} />;

  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const publishedThisMonth = publications.filter(
    (p) => p.status === "PUBLISHED" && p.published_at && new Date(p.published_at) >= monthStart
  ).length;
  const awaitingApproval = workflows.filter((w) =>
    ["AWAITING_APPROVAL", "BLOCKED_ON_APPROVAL"].includes(w.status)
  ).length;
  const activeJobs = workflows.filter((w) =>
    !["PUBLISHED", "FAILED", "CANCELED", "DRAFT"].includes(w.status)
  ).length;
  const failedJobs = workflows.filter((w) => w.status === "FAILED").length;
  const monthSpend = usage
    .filter((u) => new Date(u.occurred_at) >= monthStart)
    .reduce((s, u) => s + (u.actual_cost ?? u.estimated_cost ?? 0), 0);

  const stages = ["RESEARCHING","SCRIPTING","STORYBOARDING","GENERATING_ASSETS","GENERATING_NARRATION","ASSEMBLING","RENDERING","VALIDATING","FINAL_REVIEW","READY_TO_PUBLISH"];
  const upcoming = publications
    .filter((p) => p.scheduled_at && new Date(p.scheduled_at) > new Date())
    .sort((a, b) => new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime())
    .slice(0, 5);
  const recentVideos = publications
    .filter((p) => p.status === "PUBLISHED")
    .sort((a, b) => new Date(b.published_at || 0).getTime() - new Date(a.published_at || 0).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-studio-text">Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard label="Channels" value={String(channels.length)} href="/channels" />
        <KpiCard label="Published this month" value={String(publishedThisMonth)} href="/publishing" />
        <KpiCard label="Awaiting approval" value={String(awaitingApproval)} href="/queue" />
        <KpiCard label="Active jobs" value={String(activeJobs)} href="/queue" />
        <KpiCard label="Failed jobs" value={String(failedJobs)} href="/queue" />
        <KpiCard label="Monthly spend" value={fmtUsd(monthSpend)} href="/analytics" delta="calculated from resource usage" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium text-studio-text">Production pipeline</h2>
            <Link href="/queue" className="text-xs text-accent hover:underline">View queue</Link>
          </div>
          {workflows.length === 0 ? (
            <p className="text-sm text-studio-faint">No workflow runs yet. Create a project, then start a workflow from the AI Command Center.</p>
          ) : (
            <ul className="space-y-2">
              {stages.map((s) => {
                const inStage = workflows.filter((w) => w.current_stage === s || w.status === s);
                if (inStage.length === 0) return null;
                return (
                  <li key={s} className="flex items-center gap-3 text-sm">
                    <span className="w-44 text-studio-muted">{s.replace(/_/g, " ")}</span>
                    <div className="flex-1 h-2 bg-studio-panel2 rounded overflow-hidden">
                      <div className="h-full bg-accent/70" style={{ width: `${Math.min(100, (inStage.length / Math.max(1, workflows.length)) * 100)}%` }} />
                    </div>
                    <span className="text-studio-text w-8 text-right">{inStage.length}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium text-studio-text">Upcoming publications</h2>
            <Link href="/calendar" className="text-xs text-accent hover:underline">Calendar</Link>
          </div>
          {upcoming.length === 0 ? (
            <p className="text-sm text-studio-faint">Nothing scheduled. Schedule a publication from the Publishing page.</p>
          ) : (
            <ul className="space-y-2">
              {upcoming.map((p) => (
                <li key={p.id} className="flex items-center justify-between text-sm gap-3">
                  <span className="text-studio-text truncate">{p.title}</span>
                  <span className="text-studio-faint text-xs shrink-0">{fmtDate(p.scheduled_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <h2 className="font-medium text-studio-text mb-3">Recent videos</h2>
          {recentVideos.length === 0 ? (
            <p className="text-sm text-studio-faint">No published videos yet.</p>
          ) : (
            <ul className="space-y-2">
              {recentVideos.map((v) => (
                <li key={v.id} className="flex items-center justify-between text-sm gap-3">
                  <span className="text-studio-text truncate">{v.title}</span>
                  <span className="text-studio-faint text-xs shrink-0">{fmtDate(v.published_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <h2 className="font-medium text-studio-text mb-3">Alerts</h2>
          <Alerts workflows={workflows} publications={publications} />
        </section>
      </div>

      <section>
        <h2 className="font-medium text-studio-text mb-3">Resources</h2>
        <ResourceMeters />
      </section>
    </div>
  );
}

function Alerts({ workflows, publications }: { workflows: WorkflowRun[]; publications: PublicationJob[] }) {
  const items: { text: string; href: string }[] = [];
  workflows
    .filter((w) => ["FAILED", "BLOCKED_ON_RESOURCES", "BLOCKED_ON_APPROVAL"].includes(w.status))
    .slice(0, 5)
    .forEach((w) => items.push({ text: `Workflow ${w.id.slice(0, 8)}… is ${w.status.replace(/_/g, " ")}`, href: "/queue" }));
  publications
    .filter((p) => ["RETRYABLE_FAILURE", "PERMANENT_FAILURE", "QUOTA_BLOCKED", "AUTHORIZATION_REQUIRED"].includes(p.status))
    .slice(0, 5)
    .forEach((p) => items.push({ text: `Publication "${p.title}" — ${p.status.replace(/_/g, " ")}`, href: "/publishing" }));
  if (items.length === 0) return <p className="text-sm text-studio-faint">No alerts. All systems nominal.</p>;
  return (
    <ul className="space-y-2">
      {items.map((a, i) => (
        <li key={i}>
          <Link href={a.href} className="text-sm text-amber-400 hover:underline">⚠ {a.text}</Link>
        </li>
      ))}
    </ul>
  );
}
