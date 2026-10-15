"use client";

import { useEffect, useState } from "react";
import { api, asList, fmtDate } from "../../../lib/api";
import type { AuditEvent, HealthStatus, Provider, WorkflowRun } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

export default function HealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [failures, setFailures] = useState<WorkflowRun[]>([]);
  const [securityEvents, setSecurityEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, pr, wf, audit] = await Promise.all([
        api.get<HealthStatus>("/health"),
        api.get<Provider[]>("/providers").catch(() => [] as Provider[]),
        api.get<WorkflowRun[]>("/workflows").catch(() => [] as WorkflowRun[]),
        api.get<AuditEvent[]>("/audit-events").catch(() => [] as AuditEvent[]),
      ]);
      setHealth(h);
      setProviders(asList(pr));
      setFailures(asList(wf).filter((w) => w.status === "FAILED"));
      setSecurityEvents(
        asList(audit).filter((e) =>
          /auth|login|denied|security|permission/i.test(e.action)
        ).slice(0, 10)
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load health.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="text-studio-muted text-sm">Checking system health…</div>;
  if (error || !health)
    return (
      <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4">
        <div className="text-sm text-red-300 font-medium">API unreachable</div>
        <div className="text-sm text-red-300/80 mt-1">{error || "No health data."}</div>
        <button onClick={load} className="mt-2 text-xs underline text-red-300">Retry</button>
      </div>
    );

  const alerts: string[] = [];
  if (health.workflow_failures_24h) alerts.push(`${health.workflow_failures_24h} workflow failures in the last 24h`);
  // Backend HealthView returns checks as plain strings: "ok", "not_configured",
  // "unreachable", "error: ...", etc.
  Object.entries(health.checks || {}).forEach(([k, v]) => {
    if (v !== "ok" && v !== "not_configured") alerts.push(`${k}: ${v}`);
  });
  providers.filter((p) => p.health_status.toUpperCase() !== "HEALTHY").forEach((p) =>
    alerts.push(`Provider ${p.name}: ${p.health_status}`)
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-studio-text">System Health</h1>
        <div className="flex items-center gap-3">
          <StatusBadge status={health.status} />
          <button onClick={load} className="text-xs text-studio-muted hover:text-studio-text underline">Refresh</button>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/40 rounded-lg p-4">
          <div className="text-sm font-medium text-amber-300 mb-2">Actionable alerts ({alerts.length})</div>
          <ul className="space-y-1">
            {alerts.map((a, i) => <li key={i} className="text-sm text-amber-200/90">⚠ {a}</li>)}
          </ul>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Metric label="CPU" value={health.cpu_percent !== null && health.cpu_percent !== undefined ? `${health.cpu_percent}%` : "—"} />
        <Metric label="RAM" value={health.ram_percent !== null && health.ram_percent !== undefined ? `${health.ram_percent}%` : "—"} />
        <Metric label="Disk" value={health.disk_percent !== null && health.disk_percent !== undefined ? `${health.disk_percent}%` : "—"} />
        <Metric label="Queue depth" value={health.queue_depth !== null && health.queue_depth !== undefined ? String(health.queue_depth) : "—"} />
        <Metric label="Workflow failures (24h)" value={health.workflow_failures_24h !== null && health.workflow_failures_24h !== undefined ? String(health.workflow_failures_24h) : "—"} />
        <Metric label="Database" value={health.db || "—"} />
        <Metric label="Backup" value={health.backup ? `${health.backup.status}${health.backup.last_run ? ` · ${fmtDate(health.backup.last_run)}` : ""}` : "—"} />
        <Metric label="Cert expiry" value={health.cert_expiry ? fmtDate(health.cert_expiry) : "—"} />
      </div>

      {health.gpu && Object.keys(health.gpu).length > 0 && (
        <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <h2 className="font-medium text-studio-text mb-2">GPU</h2>
          <pre className="text-xs text-studio-muted overflow-x-auto">{JSON.stringify(health.gpu, null, 2)}</pre>
        </section>
      )}

      <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
        <h2 className="font-medium text-studio-text mb-3">Service checks</h2>
        {Object.keys(health.checks || {}).length === 0 ? (
          <p className="text-sm text-studio-faint">No service checks reported.</p>
        ) : (
          <ul className="space-y-1.5">
            {Object.entries(health.checks).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between text-sm">
                <span className="text-studio-text">{k}</span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-studio-faint font-mono">{v}</span>
                  <StatusBadge status={v === "ok" ? "HEALTHY" : v === "not_configured" ? "PAUSED" : "UNHEALTHY"} />
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
        <h2 className="font-medium text-studio-text mb-3">Provider health</h2>
        {providers.length === 0 ? (
          <p className="text-sm text-studio-faint">No providers registered.</p>
        ) : (
          <ul className="space-y-1.5">
            {providers.map((p) => (
              <li key={p.id} className="flex items-center justify-between text-sm">
                <span className="text-studio-text">{p.name}</span>
                <StatusBadge status={p.health_status} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
        <h2 className="font-medium text-studio-text mb-3">Recent workflow failures</h2>
        {failures.length === 0 ? (
          <p className="text-sm text-studio-faint">No failed workflow runs.</p>
        ) : (
          <ul className="space-y-1.5">
            {failures.slice(0, 10).map((w) => (
              <li key={w.id} className="text-sm flex justify-between gap-3">
                <span className="text-studio-text font-mono text-xs">{w.id.slice(0, 12)}… · {w.workflow_type}</span>
                <span className="text-xs text-studio-faint">{fmtDate(w.completed_at || w.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-studio-panel border border-studio-border rounded-lg p-4">
        <h2 className="font-medium text-studio-text mb-3">Security events</h2>
        {securityEvents.length === 0 ? (
          <p className="text-sm text-studio-faint">No security-relevant audit events.</p>
        ) : (
          <ul className="space-y-1.5">
            {securityEvents.map((e) => (
              <li key={e.id} className="text-sm flex justify-between gap-3">
                <span className="text-studio-text">{e.actor} — {e.action} <span className="text-studio-faint">({e.resource_type})</span></span>
                <span className="text-xs text-studio-faint">{fmtDate(e.occurred_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-3">
      <div className="text-xs text-studio-muted">{label}</div>
      <div className="text-lg font-semibold text-studio-text mt-0.5 break-words">{value}</div>
    </div>
  );
}
