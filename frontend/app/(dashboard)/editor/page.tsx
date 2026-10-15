"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { Asset, Project, RenderJob, Scene } from "../../../lib/types";
import {
  blankEDL,
  clipEnd,
  isEDLDocument,
  normalizeEDL,
  uid,
  type EDL,
  type EDLClip,
  type EDLTrackType,
} from "../../../lib/edl";
import VideoEditor, { type ClipSelection } from "../../../components/video-editor/VideoEditor";
import PreviewPlayer from "../../../components/video-editor/PreviewPlayer";
import Inspector from "../../../components/video-editor/Inspector";

interface HistoryEntry {
  past: EDL[];
  future: EDL[];
}

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELED"]);

export default function EditorPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [edl, setEdl] = useState<EDL>(blankEDL());
  const [history, setHistory] = useState<HistoryEntry>({ past: [], future: [] });
  const [leftTab, setLeftTab] = useState<"assets" | "scenes">("assets");
  const [selected, setSelected] = useState<ClipSelection | null>(null);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renders, setRenders] = useState<RenderJob[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const edlRef = useRef(edl);
  edlRef.current = edl;
  const playheadRef = useRef(playhead);
  playheadRef.current = playhead;

  // -- load -----------------------------------------------------------------
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
      const [a, s, t, r] = await Promise.all([
        api.get<Asset[]>("/assets").catch(() => [] as Asset[]),
        api.get<Scene[]>(`/projects/${projectId}/scenes`).catch(() => [] as Scene[]),
        api.get<{ timeline_json: unknown }>(`/projects/${projectId}/timeline`).catch(() => null),
        api.get<RenderJob[]>(`/projects/${projectId}/renders`).catch(() => [] as RenderJob[]),
      ]);
      setAssets(asList(a));
      setScenes(asList(s));
      const doc = t?.timeline_json;
      const next = isEDLDocument(doc) ? normalizeEDL(doc) : blankEDL();
      setEdl(next);
      setRenders(asList(r));
      setHistory({ past: [], future: [] });
      setSelected(null);
      setPlayhead(0);
      setPlaying(false);
      setActiveJobId(null);
    })();
  }, [projectId]);

  // -- history ---------------------------------------------------------------
  const commit = useCallback((next: EDL) => {
    setHistory((h) => ({ past: [...h.past.slice(-49), edlRef.current], future: [] }));
    setEdl(next);
    // Drop the selection if its clip no longer exists.
    setSelected((sel) => {
      if (!sel) return null;
      const track = next.tracks.find((t) => t.id === sel.trackId);
      return track?.clips.some((c) => c.id === sel.clipId) ? sel : null;
    });
  }, []);

  const undo = () => {
    setHistory((h) => {
      if (h.past.length === 0) return h;
      const prev = h.past[h.past.length - 1];
      setEdl(prev);
      return { past: h.past.slice(0, -1), future: [edlRef.current, ...h.future] };
    });
    setSelected(null);
  };
  const redo = () => {
    setHistory((h) => {
      if (h.future.length === 0) return h;
      const next = h.future[0];
      setEdl(next);
      return { past: [...h.past, edlRef.current], future: h.future.slice(1) };
    });
    setSelected(null);
  };

  // -- playback ---------------------------------------------------------------
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      const dur = edlRef.current.duration;
      const next = playheadRef.current + dt;
      if (next >= dur) {
        setPlayhead(dur);
        setPlaying(false);
        return;
      }
      setPlayhead(next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  // -- render job polling ------------------------------------------------------
  useEffect(() => {
    if (!activeJobId || !projectId) return;
    const iv = setInterval(async () => {
      try {
        const j = await api.get<RenderJob>(`/projects/${projectId}/renders/${activeJobId}`);
        setRenders((rs) => rs.map((r) => (r.id === j.id ? j : r)));
        if (TERMINAL.has(j.status)) {
          setActiveJobId(null);
          setMsg(
            j.status === "COMPLETED"
              ? "Render complete — output asset is ready."
              : `Render ${j.status.toLowerCase()}${j.error ? `: ${j.error.slice(0, 160)}` : ""}`
          );
        }
      } catch {
        /* keep polling */
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [activeJobId, projectId]);

  // -- clip ops -----------------------------------------------------------------
  const selectedClip: { clip: EDLClip; trackType: EDLTrackType } | null = selected
    ? (() => {
        const track = edl.tracks.find((t) => t.id === selected.trackId);
        const clip = track?.clips.find((c) => c.id === selected.clipId);
        return track && clip ? { clip, trackType: track.type } : null;
      })()
    : null;

  const patchSelected = (patch: Partial<EDLClip>) => {
    if (!selected) return;
    commit({
      ...edl,
      tracks: edl.tracks.map((t) =>
        t.id === selected.trackId
          ? { ...t, clips: t.clips.map((c) => (c.id === selected.clipId ? { ...c, ...patch } : c)) }
          : t
      ),
    });
  };

  const deleteSelected = () => {
    if (!selected) return;
    commit({
      ...edl,
      tracks: edl.tracks.map((t) =>
        t.id === selected.trackId
          ? { ...t, clips: t.clips.filter((c) => c.id !== selected.clipId) }
          : t
      ),
    });
    setSelected(null);
  };

  const nextFreeStart = (trackId: string): number => {
    const track = edl.tracks.find((t) => t.id === trackId);
    if (!track || track.clips.length === 0) return 0;
    return Math.max(...track.clips.map(clipEnd));
  };

  const addClipFromAsset = (asset: Asset) => {
    const type: EDLTrackType = asset.asset_type === "AUDIO" ? "audio" : "video";
    const track = edl.tracks.find((t) => t.type === type) ?? edl.tracks[0];
    const dur = asset.duration_seconds && asset.duration_seconds > 0 ? asset.duration_seconds : 5;
    const clip: EDLClip = {
      id: uid("clip"),
      source: asset.source_url || asset.object_key,
      label: `${asset.asset_type} ${asset.id.slice(0, 6)}`,
      start: Math.round(nextFreeStart(track.id) * 100) / 100,
      in: 0,
      out: Math.round(Math.min(dur, 60) * 100) / 100,
    };
    commit({
      ...edl,
      tracks: edl.tracks.map((t) => (t.id === track.id ? { ...t, clips: [...t.clips, clip] } : t)),
    });
    setSelected({ trackId: track.id, clipId: clip.id });
  };

  const addTextClip = () => {
    const track = edl.tracks.find((t) => t.type === "text") ?? edl.tracks[0];
    const clip: EDLClip = {
      id: uid("clip"),
      source: "text",
      label: "Text overlay",
      start: Math.round(playheadRef.current * 100) / 100,
      in: 0,
      out: 4,
      textOverlay: { text: "Your text", x: 0.5, y: 0.85, fontSize: 48, color: "#ffffff" },
    };
    commit({
      ...edl,
      tracks: edl.tracks.map((t) => (t.id === track.id ? { ...t, clips: [...t.clips, clip] } : t)),
    });
    setSelected({ trackId: track.id, clipId: clip.id });
  };

  // -- save / render -------------------------------------------------------------
  const save = async (): Promise<string | null> => {
    if (!projectId) return null;
    setSaving(true);
    setMsg(null);
    try {
      const row = await api.post<{ id: string }>(`/projects/${projectId}/timeline`, {
        edl: edlRef.current,
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
      const versionId = await save();
      if (!versionId) {
        setMsg("Render aborted: timeline could not be saved.");
        return;
      }
      const job = await api.post<RenderJob>(
        `/projects/${projectId}/timeline/${versionId}/render`,
        {}
      );
      setRenders((r) => [job, ...r]);
      setActiveJobId(job.id);
      setMsg(`Render job ${job.id.slice(0, 8)}… queued.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Render failed.");
    } finally {
      setRendering(false);
    }
  };

  const exportTimeline = () => {
    const blob = new Blob([JSON.stringify(edlRef.current, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `timeline-${projectId || "untitled"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-3 min-h-[calc(100vh-9rem)] flex flex-col">
      {/* top toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="bg-studio-panel2 border border-studio-border rounded-md px-3 py-1.5 text-sm text-studio-text"
        >
          {projects.length === 0 && <option value="">No projects</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.title}</option>
          ))}
        </select>
        <div className="flex gap-1">
          <ToolbarBtn onClick={undo} disabled={history.past.length === 0} title="Undo">↶ Undo</ToolbarBtn>
          <ToolbarBtn onClick={redo} disabled={history.future.length === 0} title="Redo">↷ Redo</ToolbarBtn>
        </div>
        <div className="flex gap-1 ml-auto">
          <ToolbarBtn onClick={save} disabled={saving || !projectId} primary>{saving ? "Saving…" : "Save Timeline"}</ToolbarBtn>
          <ToolbarBtn onClick={render} disabled={rendering || !projectId} primary>{rendering ? "Queuing…" : "▶ Render"}</ToolbarBtn>
          <ToolbarBtn onClick={exportTimeline} disabled={!projectId}>Export</ToolbarBtn>
        </div>
      </div>
      {msg && <div className="text-sm text-studio-muted">{msg}</div>}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[240px_1fr_280px] gap-3">
        {/* left: assets / scenes */}
        <aside className="bg-studio-panel border border-studio-border rounded-lg overflow-hidden flex flex-col max-h-[70vh]">
          <div className="flex border-b border-studio-border">
            {(["assets", "scenes"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setLeftTab(t)}
                className={`flex-1 py-2 text-xs capitalize ${leftTab === t ? "text-accent border-b-2 border-accent" : "text-studio-muted"}`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {leftTab === "assets" && (
              assets.length === 0 ? (
                <p className="text-xs text-studio-faint p-2">No assets. Generated media will appear here.</p>
              ) : (
                assets.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => addClipFromAsset(a)}
                    className="w-full text-left bg-studio-panel2 border border-studio-border rounded p-2 hover:border-accent/50"
                  >
                    <div className="text-xs text-studio-text">{a.asset_type}</div>
                    <div className="text-[11px] text-studio-faint font-mono truncate">{a.source_url || a.object_key}</div>
                    <div className="text-[11px] text-accent mt-1">+ add to timeline</div>
                  </button>
                ))
              )
            )}
            {leftTab === "scenes" && (
              scenes.length === 0 ? (
                <p className="text-xs text-studio-faint p-2">No scenes for this project yet.</p>
              ) : (
                scenes.map((s) => (
                  <div key={s.id} className="bg-studio-panel2 border border-studio-border rounded p-2">
                    <div className="text-xs text-studio-text">
                      <span className="text-accent font-mono mr-1">{String(s.position).padStart(2, "0")}</span>
                      {s.visual_prompt || "(untitled scene)"}
                    </div>
                    <div className="text-[11px] text-studio-faint mt-0.5 line-clamp-3">{s.script_segment}</div>
                  </div>
                ))
              )
            )}
          </div>
        </aside>

        {/* center: preview + timeline */}
        <div className="flex flex-col gap-3 min-w-0">
          <PreviewPlayer
            edl={edl}
            playhead={playhead}
            playing={playing}
            onTogglePlay={() => setPlaying((p) => !p)}
            onSeek={(t) => {
              setPlayhead(t);
            }}
          />
          <div className="flex items-center gap-2">
            <button
              onClick={addTextClip}
              className="text-xs px-2.5 py-1 rounded-md border border-studio-border text-studio-text hover:border-accent/60"
            >
              + Text clip at playhead
            </button>
            <span className="text-[11px] text-studio-faint">
              {edl.tracks.reduce((n, t) => n + t.clips.length, 0)} clips
            </span>
          </div>
          <VideoEditor
            edl={edl}
            onChange={commit}
            playhead={playhead}
            onSeek={setPlayhead}
            selected={selected}
            onSelect={setSelected}
          />
        </div>

        {/* right: inspector + render jobs */}
        <aside className="space-y-3 max-h-[70vh] overflow-y-auto">
          <Inspector
            clip={selectedClip?.clip ?? null}
            trackType={selectedClip?.trackType ?? null}
            onPatch={patchSelected}
            onDelete={deleteSelected}
          />
          <div className="bg-studio-panel border border-studio-border rounded-lg p-3">
            <h3 className="text-xs font-medium text-studio-text mb-2">Render jobs</h3>
            {renders.length === 0 ? (
              <p className="text-[11px] text-studio-faint">No render jobs yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {renders.map((r) => (
                  <li key={r.id} className="text-[11px] font-mono">
                    <span className="text-studio-muted">{r.id.slice(0, 12)}…</span>{" "}
                    <StatusPill status={r.status} />
                    {r.id === activeJobId && <span className="text-accent ml-1">● live</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const color =
    status === "COMPLETED"
      ? "text-emerald-400 border-emerald-500/40 bg-emerald-500/10"
      : status === "FAILED"
        ? "text-red-400 border-red-500/40 bg-red-500/10"
        : status === "CANCELED"
          ? "text-studio-faint border-studio-border bg-studio-panel2"
          : "text-amber-300 border-amber-500/40 bg-amber-500/10";
  return (
    <span className={`px-1.5 py-0.5 rounded border text-[10px] ${color}`}>{status}</span>
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
