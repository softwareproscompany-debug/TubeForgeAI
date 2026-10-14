"use client";

// HARD RULE: resources are ALWAYS reported as five separate meters —
// Local GPU, Cloud GPU, Paid API spend, Storage, Queue depth.
// NEVER combine them into a single "credits" metric. Budgets are
// enforced server-side per resource; the UI must not invent a unified
// currency or imply one resource substitutes for another.

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ResourceUsageEvent } from "../lib/types";

interface Meter {
  label: string;
  value: string;
  note: string;
}

export default function ResourceMeters({ compact = false }: { compact?: boolean }) {
  const [meters, setMeters] = useState<Meter[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [usage, health] = await Promise.all([
          api.get<ResourceUsageEvent[]>("/resource-usage").catch(() => [] as ResourceUsageEvent[]),
          api.get<{ queue_depth?: number | null } & Record<string, unknown>>("/health").catch(() => null),
        ]);
        if (!alive) return;
        // Backend canonical resource types (backend/providers/models.py):
        // local_gpu_seconds, cloud_gpu_seconds, api_spend_usd, storage_gb,
        // cpu_seconds, ram_gb_seconds, youtube_quota_units, render_seconds.
        // Match by prefix so meters stay correct if the backend refines units.
        const byType = (prefix: string, perUnit = 1) =>
          usage
            .filter((u) => u.resource_type.toLowerCase().startsWith(prefix))
            .reduce((s, u) => s + Number(u.quantity) * perUnit, 0);
        setMeters([
          { label: "Local GPU", value: `${byType("local_gpu", 1 / 60).toFixed(0)} min`, note: "self-hosted" },
          { label: "Cloud GPU", value: `${byType("cloud_gpu", 1 / 60).toFixed(0)} min`, note: "remote render" },
          { label: "Paid API", value: `$${byType("api_spend").toFixed(2)}`, note: "spend" },
          { label: "Storage", value: `${byType("storage").toFixed(1)} GB`, note: "media" },
          { label: "Queue depth", value: String(health?.queue_depth ?? 0), note: "pending" },
        ]);
      } catch {
        if (alive) setError(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (error) return <span className="text-xs text-studio-faint">resources unavailable</span>;

  if (compact) {
    return (
      <div className="hidden xl:flex items-center gap-3 text-[11px] text-studio-muted">
        {meters.map((m) => (
          <span key={m.label} title={`${m.label} (${m.note})`}>
            <span className="text-studio-faint">{m.label}:</span> <span className="text-studio-text">{m.value}</span>
          </span>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {meters.map((m) => (
        <div key={m.label} className="bg-studio-panel border border-studio-border rounded-lg p-3">
          <div className="text-xs text-studio-muted">{m.label}</div>
          <div className="text-lg font-semibold text-studio-text mt-0.5">{m.value}</div>
          <div className="text-[11px] text-studio-faint">{m.note}</div>
        </div>
      ))}
    </div>
  );
}
