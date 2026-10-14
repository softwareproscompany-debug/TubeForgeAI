// Color-coded badge for workflow states, upload states, and approval states.
// Status color only — never decorative.

function colorFor(status: string): string {
  const s = status.toUpperCase();
  if (["PUBLISHED", "APPROVED", "SCHEDULED", "READY_TO_PUBLISH", "SUCCESS", "HEALTHY"].includes(s))
    return "bg-emerald-500/15 text-emerald-400 border-emerald-500/40";
  if (["AWAITING_APPROVAL", "BLOCKED_ON_APPROVAL", "AUTHORIZATION_REQUIRED", "QUOTA_BLOCKED", "PAUSED"].includes(s))
    return "bg-amber-500/15 text-amber-400 border-amber-500/40";
  if (["FAILED", "PERMANENT_FAILURE", "CANCELED", "RETRYABLE_FAILURE", "BLOCKED_ON_RESOURCES", "UNHEALTHY"].includes(s))
    return "bg-red-500/15 text-red-400 border-red-500/40";
  if (["UPLOADING", "RENDERING", "GENERATING_ASSETS", "GENERATING_NARRATION", "ASSEMBLING", "PROCESSING", "VALIDATING"].includes(s))
    return "bg-accent/15 text-accent border-accent/40";
  return "bg-studio-panel2 text-studio-muted border-studio-border";
}

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${colorFor(status)}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

// Analytics metric source label — every number in the UI must carry its
// source: YOUTUBE_API (reported), CALCULATED (derived),
// AI_INTERPRETATION (model-generated), FORECAST (predicted).
export function SourceLabel({ source }: { source: string }) {
  const label: Record<string, string> = {
    YOUTUBE_API: "YouTube API",
    CALCULATED: "Calculated",
    AI_INTERPRETATION: "AI interpretation",
    FORECAST: "Forecast",
  };
  const color: Record<string, string> = {
    YOUTUBE_API: "bg-emerald-500/15 text-emerald-400 border-emerald-500/40",
    CALCULATED: "bg-accent/15 text-accent border-accent/40",
    AI_INTERPRETATION: "bg-purple-500/15 text-purple-400 border-purple-500/40",
    FORECAST: "bg-amber-500/15 text-amber-400 border-amber-500/40",
  };
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded border ${color[source] || "bg-studio-panel2 text-studio-muted border-studio-border"}`}>
      {label[source] || source}
    </span>
  );
}
