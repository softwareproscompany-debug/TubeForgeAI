"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  clipEnd,
  fmtTime,
  normalizeEDL,
  uid,
  type EDL,
  type EDLClip,
  type EDLTrack,
} from "../../lib/edl";

const MIN_CLIP_DUR = 0.2;

const TRACK_STYLE: Record<string, { row: string; clip: string; label: string }> = {
  video: {
    row: "h-20",
    clip: "bg-accent/20 border-accent/60",
    label: "VIDEO",
  },
  audio: {
    row: "h-14",
    clip: "bg-emerald-500/20 border-emerald-500/50",
    label: "AUDIO",
  },
  text: {
    row: "h-14",
    clip: "bg-purple-500/20 border-purple-500/50",
    label: "TEXT",
  },
};

export interface ClipSelection {
  trackId: string;
  clipId: string;
}

interface VideoEditorProps {
  edl: EDL;
  onChange: (edl: EDL) => void;
  playhead: number;
  onSeek: (t: number) => void;
  selected: ClipSelection | null;
  onSelect: (sel: ClipSelection | null) => void;
}

interface DragState {
  mode: "trim-l" | "trim-r" | "move";
  trackId: string;
  clipId: string;
  startX: number;
  orig: EDLClip;
  targetTrackId: string;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

export default function VideoEditor({
  edl,
  onChange,
  playhead,
  onSeek,
  selected,
  onSelect,
}: VideoEditorProps) {
  const [pxPerSec, setPxPerSec] = useState(14);
  const [drag, setDrag] = useState<DragState | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const totalDuration = Math.max(30, edl.duration, playhead + 5);
  const width = totalDuration * pxPerSec;

  const emit = useCallback(
    (next: EDL) => onChange(normalizeEDL(next)),
    [onChange]
  );

  const findClip = useCallback(
    (trackId: string, clipId: string): { track: EDLTrack; clip: EDLClip } | null => {
      const track = edl.tracks.find((t) => t.id === trackId);
      const clip = track?.clips.find((c) => c.id === clipId);
      return track && clip ? { track, clip } : null;
    },
    [edl]
  );

  // Refs so the pointer handlers always see fresh state.
  const edlRef = useRef(edl);
  edlRef.current = edl;
  const emitRef = useRef(emit);
  emitRef.current = emit;
  const findClipRef = useRef(findClip);
  findClipRef.current = findClip;

  // -- drag handling ---------------------------------------------------------
  useEffect(() => {
    if (!drag) return;
    const onMove = (e: PointerEvent) => {
      const dxSec = round2((e.clientX - drag.startX) / pxPerSec);
      const found = findClipRef.current(drag.trackId, drag.clipId);
      if (!found) return;
      const { clip } = found;
      let patch: Partial<EDLClip> = {};
      let targetTrackId = drag.trackId;
      if (drag.mode === "trim-l") {
        const newIn = Math.min(
          Math.max(0, round2(drag.orig.in + dxSec)),
          round2(drag.orig.out - MIN_CLIP_DUR)
        );
        patch = { in: newIn, start: round2(drag.orig.start + (newIn - drag.orig.in)) };
      } else if (drag.mode === "trim-r") {
        patch = {
          out: Math.max(round2(drag.orig.out + dxSec), round2(drag.orig.in + MIN_CLIP_DUR)),
        };
      } else {
        patch = { start: Math.max(0, round2(drag.orig.start + dxSec)) };
        // Vertical drag: move across tracks of the same type.
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const row = el?.closest?.("[data-track-id]") as HTMLElement | null;
        const hoverTrackId = row?.dataset.trackId;
        const hoverTrack = edlRef.current.tracks.find((t) => t.id === hoverTrackId);
        if (
          hoverTrack &&
          hoverTrack.id !== drag.trackId &&
          hoverTrack.type === found.track.type
        ) {
          targetTrackId = hoverTrack.id;
        }
      }
      // Keep the drag anchored on the clip's current track so the lookup
      // stays valid after a cross-track move.
      setDrag((d) => (d ? { ...d, trackId: targetTrackId, targetTrackId } : d));
      const clipId = drag.clipId;
      const tracks = edlRef.current.tracks.map((t) => {
        if (t.id === drag.trackId && t.id === targetTrackId) {
          return {
            ...t,
            clips: t.clips.map((c) => (c.id === clipId ? { ...c, ...patch } : c)),
          };
        }
        if (t.id === drag.trackId)
          return { ...t, clips: t.clips.filter((c) => c.id !== clipId) };
        if (t.id === targetTrackId)
          return { ...t, clips: [...t.clips, { ...clip, ...patch }] };
        return t;
      });
      emitRef.current({ ...edlRef.current, tracks });
    };
    const onUp = () => setDrag(null);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [drag, pxPerSec]);

  const startDrag = (
    e: React.PointerEvent,
    mode: DragState["mode"],
    trackId: string,
    clip: EDLClip
  ) => {
    e.stopPropagation();
    e.preventDefault();
    onSelect({ trackId, clipId: clip.id });
    setDrag({
      mode,
      trackId,
      clipId: clip.id,
      startX: e.clientX,
      orig: { ...clip },
      targetTrackId: trackId,
    });
  };

  // -- clip ops ---------------------------------------------------------------
  const deleteSelected = useCallback(() => {
    if (!selected) return;
    const tracks = edlRef.current.tracks.map((t) =>
      t.id === selected.trackId
        ? { ...t, clips: t.clips.filter((c) => c.id !== selected.clipId) }
        : t
    );
    onSelect(null);
    emitRef.current({ ...edlRef.current, tracks });
  }, [selected, onSelect]);

  const splitAtPlayhead = useCallback(() => {
    const t = playhead;
    const targets: { track: EDLTrack; clip: EDLClip }[] = [];
    const sel = selected ? findClipRef.current(selected.trackId, selected.clipId) : null;
    const consider = (track: EDLTrack, clip: EDLClip) => {
      const end = clipEnd(clip);
      if (t > clip.start + MIN_CLIP_DUR && t < end - MIN_CLIP_DUR)
        targets.push({ track, clip });
    };
    if (sel) consider(sel.track, sel.clip);
    else for (const track of edlRef.current.tracks) for (const clip of track.clips) consider(track, clip);
    if (targets.length === 0) return;
    const ids = new Set(targets.map(({ clip }) => clip.id));
    const tracks = edlRef.current.tracks.map((track) => {
      const out: EDLClip[] = [];
      for (const clip of track.clips) {
        if (!ids.has(clip.id)) {
          out.push(clip);
          continue;
        }
        const leftOut = round2(clip.in + (t - clip.start));
        const left: EDLClip = {
          ...clip,
          out: leftOut,
          transitions: { ...clip.transitions, out: "cut" },
        };
        const right: EDLClip = {
          ...clip,
          id: uid("clip"),
          start: round2(t),
          in: leftOut,
          label: clip.label ? `${clip.label} (2)` : undefined,
          transitions: { ...clip.transitions, in: "cut" },
        };
        out.push(left, right);
      }
      return { ...track, clips: out };
    });
    emitRef.current({ ...edlRef.current, tracks });
  }, [playhead, selected]);

  // Keyboard: Delete/Backspace removes the selected clip.
  const onKeyDown = (e: React.KeyboardEvent) => {
    const el = e.target as HTMLElement;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT")
      return;
    if ((e.key === "Delete" || e.key === "Backspace") && selected) {
      e.preventDefault();
      deleteSelected();
    }
  };

  const seekFromRuler = (e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    onSeek(Math.max(0, round2((e.clientX - rect.left) / pxPerSec)));
  };

  const styleFor = TRACK_STYLE;
  const selectedClip = selected ? findClip(selected.trackId, selected.clipId)?.clip ?? null : null;

  return (
    <div
      className="bg-studio-bg border border-studio-border rounded-lg overflow-hidden select-none"
      onKeyDown={onKeyDown}
      tabIndex={0}
      aria-label="Video timeline editor"
    >
      {/* toolbar */}
      <div className="px-3 py-2 border-b border-studio-border flex items-center gap-2 flex-wrap">
        <span className="text-xs text-studio-muted mr-1">
          {fmtTime(playhead)} / {fmtTime(edl.duration)}
        </span>
        <div className="flex items-center gap-1 text-xs">
          <ToolBtn onClick={() => setPxPerSec((z) => Math.max(4, z - 4))} title="Zoom out">−</ToolBtn>
          <ToolBtn onClick={() => setPxPerSec((z) => Math.min(80, z + 4))} title="Zoom in">+</ToolBtn>
        </div>
        <ToolBtn onClick={splitAtPlayhead} title="Split clip(s) at playhead">✂ Split</ToolBtn>
        <ToolBtn onClick={deleteSelected} disabled={!selected} title="Delete selected clip (Del)">
          🗑 Delete
        </ToolBtn>
        <span className="ml-auto text-[11px] text-studio-faint hidden md:block">
          Drag edges to trim · drag body to move · drag across same-type tracks to move tracks
        </span>
      </div>

      <div ref={scrollRef} className="overflow-x-auto">
        <div style={{ minWidth: width + 220 }}>
          {/* ruler */}
          <div className="flex ml-40">
            <div
              className="relative h-7 border-b border-studio-border cursor-pointer flex-1"
              style={{ width }}
              onClick={seekFromRuler}
            >
              {Array.from({ length: Math.floor(totalDuration / 5) + 1 }).map((_, i) => (
                <div
                  key={i}
                  className="absolute top-0 h-full border-l border-studio-border/60 pl-1 text-[10px] text-studio-faint"
                  style={{ left: i * 5 * pxPerSec }}
                >
                  {fmtTime(i * 5)}
                </div>
              ))}
              {/* playhead */}
              <div
                className="absolute top-0 bottom-0 w-px bg-red-500 z-20 pointer-events-none"
                style={{ left: playhead * pxPerSec }}
              >
                <div className="w-2.5 h-2.5 bg-red-500 rotate-45 -translate-x-[5px] -translate-y-[1px]" />
              </div>
            </div>
          </div>

          {/* tracks */}
          {edl.tracks.map((track) => {
            const st = styleFor[track.type] ?? styleFor.video;
            return (
              <div key={track.id} className="flex border-b border-studio-border/60 last:border-b-0">
                <div className="w-40 shrink-0 px-3 py-2 bg-studio-panel flex flex-col justify-center">
                  <div className="text-xs text-studio-text font-medium truncate">
                    {track.name || track.id}
                  </div>
                  <div className="text-[10px] text-studio-faint uppercase tracking-wide">
                    {st.label} · {track.clips.length}
                  </div>
                </div>
                <div
                  data-track-id={track.id}
                  className={`relative flex-1 ${st.row} bg-studio-bg/40`}
                  style={{ width }}
                  onClick={() => onSelect(null)}
                >
                  {track.clips.length === 0 && (
                    <span className="absolute inset-0 flex items-center px-3 text-[11px] text-studio-faint/60 pointer-events-none">
                      Empty {st.label.toLowerCase()} track
                    </span>
                  )}
                  {track.clips.map((clip) => (
                    <ClipBlock
                      key={clip.id}
                      clip={clip}
                      trackType={track.type}
                      pxPerSec={pxPerSec}
                      selected={selected?.trackId === track.id && selected?.clipId === clip.id}
                      onBodyDown={(e) => startDrag(e, "move", track.id, clip)}
                      onTrimLeft={(e) => startDrag(e, "trim-l", track.id, clip)}
                      onTrimRight={(e) => startDrag(e, "trim-r", track.id, clip)}
                    />
                  ))}
                  {/* playhead continues through tracks */}
                  <div
                    className="absolute top-0 bottom-0 w-px bg-red-500/80 z-10 pointer-events-none"
                    style={{ left: playhead * pxPerSec }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {selectedClip && (
        <div className="px-3 py-1.5 border-t border-studio-border text-[11px] text-studio-muted">
          Selected: <span className="text-accent font-mono">{selectedClip.label || selectedClip.id.slice(0, 8)}</span>
          {" · "}{fmtTime(selectedClip.start)} → {fmtTime(clipEnd(selectedClip))}
          {" · "}src {selectedClip.in.toFixed(1)}s–{selectedClip.out.toFixed(1)}s
        </div>
      )}
    </div>
  );
}

function ToolBtn({
  children,
  onClick,
  disabled,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className="text-xs px-2.5 py-1 rounded-md border border-studio-border text-studio-text hover:border-accent/60 disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function ClipBlock({
  clip,
  trackType,
  pxPerSec,
  selected,
  onBodyDown,
  onTrimLeft,
  onTrimRight,
}: {
  clip: EDLClip;
  trackType: string;
  pxPerSec: number;
  selected: boolean;
  onBodyDown: (e: React.PointerEvent) => void;
  onTrimLeft: (e: React.PointerEvent) => void;
  onTrimRight: (e: React.PointerEvent) => void;
}) {
  const st = TRACK_STYLE[trackType] ?? TRACK_STYLE.video;
  const dur = clipEnd(clip) - clip.start;
  const label =
    clip.label ||
    (trackType === "text" && clip.textOverlay
      ? `“${clip.textOverlay.text.slice(0, 24)}”`
      : clip.source.split("/").pop()?.slice(0, 28) || clip.id.slice(0, 8));
  const transIn = clip.transitions?.in;
  const transOut = clip.transitions?.out;
  const showTrans = (t?: string) => t && t !== "none" && t !== "cut";

  return (
    <div
      onPointerDown={onBodyDown}
      className={`absolute top-1 bottom-1 border rounded-md px-2 text-[11px] overflow-hidden cursor-grab active:cursor-grabbing flex items-center ${st.clip} ${
        selected ? "ring-2 ring-accent z-10" : ""
      }`}
      style={{ left: clip.start * pxPerSec, width: Math.max(20, dur * pxPerSec) }}
      title={`${label}\n${fmtTime(clip.start)} → ${fmtTime(clipEnd(clip))} (src ${clip.in}s–${clip.out}s)`}
    >
      {/* trim handles */}
      <div
        onPointerDown={onTrimLeft}
        className="absolute left-0 top-0 bottom-0 w-2.5 cursor-ew-resize hover:bg-accent/40 rounded-l-md touch-none"
        title="Drag to trim head"
      />
      <div
        onPointerDown={onTrimRight}
        className="absolute right-0 top-0 bottom-0 w-2.5 cursor-ew-resize hover:bg-accent/40 rounded-r-md touch-none"
        title="Drag to trim tail"
      />
      {showTrans(transIn) && (
        <span className="absolute left-2.5 top-1 text-[9px] text-amber-300" title={`Transition in: ${transIn}`}>
          ◀
        </span>
      )}
      <span className="text-studio-text truncate mx-3 pointer-events-none">{label}</span>
      {showTrans(transOut) && (
        <span className="absolute right-2.5 top-1 text-[9px] text-amber-300" title={`Transition out: ${transOut}`}>
          ▶
        </span>
      )}
    </div>
  );
}
