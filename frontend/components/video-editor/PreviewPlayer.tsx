"use client";

import { useEffect, useMemo, useRef } from "react";
import { clipEnd, fmtTime, type EDL, type EDLClip } from "../../lib/edl";

interface PreviewPlayerProps {
  edl: EDL;
  playhead: number;
  playing: boolean;
  onTogglePlay: () => void;
  onSeek: (t: number) => void;
}

const isPlayableUrl = (src: string) => /^https?:\/\//i.test(src);

function activeClipAt(clips: EDLClip[], t: number): EDLClip | null {
  for (const c of clips) {
    if (t >= c.start && t < clipEnd(c)) return c;
  }
  return null;
}

export default function PreviewPlayer({
  edl,
  playhead,
  playing,
  onTogglePlay,
  onSeek,
}: PreviewPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playheadRef = useRef(playhead);
  playheadRef.current = playhead;
  const playingRef = useRef(playing);
  playingRef.current = playing;

  const videoClips = useMemo(
    () =>
      edl.tracks
        .filter((t) => t.type === "video")
        .flatMap((t) => t.clips)
        .sort((a, b) => a.start - b.start),
    [edl]
  );
  const activeVideo = activeClipAt(videoClips, playhead);

  const overlays = useMemo(() => {
    const out: { clip: EDLClip; text: string; x: number; y: number; fontSize: number; color: string }[] = [];
    for (const track of edl.tracks)
      for (const clip of track.clips) {
        const ov = clip.textOverlay;
        if (!ov) continue;
        if (playhead >= clip.start && playhead < clipEnd(clip))
          out.push({
            clip,
            text: ov.text,
            x: ov.x,
            y: ov.y,
            fontSize: ov.fontSize,
            color: ov.color,
          });
      }
    return out;
  }, [edl, playhead]);

  // Keep the <video> element in sync with the timeline playhead.
  const activeId = activeVideo?.id;
  const activeSource = activeVideo?.source;
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = videoRef.current;
      if (v && activeSource && isPlayableUrl(activeSource)) {
        const clip = activeClipAt(videoClips, playheadRef.current);
        if (clip) {
          const expected = clip.in + (playheadRef.current - clip.start);
          if (playingRef.current) {
            if (v.paused) v.play().catch(() => {});
            const drift = Math.abs(v.currentTime - expected);
            if (drift > 0.6 && expected >= 0 && Number.isFinite(expected)) {
              try {
                v.currentTime = Math.max(0, expected);
              } catch {
                /* seek not ready yet */
              }
            }
          } else if (!v.paused) {
            v.pause();
          }
        } else if (!v.paused) {
          v.pause();
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [activeId, activeSource, videoClips]);

  const showVideo = !!activeVideo && isPlayableUrl(activeVideo.source);

  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-3 w-full max-w-full min-w-0">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-studio-muted">Preview</span>
        <span className="text-[11px] px-2 py-0.5 rounded border border-amber-500/40 text-amber-400 bg-amber-500/10">
          PREVIEW — not the final render
        </span>
      </div>

      {/* 16:9 canvas */}
      <div className="relative w-full aspect-video bg-black rounded overflow-hidden">
        {showVideo ? (
          <video
            key={activeVideo.id}
            ref={videoRef}
            src={activeVideo.source}
            className="absolute inset-0 w-full h-full object-contain"
            muted
            playsInline
            preload="auto"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6">
            {activeVideo ? (
              <>
                <div className="text-sm text-studio-text font-medium">
                  {activeVideo.label || activeVideo.source.split("/").pop()}
                </div>
                <div className="text-[11px] text-studio-faint mt-1 font-mono">
                  {fmtTime(activeVideo.start)} → {fmtTime(clipEnd(activeVideo))}
                </div>
                <div className="text-[11px] text-studio-faint mt-2 max-w-md">
                  Source is not a playable URL — the final render will include it.
                </div>
              </>
            ) : (
              <div className="text-xs text-studio-faint">
                {edl.duration === 0
                  ? "Add clips to the timeline to preview"
                  : "Gap — no video clip at playhead"}
              </div>
            )}
          </div>
        )}
        {/* text overlays */}
        {overlays.map((o) => (
          <div
            key={o.clip.id}
            className="absolute z-10 pointer-events-none font-semibold"
            style={{
              left: `${o.x * 100}%`,
              top: `${o.y * 100}%`,
              transform: "translate(-50%, -50%)",
              fontSize: Math.max(10, o.fontSize / 3),
              color: o.color,
              textShadow: "0 1px 4px rgba(0,0,0,0.9)",
              whiteSpace: "nowrap",
            }}
          >
            {o.text}
          </div>
        ))}
        {/* playhead timecode */}
        <div className="absolute bottom-2 right-2 text-[11px] font-mono text-studio-text bg-black/60 px-1.5 py-0.5 rounded">
          {fmtTime(playhead)}
        </div>
      </div>

      {/* transport */}
      <div className="flex items-center gap-3 mt-2">
        <button
          onClick={onTogglePlay}
          className="w-11 h-11 shrink-0 rounded-full bg-accent text-black flex items-center justify-center hover:brightness-110 touch-manipulation"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(0.1, edl.duration)}
          step={0.1}
          value={Math.min(playhead, edl.duration)}
          onChange={(e) => onSeek(Number(e.target.value))}
          className="flex-1 min-w-0 min-h-[44px] accent-cyan-400 touch-manipulation"
          aria-label="Seek"
        />
        <span className="text-[11px] font-mono text-studio-faint whitespace-nowrap">
          {fmtTime(playhead)} / {fmtTime(edl.duration)}
        </span>
      </div>
    </div>
  );
}
