"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, asList } from "../../../lib/api";
import type { Channel } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setChannels(asList(await api.get<Channel[]>("/channels")));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load channels.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const connect = async () => {
    const youtube_channel_id = window.prompt("YouTube channel ID (or handle):");
    if (!youtube_channel_id) return;
    const title = window.prompt("Channel display title:") || youtube_channel_id;
    setConnecting(true);
    try {
      const res = await api.post<{ authorization_url: string; state: string }>("/channels/connect", {
        youtube_channel_id,
        title,
      });
      window.open(res.authorization_url, "_blank", "noopener");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connect failed.");
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-studio-text">Channels</h1>
        <button
          onClick={connect}
          disabled={connecting}
          className="bg-accent text-black font-medium text-sm px-4 py-2 min-h-[44px] rounded-md hover:brightness-110 disabled:opacity-50"
        >
          {connecting ? "Connecting…" : "+ Connect channel"}
        </button>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading channels…</div>}

      {!loading && channels.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">No channels connected</p>
          <p className="text-sm text-studio-muted mt-1">
            Connect a YouTube channel via OAuth to start producing content. The authorization page opens in a new tab.
          </p>
        </div>
      )}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {channels.map((c) => (
          <Link
            key={c.id}
            href={`/channels/${c.id}`}
            className="bg-studio-panel border border-studio-border rounded-lg p-4 hover:border-accent/50 transition-colors"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="font-medium text-studio-text">{c.title}</div>
              <StatusBadge status={c.is_active ? "HEALTHY" : "PAUSED"} />
            </div>
            <div className="text-xs text-studio-faint mt-1 font-mono">{c.youtube_channel_id}</div>
            <div className="text-sm text-studio-muted mt-2 line-clamp-2">{c.description || "No description."}</div>
            <div className="text-xs text-studio-faint mt-2">
              {c.default_language} · {c.timezone}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
