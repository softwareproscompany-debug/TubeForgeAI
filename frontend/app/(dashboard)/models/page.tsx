"use client";

import { useEffect, useState } from "react";
import { api, asList, fmtDate } from "../../../lib/api";
import type { AIModel, Provider } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

// Secrets are shown masked only — the API never returns secret values,
// and this page never renders them.

export default function ModelsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, m] = await Promise.all([
        api.get<Provider[]>("/providers"),
        api.get<AIModel[]>("/models").catch(() => [] as AIModel[]),
      ]);
      setProviders(asList(p));
      setModels(asList(m));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load providers.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const act = async (id: string, a: "health-check" | "test-generation") => {
    setActing(id + a);
    setMsg(null);
    try {
      const res = await api.post<{ status?: string; detail?: string }>(`/providers/${id}/${a}`);
      setMsg(`${a === "health-check" ? "Health check" : "Test generation"} for provider ${id.slice(0, 8)}…: ${res.status || "completed"}${res.detail ? ` — ${res.detail}` : ""}`);
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Action failed.");
    } finally {
      setActing(null);
    }
  };

  const toggle = async (p: Provider) => {
    setActing(p.id + "toggle");
    setMsg(null);
    try {
      await api.patch(`/providers/${p.id}`, { enabled: !p.enabled });
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setActing(null);
    }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-studio-text">AI Models & Providers</h1>
      {msg && <div className="text-sm text-studio-muted bg-studio-panel border border-studio-border rounded p-3">{msg}</div>}
      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading providers…</div>}

      {!loading && providers.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">No providers registered</p>
          <p className="text-sm text-studio-muted mt-1">Register a provider (ComfyUI, local model, or cloud API) via the backend admin API to begin.</p>
        </div>
      )}

      <div className="space-y-3">
        {providers.map((p) => (
          <div key={p.id} className="bg-studio-panel border border-studio-border rounded-lg p-4">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <div className="text-studio-text font-medium">{p.name}</div>
                <div className="text-xs text-studio-faint mt-0.5">
                  adapter: {p.adapter_type} · deployment: {p.deployment_type} · priority {p.priority}
                </div>
                <div className="text-xs text-studio-faint font-mono mt-0.5 truncate max-w-full">{p.base_url}</div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={p.health_status} />
                <StatusBadge status={p.enabled ? "HEALTHY" : "PAUSED"} />
              </div>
            </div>
            <div className="mt-3 grid sm:grid-cols-3 gap-2 text-xs">
              <Spec k="Adapter" v={p.adapter_type} />
              <Spec k="Deployment" v={p.deployment_type} />
              <Spec k="Priority" v={String(p.priority)} />
              <Spec k="Capabilities" v={p.capabilities.length ? p.capabilities.join(", ") : "—"} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button disabled={acting === p.id + "health-check"} onClick={() => act(p.id, "health-check")}
                className="text-xs px-3 py-1.5 min-h-[44px] rounded-md border border-studio-border text-studio-text hover:border-accent/60 disabled:opacity-50">
                Test connection
              </button>
              <button disabled={acting === p.id + "test-generation"} onClick={() => act(p.id, "test-generation")}
                className="text-xs px-3 py-1.5 min-h-[44px] rounded-md border border-studio-border text-studio-text hover:border-accent/60 disabled:opacity-50">
                Test generation
              </button>
              <button disabled={acting === p.id + "toggle"} onClick={() => toggle(p)}
                className="text-xs px-3 py-1.5 min-h-[44px] rounded-md border border-studio-border text-studio-text hover:border-red-400/60 disabled:opacity-50">
                {p.enabled ? "Disable" : "Enable"}
              </button>
            </div>
            <div className="mt-2 text-[11px] text-studio-faint">
              Credentials: <span className="font-mono">••••••••</span> (masked — secrets are never displayed)
            </div>
          </div>
        ))}
      </div>

      {models.length > 0 && (
        <section>
          <h2 className="font-medium text-studio-text mb-3">Models</h2>
          <div className="bg-studio-panel border border-studio-border rounded-lg overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs text-studio-faint border-b border-studio-border">
                  <th className="px-4 py-2">Model</th>
                  <th className="px-4 py-2">Task type</th>
                  <th className="px-4 py-2">Version</th>
                  <th className="px-4 py-2">Provider</th>
                  <th className="px-4 py-2">Quality profile</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id} className="border-b border-studio-border/50">
                    <td className="px-4 py-2 text-studio-text">{m.model_identifier}</td>
                    <td className="px-4 py-2 text-studio-muted">{m.task_type}</td>
                    <td className="px-4 py-2 text-studio-muted text-xs">{m.model_version || "—"}</td>
                    <td className="px-4 py-2 text-studio-muted font-mono text-xs">{m.provider.slice(0, 12)}…</td>
                    <td className="px-4 py-2 text-studio-muted text-xs">{m.quality_profile || "—"}</td>
                    <td className="px-4 py-2"><StatusBadge status={m.enabled ? "HEALTHY" : "PAUSED"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function Spec({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-studio-panel2 border border-studio-border rounded p-2">
      <div className="text-studio-faint">{k}</div>
      <div className="text-studio-text mt-0.5 break-words">{v}</div>
    </div>
  );
}
