"use client";

import { useEffect, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { Asset, Project, RenderJob, Scene, TimelineClip, TimelineV1, TimelineVersionRow } from "../../../lib/types";
import TimelineEditor from "../../../components/TimelineEditor";

const DEFAULT_TIMELINE: TimelineV1 = {
  version: 1,
  tracks: [
    { id: "v1", kind: "video", name: "Video 1", clips: [] },
    { id: "a1", kind: "audio", name: "Narration", clips: [] },
    { id: "c1", kind: "caption", name: "Captions", clips: [] },
  ],
};

interface HistoryEntry {
  past: TimelineV1[];
  future: TimelineV1[];
}

export default function EditorPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [timeline, setTimeline] = useState<TimelineV1>(DEFAULT_TIMELINE);
  const [history, setHistory] = useState<HistoryEntry>({ past: [], future: [] });
  const [leftTab, setLeftTab] = useState<"assets" | "scenes">("assets");
  const [selectedClip, setSelectedClip] = useState<TimelineClip | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renders, setRenders] = useState<RenderJob[]>([]);

  useEffect(() => {
    (async () => {
      const p = asList(await api.get<Project[]>("/projects").catch(() => [] as Project[]));
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id);
    })();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      // Backend GET /timeline returns a TimelineVersion row wrapping the
      // TimelineV1 document in `timeline_json` (404 when none saved yet).
      const [a, s, t, r] = await Promise.all([
        api.get<Asset[]>("/assets").catch(() => [] as Asset[]),
        api.get<Scene[]>(`/projects/${projectId}/scenes`).catch(() => [] as Scene[]),
        api.get<TimelineVersionRow>(`/projects/${projectId}/timeline`).catch(() => null),
        api.get<RenderJob[]>(`/projects/${projectId}/renders`).catch(() => [] as RenderJob[]),
      ]);
      setAssets(asList(a));
      setScenes(asList(s));
      const doc = t?.timeline_json;
      setTimeline(doc && Array.isArray(doc.tracks) ? doc : DEFAULT_TIMELINE);
      setRenders(asList(r));
      setHistory({ past: [], future: [] });
      setSelectedClip(null);
    })();
  }, [projectId]);

  // Client-side undo/redo stack — every timeline mutation pushes history.
  const commit = (next: TimelineV1) => {
    setHistory((h) => ({ past: [...h.past.slice(-49), timeline], future: [] }));
    setTimeline(next);
    syncSelection(next);
  };

  const undo = () => {
    setHistory((h) => {
      if (h.past.length === 0) return h;
      const prev = h.past[h.past.length - 1];
      setTimeline(prev);
      syncSelection(prev);
      return { past: h.past.slice(0, -1), future: [timeline, ...h.future] };
    });
  };

  const redo = () => {
    setHistory((h) => {
      if (h.future.length === 0) return h;
      const next = h.future[0];
      setTimeline(next);
      syncSelection(next);
      return { past: [...h.past, timeline], future: h.future.slice(1) };
    });
  };

  const syncSelection = (t: TimelineV1) => {
    setSelectedClip((sel) => {
      if (!sel) return null;
      for (const track of t.tracks) {
        const c = track.clips.find((x) => x.id === sel.id);
        if (c) return c;
      }
      return null;
    });
  };

  const addClipFromAsset = (asset: Asset) => {
    const clip: TimelineClip = {
      id: `clip-${Date.now()}`,
      track_id: "v1",
      asset_id: asset.id,
      start_s: nextFreeStart(timeline, "v1"),
      end_s: nextFreeStart(timeline, "v1") + (asset.duration_seconds || 5),
      offset_s: 0,
      label: `${asset.asset_type} ${asset.id.slice(0, 6)}`,
    };
    commit({
      ...timeline,
      tracks: timeline.tracks.map((t) => (t.id === "v1" ? { ...t, clips: [...t.clips, clip] } : t)),
    });
  };

  const updateSelectedClip = (patch: Partial<TimelineClip>) => {
    if (!selectedClip) return;
    commit({
      ...timeline,
      tracks: timeline.tracks.map((t) => ({
        ...t,
        clips: t.clips.map((c) => (c.id === selectedClip.id ? { ...c, ...patch } : c)),
      })),
    });
  };

  const save = async (): Promise<string | null> => {
    if (!projectId) return null;
    setSaving(true);
    setMsg(null);
    try {
      // Backend TimelineView expects the document under `timeline_json` and
      // returns the saved TimelineVersion row (its `id` is what renders need).
      const row = await api.post<{ id: string }>(`/projects/${projectId}/timeline`, {
        timeline_json: timeline,
      });
      setMsg("Timeline saved.");
      return row.id;
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const render = async () => {
    if (!projectId) return;
    setRendering(true);
    setMsg(null);
    try {
      // Render jobs reference a saved TimelineVersion row by its DB id —
      // save first so the render points at exactly what is on screen.
      const versionId = await save();
      if (!versionId) {
        setMsg("Render aborted: timeline could not be saved.");
        return;
      }
      const job = await api.post<RenderJob>(`/projects/${projectId}/renders`, {
        timeline_version_id: versionId,
      });
      setRenders((r) => [job, ...r]);
      setMsg(`Render job ${job.id.slice(0, 8)}… submitted.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Render failed.");
    } finally {
      setRendering(false);
    }
  };

  const exportTimeline = () => {
    const blob = new Blob([JSON.stringify(timeline, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `timeline-${projectId || "untitled"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-3 h-[calc(100vh-9rem)] flex flex-col">
      {/* top toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}
          className="bg-studio-panel2 border border-studio-border rounded-md px-3 py-1.5 text-sm text-studio-text">
          {projects.length === 0 && <option value="">No projects</option>}
          {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <div className="flex gap-1">
          <ToolbarBtn onClick={undo} disabled={history.past.length === 0} title="Undo">↶ Undo</ToolbarBtn>
          <ToolbarBtn onClick={redo} disabled={history.future.length === 0} title="Redo">↷ Redo</ToolbarBtn>
        </div>
        <div className="flex gap-1 ml-auto">
          <ToolbarBtn onClick={save} disabled={saving || !projectId} primary>{saving ? "Saving…" : "Save"}</ToolbarBtn>
          <ToolbarBtn onClick={render} disabled={rendering || !projectId} primary>{rendering ? "Rendering…" : "Render"}</ToolbarBtn>
          <ToolbarBtn onClick={exportTimeline} disabled={!projectId}>Export</ToolbarBtn>
        </div>
      </div>
      {msg && <div className="text-sm text-studio-muted">{msg}</div>}

      <div className="flex-1 grid grid-cols-[240px_1fr_240px] gap-3 min-h-0">
        {/* left: assets / scenes */}
        <aside className="bg-studio-panel border border-studio-border rounded-lg overflow-hidden flex flex-col">
          <div className="flex border-b border-studio-border">
            {(["assets", "scenes"] as const).map((t) => (
              <button key={t} onClick={() => setLeftTab(t)}
                className={`flex-1 py-2 text-xs capitalize ${leftTab === t ? "text-accent border-b-2 border-accent" : "text-studio-muted"}`}>
                {t}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {leftTab === "assets" && (
              assets.length === 0
                ? <p className="text-xs text-studio-faint p-2">No assets. Generated media will appear here.</p>
                : assets.map((a) => (
                    <button key={a.id} onClick={() => addClipFromAsset(a)}
                      className="w-full text-left bg-studio-panel2 border border-studio-border rounded p-2 hover:border-accent/50">
                      <div className="text-xs text-studio-text">{a.asset_type}</div>
                      <div className="text-[11px] text-studio-faint font-mono">{a.id.slice(0, 10)}…</div>
                      <div className="text-[11px] text-accent mt-1">+ add to timeline</div>
                    </button>
                  ))
            )}
            {leftTab === "scenes" && (
              scenes.length === 0
                ? <p className="text-xs text-studio-faint p-2">No scenes for this project yet.</p>
                : scenes.map((s) => (
                    <div key={s.id} className="bg-studio-panel2 border border-studio-border rounded p-2">
                      <div className="text-xs text-studio-text"><span className="text-accent font-mono mr-1">{String(s.position).padStart(2, "0")}</span>{s.visual_prompt || "(untitled scene)"}</div>
                      <div className="text-[11px] text-studio-faint mt-0.5">{s.script_segment}</div>
                    </div>
                  ))
            )}
          </div>
        </aside>

        {/* center: preview + timeline */}
        <div className="flex flex-col gap-3 min-h-0">
          <div className="bg-studio-panel border border-studio-border rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-studio-muted">Preview</span>
              <span className="text-[11px] px-2 py-0.5 rounded border border-amber-500/40 text-amber-400 bg-amber-500/10">
                PREVIEW — not the final render
              </span>
            </div>
            <input value={previewUrl} onChange={(e) => setPreviewUrl(e.target.value)}
              placeholder="Paste a media URL to preview (optional)"
              className="w-full mb-2 bg-studio-bg border border-studio-border rounded-md px-2 py-1.5 text-xs text-studio-text placeholder:text-studio-faint" />
            {previewUrl ? (
              <video src={previewUrl} controls className="w-full max-h-56 bg-black rounded" />
            ) : (
              <div className="w-full h-56 bg-black rounded flex items-center justify-center text-studio-faint text-xs">
                No preview source — paste a URL above
              </div>
            )}
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            <TimelineEditor timeline={timeline} onChange={commit} />
          </div>
        </div>

        {/* right: clip properties */}
        <aside className="bg-studio-panel border border-studio-border rounded-lg p-3 overflow-y-auto">
          <h3 className="text-xs font-medium text-studio-text mb-2">Clip properties</h3>
          {!selectedClip ? (
            <p className="text-xs text-studio-faint">Click a clip in the timeline to edit it.</p>
          ) : (
            <div className="space-y-2 text-xs">
              <label className="block">
                <span className="text-studio-faint">Label</span>
                <input value={selectedClip.label} onChange={(e) => updateSelectedClip({ label: e.target.value })}
                  className="mt-0.5 w-full bg-studio-bg border border-studio-border rounded px-2 py-1 text-studio-text" />
              </label>
              <label className="block">
                <span className="text-studio-faint">Start (s)</span>
                <input type="number" step={0.1} min={0} value={selectedClip.start_s}
                  onChange={(e) => updateSelectedClip({ start_s: Number(e.target.value) })}
                  className="mt-0.5 w-full bg-studio-bg border border-studio-border rounded px-2 py-1 text-studio-text" />
              </label>
              <label className="block">
                <span className="text-studio-faint">End (s)</span>
                <input type="number" step={0.1} min={0} value={selectedClip.end_s}
                  onChange={(e) => updateSelectedClip({ end_s: Number(e.target.value) })}
                  className="mt-0.5 w-full bg-studio-bg border border-studio-border rounded px-2 py-1 text-studio-text" />
              </label>
              <label className="block">
                <span className="text-studio-faint">Source offset (s)</span>
                <input type="number" step={0.1} min={0} value={selectedClip.offset_s}
                  onChange={(e) => updateSelectedClip({ offset_s: Number(e.target.value) })}
                  className="mt-0.5 w-full bg-studio-bg border border-studio-border rounded px-2 py-1 text-studio-text" />
              </label>
              <div className="text-studio-faint">Asset: <span className="font-mono text-studio-text">{selectedClip.asset_id?.slice(0, 12) || "—"}</span></div>
              <button
                onClick={() => {
                  commit({ ...timeline, tracks: timeline.tracks.map((t) => ({ ...t, clips: t.clips.filter((c) => c.id !== selectedClip.id) })) });
                }}
                className="text-red-400 hover:underline"
              >
                Delete clip
              </button>
            </div>
          )}
          {renders.length > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-medium text-studio-text mb-2">Render jobs</h3>
              <ul className="space-y-1">
                {renders.map((r) => (
                  <li key={r.id} className="text-[11px] text-studio-muted font-mono">{r.id.slice(0, 12)}… · {r.status}</li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function ToolbarBtn({
  children, onClick, disabled, primary, title,
}: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean; primary?: boolean; title?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`text-sm px-3 py-1.5 rounded-md border disabled:opacity-40 ${
        primary
          ? "bg-accent text-black font-medium border-accent hover:brightness-110"
          : "border-studio-border text-studio-text hover:border-accent/60"
      }`}
    >
      {children}
    </button>
  );
}

function nextFreeStart(t: TimelineV1, trackId: string): number {
  const track = t.tracks.find((x) => x.id === trackId);
  if (!track || track.clips.length === 0) return 0;
  return Math.max(...track.clips.map((c) => c.end_s));
}
