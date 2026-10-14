"use client";

import { useEffect, useMemo, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { Asset } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

export default function MediaLibraryPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fType, setFType] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [selected, setSelected] = useState<Asset | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setAssets(asList(await api.get<Asset[]>("/assets")));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load assets.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const types = useMemo(() => Array.from(new Set(assets.map((a) => a.asset_type))).sort(), [assets]);
  const statuses = useMemo(() => Array.from(new Set(assets.map((a) => a.status))).sort(), [assets]);
  const filtered = assets.filter(
    (a) => (!fType || a.asset_type === fType) && (!fStatus || a.status === fStatus)
  );

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-studio-text">Media Library</h1>

      <div className="flex gap-3 bg-studio-panel border border-studio-border rounded-lg p-3">
        <label className="text-xs">
          <span className="text-studio-muted block mb-1">Type</span>
          <select value={fType} onChange={(e) => setFType(e.target.value)}
            className="bg-studio-panel2 border border-studio-border rounded-md px-2 py-1.5 text-studio-text text-sm">
            <option value="">All</option>
            {types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-xs">
          <span className="text-studio-muted block mb-1">Status</span>
          <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}
            className="bg-studio-panel2 border border-studio-border rounded-md px-2 py-1.5 text-studio-text text-sm">
            <option value="">All</option>
            {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <div className="ml-auto self-end text-xs text-studio-faint pb-2">{filtered.length} assets</div>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading assets…</div>}

      {!loading && assets.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">No assets yet</p>
          <p className="text-sm text-studio-muted mt-1">Assets appear here once generation workflows produce images, audio, or video.</p>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((a) => (
          <button
            key={a.id}
            onClick={() => setSelected(a)}
            className="text-left bg-studio-panel border border-studio-border rounded-lg p-3 hover:border-accent/50 transition-colors"
          >
            <div className="h-24 bg-studio-bg border border-studio-border/60 rounded flex items-center justify-center text-studio-faint text-xs">
              {a.asset_type} · {a.mime_type.split("/")[1] || a.mime_type}
            </div>
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-xs text-studio-faint font-mono truncate">{a.id.slice(0, 12)}…</span>
              <StatusBadge status={a.status} />
            </div>
            <div className="text-[11px] text-studio-faint mt-1">
              {a.width && a.height ? `${a.width}×${a.height}` : ""}
              {a.duration_seconds ? ` · ${a.duration_seconds.toFixed(1)}s` : ""} · {a.source_type}
            </div>
          </button>
        ))}
      </div>

      {selected && <AssetPanel asset={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function AssetPanel({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <aside className="absolute right-0 top-0 bottom-0 w-full max-w-md bg-studio-panel border-l border-studio-border overflow-y-auto p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-studio-text">Asset detail</h2>
          <button onClick={onClose} className="text-studio-muted hover:text-studio-text text-xl" aria-label="Close">×</button>
        </div>
        <div className="space-y-4 text-sm">
          <div className="flex items-center gap-2">
            <StatusBadge status={asset.status} />
            <span className="text-studio-faint text-xs">{asset.asset_type}</span>
          </div>
          <KV k="ID" v={asset.id} mono />
          <KV k="SHA-256" v={asset.sha256} mono wrap />
          <KV k="MIME" v={asset.mime_type} />
          <KV k="Source" v={asset.source_type} />
          <KV k="Dimensions" v={asset.width && asset.height ? `${asset.width} × ${asset.height}` : "—"} />
          <KV k="Duration" v={asset.duration_seconds !== null ? `${asset.duration_seconds}s` : "—"} />
          <div>
            <div className="text-studio-faint text-xs mb-1">License metadata (provenance)</div>
            <pre className="bg-studio-bg border border-studio-border rounded p-2 text-xs text-studio-text overflow-x-auto">
              {JSON.stringify(asset.license_metadata || {}, null, 2)}
            </pre>
          </div>
          <div>
            <div className="text-studio-faint text-xs mb-1">Model metadata (generation provenance)</div>
            <pre className="bg-studio-bg border border-studio-border rounded p-2 text-xs text-studio-text overflow-x-auto">
              {JSON.stringify(asset.model_metadata || {}, null, 2)}
            </pre>
          </div>
        </div>
      </aside>
    </div>
  );
}

function KV({ k, v, mono = false, wrap = false }: { k: string; v: string; mono?: boolean; wrap?: boolean }) {
  return (
    <div>
      <div className="text-studio-faint text-xs mb-0.5">{k}</div>
      <div className={`text-studio-text ${mono ? "font-mono text-xs" : ""} ${wrap ? "break-all" : ""}`}>{v}</div>
    </div>
  );
}
