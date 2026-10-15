// EDL (Edit Decision List) schema + client-side helpers for the video editor.
//
// Mirrors the backend contract in backend/projects/edl_to_ffmpeg.py:
//   clip.start      — position on the timeline, seconds
//   clip.in/out     — trim points *within the source media*, seconds
//                     (timeline duration of a clip = out - in)
//   transitions     — none | cut | fade | dissolve at the clip's head/tail
//   textOverlay     — x/y are fractional (0..1) anchors on the frame

export type EDLTransition = "none" | "cut" | "fade" | "dissolve";
export type EDLTrackType = "video" | "audio" | "text";

export interface EDLTextOverlay {
  text: string;
  x: number; // 0..1
  y: number; // 0..1
  fontSize: number;
  color: string;
}

export interface EDLClip {
  id: string;
  source: string;
  label?: string;
  start: number;
  in: number;
  out: number;
  transitions?: { in?: EDLTransition; out?: EDLTransition };
  textOverlay?: EDLTextOverlay;
}

export interface EDLTrack {
  id: string;
  type: EDLTrackType;
  name?: string;
  clips: EDLClip[];
}

export interface EDL {
  version: 1;
  tracks: EDLTrack[];
  duration: number;
}

export const TRANSITIONS: EDLTransition[] = ["none", "cut", "fade", "dissolve"];

export function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

export function blankEDL(): EDL {
  return {
    version: 1,
    tracks: [
      { id: "v1", type: "video", name: "Video 1", clips: [] },
      { id: "a1", type: "audio", name: "Audio 1", clips: [] },
      { id: "t1", type: "text", name: "Text overlays", clips: [] },
    ],
    duration: 0,
  };
}

export function clipEnd(clip: EDLClip): number {
  return clip.start + Math.max(0, clip.out - clip.in);
}

/** Recompute total duration and keep every track's clips sorted by start. */
export function normalizeEDL(edl: EDL): EDL {
  const tracks = edl.tracks.map((t) => ({
    ...t,
    clips: [...t.clips].sort((a, b) => a.start - b.start || a.id.localeCompare(b.id)),
  }));
  const duration = Math.max(
    0,
    ...tracks.flatMap((t) => t.clips.map(clipEnd))
  );
  return { ...edl, tracks, duration };
}

/** Lightweight client-side validation; returns a list of human-readable errors. */
export function validateEDLClient(edl: EDL): string[] {
  const errors: string[] = [];
  if (!edl || typeof edl !== "object") return ["Timeline is not an object."];
  if (edl.version !== 1) errors.push("version must be 1.");
  if (!Array.isArray(edl.tracks) || edl.tracks.length === 0)
    errors.push("At least one track is required.");
  let clips = 0;
  for (const track of edl.tracks ?? []) {
    if (!["video", "audio", "text"].includes(track.type))
      errors.push(`Track ${track.id}: unknown type ${track.type}.`);
    for (const clip of track.clips ?? []) {
      clips++;
      if (!clip.source) errors.push(`Clip ${clip.id}: missing source.`);
      if (clip.out <= clip.in)
        errors.push(`Clip ${clip.label || clip.id}: out must be after in.`);
      if (clip.start < 0) errors.push(`Clip ${clip.label || clip.id}: start < 0.`);
      for (const edge of ["in", "out"] as const) {
        const t = clip.transitions?.[edge];
        if (t && !TRANSITIONS.includes(t))
          errors.push(`Clip ${clip.label || clip.id}: bad transition ${t}.`);
      }
      const ov = clip.textOverlay;
      if (ov && (ov.x < 0 || ov.x > 1 || ov.y < 0 || ov.y > 1))
        errors.push(`Clip ${clip.label || clip.id}: overlay x/y must be 0..1.`);
    }
  }
  if (clips === 0) errors.push("Timeline has no clips.");
  return errors;
}

export function isEDLDocument(doc: unknown): doc is EDL {
  if (!doc || typeof doc !== "object") return false;
  const d = doc as Record<string, unknown>;
  if (d.version !== 1 || !Array.isArray(d.tracks)) return false;
  return (d.tracks as unknown[]).every(
    (t) =>
      !!t &&
      typeof t === "object" &&
      ["video", "audio", "text"].includes((t as EDLTrack).type)
  );
}

export function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const tenths = Math.floor((s % 1) * 10);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${tenths}`;
}
