"use client";

import { useEffect, useState } from "react";
import { api, asList, fmtDate } from "../../../lib/api";
import type { AnalyticsSnapshot, Channel } from "../../../lib/types";
import { SourceLabel } from "../../../components/StatusBadge";

export default function AnalyticsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [channelId, setChannelId] = useState("");
  const [videoId, setVideoId] = useState("");
  const [channelSnaps, setChannelSnaps] = useState<AnalyticsSnapshot[]>([]);
  const [videoSnaps, setVideoSnaps] = useState<AnalyticsSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState("");

  useEffect(() => {
    (async () => {
      const ch = asList(await api.get<Channel[]>("/channels").catch(() => [] as Channel[]));
      setChannels(ch);
      if (ch.length > 0) setChannelId(ch[0].id);
    })();
  }, []);

  useEffect(() => {
    if (!channelId) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        setChannelSnaps(asList(await api.get<AnalyticsSnapshot[]>(`/channels/${channelId}/analytics`)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load analytics.");
        setChannelSnaps([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [channelId]);

  const loadVideo = async () => {
    if (!videoId.trim()) return;
    setError(null);
    try {
      setVideoSnaps(asList(await api.get<AnalyticsSnapshot[]>(`/videos/${videoId.trim()}/analytics`)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load video analytics.");
      setVideoSnaps([]);
    }
  };

  const filterSnaps = (snaps: AnalyticsSnapshot[]) =>
    sourceFilter ? snaps.filter((s) => s.source === sourceFilter) : snaps;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-studio-text">Analytics</h1>
      <p className="text-xs text-studio-faint -mt-3">
        Every number carries its source label: YouTube API (reported), Calculated (derived), AI interpretation (model-generated), Forecast (predicted).
      </p>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}

      <div className="flex flex-wrap gap-3 bg-studio-panel border border-studio-border rounded-lg p-3 items-end">
        <label className="text-xs">
          <span className="text-studio-muted block mb-1">Channel</span>
          <select value={channelId} onChange={(e) => setChannelId(e.target.value)}
            className="bg-studio-panel2 border border-studio-border rounded-md px-2 py-1.5 text-studio-text text-sm">
            {channels.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </label>
        <label className="text-xs">
          <span className="text-studio-muted block mb-1">Video ID</span>
          <div className="flex gap-2">
            <input value={videoId} onChange={(e) => setVideoId(e.target.value)} placeholder="YouTube video ID"
              className="bg-studio-bg border border-studio-border rounded-md px-2 py-1.5 text-studio-text text-sm placeholder:text-studio-faint" />
            <button onClick={loadVideo} className="text-sm px-3 py-1.5 min-h-[44px] rounded-md border border-studio-border text-studio-text hover:border-accent/60">
              Load
            </button>
          </div>
        </label>
        <label className="text-xs">
          <span className="text-studio-muted block mb-1">Source</span>
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
            className="bg-studio-panel2 border border-studio-border rounded-md px-2 py-1.5 text-studio-text text-sm">
            <option value="">All sources</option>
            <option value="YOUTUBE_API">YouTube API</option>
            <option value="CALCULATED">Calculated</option>
            <option value="AI_INTERPRETATION">AI interpretation</option>
            <option value="FORECAST">Forecast</option>
          </select>
        </label>
      </div>

      {loading && <div className="text-studio-muted text-sm">Loading analytics…</div>}

      <section>
        <h2 className="font-medium text-studio-text mb-3">Channel snapshots</h2>
        <SnapshotList snaps={filterSnaps(channelSnaps)} empty="No channel analytics snapshots yet. Snapshots are captured from the YouTube API or computed by the backend." />
      </section>

      {videoSnaps.length > 0 && (
        <section>
          <h2 className="font-medium text-studio-text mb-3">Video snapshots</h2>
          <SnapshotList snaps={filterSnaps(videoSnaps)} empty="No snapshots for this video." />
        </section>
      )}
    </div>
  );
}

function SnapshotList({ snaps, empty }: { snaps: AnalyticsSnapshot[]; empty: string }) {
  if (snaps.length === 0) return <p className="text-sm text-studio-faint">{empty}</p>;
  return (
    <div className="space-y-3">
      {snaps.map((s) => (
        <div key={s.id} className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs text-studio-faint">{fmtDate(s.captured_at)}</span>
            <SourceLabel source={s.source} />
          </div>
          {Object.keys(s.metrics).length === 0 ? (
            <p className="text-xs text-studio-faint">No metrics in this snapshot.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Object.entries(s.metrics).map(([k, v]) => (
                <div key={k} className="bg-studio-panel2 border border-studio-border rounded p-2.5">
                  <div className="text-[11px] text-studio-faint">{k}</div>
                  <div className="text-studio-text font-medium">{v.toLocaleString()}</div>
                </div>
              ))}
            </div>
          )}
          {s.source === "FORECAST" && (
            <p className="text-[11px] text-amber-400 mt-2">Forecast — predicted values, not observed data.</p>
          )}
          {s.source === "AI_INTERPRETATION" && (
            <p className="text-[11px] text-purple-400 mt-2">AI interpretation — model-generated analysis, verify before acting.</p>
          )}
        </div>
      ))}
    </div>
  );
}
