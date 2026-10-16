"use client";

import {
  TRANSITIONS,
  clipEnd,
  fmtTime,
  type EDLClip,
  type EDLTextOverlay,
  type EDLTrackType,
  type EDLTransition,
} from "../../lib/edl";

interface InspectorProps {
  clip: EDLClip | null;
  trackType: EDLTrackType | null;
  onPatch: (patch: Partial<EDLClip>) => void;
  onDelete: () => void;
}

const inputCls =
  "mt-0.5 w-full bg-studio-bg border border-studio-border rounded px-2 py-1 text-studio-text text-xs";
const labelCls = "block text-[11px] text-studio-faint";

export default function Inspector({ clip, trackType, onPatch, onDelete }: InspectorProps) {
  if (!clip) {
    return (
      <div className="bg-studio-panel border border-studio-border rounded-lg p-3 w-full min-w-0">
        <h3 className="text-xs font-medium text-studio-text mb-2">Clip</h3>
        <p className="text-xs text-studio-faint">
          Click a clip in the timeline to edit its properties, transitions, and text
          overlays.
        </p>
      </div>
    );
  }

  const setTransition = (edge: "in" | "out", value: EDLTransition) =>
    onPatch({ transitions: { ...clip.transitions, [edge]: value } });

  const setOverlay = (patch: Partial<EDLTextOverlay>) =>
    onPatch({ textOverlay: { ...clip.textOverlay!, ...patch } });

  const addOverlay = () =>
    onPatch({
      textOverlay: { text: "Your text", x: 0.5, y: 0.85, fontSize: 48, color: "#ffffff" },
    });

  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-3 space-y-3 w-full min-w-0">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-studio-text">Clip</h3>
        <button onClick={onDelete} className="text-[11px] text-red-400 hover:underline">
          Delete
        </button>
      </div>

      <label className={labelCls}>
        Label
        <input
          value={clip.label ?? ""}
          placeholder={clip.id.slice(0, 12)}
          onChange={(e) => onPatch({ label: e.target.value })}
          className={inputCls}
        />
      </label>

      <label className={labelCls}>
        Source
        <input
          value={clip.source}
          onChange={(e) => onPatch({ source: e.target.value })}
          className={`${inputCls} font-mono`}
          spellCheck={false}
        />
      </label>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <label className={labelCls}>
          Start (s)
          <input
            type="number" step={0.1} min={0} value={clip.start}
            onChange={(e) => onPatch({ start: Number(e.target.value) })}
            className={inputCls}
          />
        </label>
        <label className={labelCls}>
          In (s)
          <input
            type="number" step={0.1} min={0} value={clip.in}
            onChange={(e) => onPatch({ in: Number(e.target.value) })}
            className={inputCls}
          />
        </label>
        <label className={labelCls}>
          Out (s)
          <input
            type="number" step={0.1} min={0.2} value={clip.out}
            onChange={(e) => onPatch({ out: Number(e.target.value) })}
            className={inputCls}
          />
        </label>
      </div>
      <div className="text-[11px] text-studio-faint">
        On timeline: <span className="text-studio-text font-mono">{fmtTime(clip.start)} → {fmtTime(clipEnd(clip))}</span>
        {" · "}length {(clip.out - clip.in).toFixed(1)}s
      </div>

      {/* transitions */}
      <div>
        <div className="text-[11px] text-studio-faint mb-1">Transitions</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {(["in", "out"] as const).map((edge) => (
            <label key={edge} className={labelCls}>
              {edge === "in" ? "Head" : "Tail"}
              <select
                value={clip.transitions?.[edge] ?? "none"}
                onChange={(e) => setTransition(edge, e.target.value as EDLTransition)}
                className={inputCls}
              >
                {TRANSITIONS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
          ))}
        </div>
        <p className="text-[10px] text-studio-faint mt-1">
          fade = through black · dissolve = cross-dissolve · cut/none = hard cut
        </p>
      </div>

      {/* text overlay */}
      <div className="border-t border-studio-border/60 pt-3">
        <div className="text-[11px] text-studio-faint mb-1">Text overlay</div>
        {clip.textOverlay ? (
          <div className="space-y-2">
            <label className={labelCls}>
              Text
              <textarea
                value={clip.textOverlay.text}
                rows={2}
                onChange={(e) => setOverlay({ text: e.target.value })}
                className={inputCls}
              />
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label className={labelCls}>
                X position
                <input
                  type="range" min={0} max={1} step={0.01} value={clip.textOverlay.x}
                  onChange={(e) => setOverlay({ x: Number(e.target.value) })}
                  className="w-full accent-purple-400"
                />
              </label>
              <label className={labelCls}>
                Y position
                <input
                  type="range" min={0} max={1} step={0.01} value={clip.textOverlay.y}
                  onChange={(e) => setOverlay({ y: Number(e.target.value) })}
                  className="w-full accent-purple-400"
                />
              </label>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label className={labelCls}>
                Font size
                <input
                  type="number" min={8} max={200} value={clip.textOverlay.fontSize}
                  onChange={(e) => setOverlay({ fontSize: Number(e.target.value) })}
                  className={inputCls}
                />
              </label>
              <label className={labelCls}>
                Color
                <span className="flex gap-1 mt-0.5">
                  <input
                    type="color" value={clip.textOverlay.color}
                    onChange={(e) => setOverlay({ color: e.target.value })}
                    className="w-8 h-7 bg-studio-bg border border-studio-border rounded cursor-pointer"
                  />
                  <input
                    value={clip.textOverlay.color}
                    onChange={(e) => setOverlay({ color: e.target.value })}
                    className={`${inputCls} font-mono !mt-0`}
                    spellCheck={false}
                  />
                </span>
              </label>
            </div>
            <button
              onClick={() => onPatch({ textOverlay: undefined })}
              className="text-[11px] text-red-400 hover:underline"
            >
              Remove overlay
            </button>
          </div>
        ) : (
          <button
            onClick={addOverlay}
            className="text-[11px] px-2 py-1 rounded border border-studio-border text-studio-text hover:border-accent/60"
          >
            + Add text overlay{trackType === "text" ? " (timed by this clip)" : ""}
          </button>
        )}
      </div>
    </div>
  );
}
