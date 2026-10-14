"use client";

import { useState } from "react";
import type { TimelineClip, TimelineV1 } from "../lib/types";

const PX_PER_SEC = 8;
const TRACK_COLORS: Record<string, string> = {
  video: "bg-accent/25 border-accent/60",
  audio: "bg-emerald-500/20 border-emerald-500/50",
  caption: "bg-purple-500/20 border-purple-500/50",
};

export default function TimelineEditor({
  timeline,
  onChange,
}: {
  timeline: TimelineV1;
  onChange: (t: TimelineV1) => void;
}) {
  const [selected, setSelected] = useState<{ trackId: string; clipId: string } | null>(null);

  const totalDuration = Math.max(
    60,
    ...timeline.tracks.flatMap((t) => t.clips.map((c) => c.end_s))
  );

  const moveClip = (trackId: string, clipId: string, deltaS: number) => {
    onChange({
      ...timeline,
      tracks: timeline.tracks.map((t) =>
        t.id !== trackId
          ? t
          : {
              ...t,
              clips: t.clips.map((c) =>
                c.id !== clipId
                  ? c
                  : {
                      ...c,
                      start_s: Math.max(0, c.start_s + deltaS),
                      end_s: Math.max(c.start_s + deltaS + 0.5, c.end_s + deltaS),
                    }
              ),
            }
      ),
    });
  };

  return (
    <div className="bg-studio-bg border border-studio-border rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-studio-border flex items-center justify-between">
        <span className="text-xs text-studio-muted">Multitrack timeline · v{timeline.version}</span>
        {selected && (
          <span className="text-xs text-accent">selected clip: {selected.clipId.slice(0, 8)}</span>
        )}
      </div>
      <div className="overflow-x-auto">
        <div style={{ minWidth: totalDuration * PX_PER_SEC + 200 }}>
          {/* ruler */}
          <div className="flex ml-36 h-6 border-b border-studio-border">
            {Array.from({ length: Math.ceil(totalDuration / 10) + 1 }).map((_, i) => (
              <div key={i} className="text-[10px] text-studio-faint pl-1" style={{ width: 10 * PX_PER_SEC }}>
                {i * 10}s
              </div>
            ))}
          </div>
          {timeline.tracks.map((track) => (
            <div key={track.id} className="flex border-b border-studio-border/60">
              <div className="w-36 shrink-0 px-3 py-2 bg-studio-panel">
                <div className="text-xs text-studio-text font-medium">{track.name}</div>
                <div className="text-[10px] text-studio-faint uppercase">{track.kind}</div>
              </div>
              <div className="relative h-12 flex-1">
                {track.clips.map((clip) => (
                  <ClipBlock
                    key={clip.id}
                    clip={clip}
                    kind={track.kind}
                    selected={selected?.clipId === clip.id}
                    onSelect={() => setSelected({ trackId: track.id, clipId: clip.id })}
                    onNudge={(d) => moveClip(track.id, clip.id, d)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="px-3 py-2 text-[11px] text-studio-faint">
        Click a clip to select it, then nudge with ◀ ▶ buttons in 1s steps. Trim via clip properties panel.
      </div>
    </div>
  );
}

function ClipBlock({
  clip,
  kind,
  selected,
  onSelect,
  onNudge,
}: {
  clip: TimelineClip;
  kind: string;
  selected: boolean;
  onSelect: () => void;
  onNudge: (d: number) => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`absolute top-1.5 h-9 border rounded px-1.5 text-[11px] overflow-hidden cursor-pointer flex items-center gap-1 ${
        TRACK_COLORS[kind] || TRACK_COLORS.video
      } ${selected ? "ring-2 ring-accent" : ""}`}
      style={{
        left: clip.start_s * PX_PER_SEC,
        width: Math.max(24, (clip.end_s - clip.start_s) * PX_PER_SEC),
      }}
      title={`${clip.label} · ${clip.start_s.toFixed(1)}s–${clip.end_s.toFixed(1)}s`}
    >
      <span className="text-studio-text truncate">{clip.label}</span>
      {selected && (
        <span className="flex gap-0.5 ml-auto shrink-0" onClick={(e) => e.stopPropagation()}>
          <button className="px-1 text-accent hover:brightness-150" onClick={() => onNudge(-1)} aria-label="Nudge left">◀</button>
          <button className="px-1 text-accent hover:brightness-150" onClick={() => onNudge(1)} aria-label="Nudge right">▶</button>
        </span>
      )}
    </div>
  );
}
