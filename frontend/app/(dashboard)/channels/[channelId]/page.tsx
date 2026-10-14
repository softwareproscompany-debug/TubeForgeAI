"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, asList, fmtDate } from "../../../../lib/api";
import type {
  AnalyticsSnapshot, AutomationRule, Channel, ContentIdea, Project, PublicationJob,
} from "../../../../lib/types";
import StatusBadge, { SourceLabel } from "../../../../components/StatusBadge";

const TABS = ["Overview", "Content", "Calendar", "Analytics", "Branding", "Automation", "Publishing"] as const;

export default function ChannelDetailPage() {
  const params = useParams();
  const channelId = params.channelId as string;
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [channel, setChannel] = useState<Channel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setChannel(await api.get<Channel>(`/channels/${channelId}`));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load channel.");
      } finally {
        setLoading(false);
      }
    })();
  }, [channelId]);

  const disconnect = async () => {
    if (!window.confirm("Disconnect this channel? Automation stops immediately.")) return;
    try {
      await api.post(`/channels/${channelId}/disconnect`);
      setChannel((c) => (c ? { ...c, is_active: false } : c));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Disconnect failed.");
    }
  };

  if (loading) return <div className="text-studio-muted text-sm">Loading channel…</div>;
  if (error || !channel)
    return <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 text-sm text-red-300">{error || "Channel not found."}</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-studio-text">{channel.title}</h1>
          <div className="text-xs text-studio-faint font-mono mt-1">{channel.youtube_channel_id}</div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={channel.is_active ? "HEALTHY" : "PAUSED"} />
          {channel.is_active && (
            <button onClick={disconnect} className="text-xs text-red-400 hover:underline">Disconnect</button>
          )}
        </div>
      </div>

      <div className="flex gap-1 border-b border-studio-border overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 -mb-px ${
              tab === t ? "border-accent text-accent" : "border-transparent text-studio-muted hover:text-studio-text"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && <OverviewTab channel={channel} />}
      {tab === "Content" && <ContentTab channelId={channelId} />}
      {tab === "Calendar" && <ChannelCalendarTab channelId={channelId} />}
      {tab === "Analytics" && <ChannelAnalyticsTab channelId={channelId} />}
      {tab === "Branding" && <BrandingTab channel={channel} />}
      {tab === "Automation" && <AutomationTab channelId={channelId} />}
      {tab === "Publishing" && <PublishingSettingsTab channel={channel} />}
    </div>
  );
}

function OverviewTab({ channel }: { channel: Channel }) {
  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-5 space-y-3 text-sm">
      <p className="text-studio-muted">{channel.description || "No description set."}</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <Info k="Language" v={channel.default_language} />
        <Info k="Timezone" v={channel.timezone} />
      </div>
    </div>
  );
}

function ContentTab({ channelId }: { channelId: string }) {
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [i, p] = await Promise.all([
        api.get<ContentIdea[]>(`/channels/${channelId}/ideas`).catch(() => [] as ContentIdea[]),
        api.get<Project[]>(`/projects?channel_id=${channelId}`).catch(() => [] as Project[]),
      ]);
      setIdeas(asList(i));
      setProjects(asList(p));
      setLoading(false);
    })();
  }, [channelId]);

  const createProject = async (ideaId: string) => {
    setMsg(null);
    try {
      const p = await api.post<Project>(`/ideas/${ideaId}/create-project`);
      setMsg(`Project "${p.title}" created.`);
      setProjects((prev) => [p, ...prev]);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed.");
    }
  };

  if (loading) return <div className="text-studio-muted text-sm">Loading content…</div>;
  return (
    <div className="space-y-5">
      {msg && <div className="text-sm text-accent">{msg}</div>}
      <section>
        <h2 className="font-medium text-studio-text mb-2">Content ideas</h2>
        {ideas.length === 0 ? (
          <p className="text-sm text-studio-faint">No ideas yet. Run research from the Research page to generate opportunities.</p>
        ) : (
          <ul className="space-y-2">
            {ideas.map((i) => (
              <li key={i.id} className="bg-studio-panel border border-studio-border rounded-lg p-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm text-studio-text font-medium">{i.title}</div>
                  <div className="text-xs text-studio-faint">{i.topic} · {i.format} · confidence {(i.confidence_score * 100).toFixed(0)}%</div>
                </div>
                <button onClick={() => createProject(i.id)} className="text-xs text-accent hover:underline shrink-0">
                  Create project
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2 className="font-medium text-studio-text mb-2">Projects</h2>
        {projects.length === 0 ? (
          <p className="text-sm text-studio-faint">No projects for this channel yet.</p>
        ) : (
          <ul className="space-y-2">
            {projects.map((p) => (
              <li key={p.id} className="bg-studio-panel border border-studio-border rounded-lg p-3 flex items-center justify-between gap-3">
                <a href={`/projects/${p.id}`} className="text-sm text-studio-text hover:text-accent">{p.title}</a>
                <StatusBadge status={p.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ChannelCalendarTab({ channelId }: { channelId: string }) {
  const [pubs, setPubs] = useState<PublicationJob[]>([]);
  useEffect(() => {
    (async () => {
      const data = asList(await api.get<PublicationJob[]>("/publications").catch(() => [] as PublicationJob[]));
      setPubs(data.filter((p) => p.scheduled_at));
    })();
  }, [channelId]);
  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-4">
      {pubs.length === 0 ? (
        <p className="text-sm text-studio-faint">No scheduled publications. See the full Content Calendar.</p>
      ) : (
        <ul className="space-y-2">
          {pubs.sort((a, b) => new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime()).map((p) => (
            <li key={p.id} className="text-sm flex justify-between gap-3">
              <span className="text-studio-text">{p.title}</span>
              <span className="text-studio-faint">{fmtDate(p.scheduled_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChannelAnalyticsTab({ channelId }: { channelId: string }) {
  const [snaps, setSnaps] = useState<AnalyticsSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      setSnaps(asList(await api.get<AnalyticsSnapshot[]>(`/channels/${channelId}/analytics`).catch(() => [] as AnalyticsSnapshot[])));
      setLoading(false);
    })();
  }, [channelId]);
  if (loading) return <div className="text-studio-muted text-sm">Loading analytics…</div>;
  if (snaps.length === 0) return <p className="text-sm text-studio-faint">No analytics snapshots yet.</p>;
  return (
    <div className="space-y-3">
      {snaps.map((s) => (
        <div key={s.id} className="bg-studio-panel border border-studio-border rounded-lg p-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-studio-faint">{fmtDate(s.captured_at)}</span>
            <SourceLabel source={s.source} />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(s.metrics).map(([k, v]) => (
              <div key={k}>
                <div className="text-[11px] text-studio-faint">{k}</div>
                <div className="text-studio-text font-medium">{v.toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function BrandingTab({ channel }: { channel: Channel }) {
  const [config, setConfig] = useState(JSON.stringify(channel.brand_config || {}, null, 2));
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    setMsg(null);
    try {
      await api.patch(`/channels/${channel.id}/settings`, { brand_config: JSON.parse(config) });
      setMsg("Branding saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
    }
  };
  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-5 space-y-3">
      <p className="text-xs text-studio-faint">Brand configuration (JSON) — voice, colors, fonts, intro/outro preferences.</p>
      <textarea
        value={config}
        onChange={(e) => setConfig(e.target.value)}
        rows={12}
        spellCheck={false}
        className="w-full bg-studio-bg border border-studio-border rounded-md p-3 font-mono text-xs text-studio-text"
      />
      <button onClick={save} className="text-sm bg-accent text-black font-medium px-4 py-1.5 rounded-md">Save branding</button>
      {msg && <div className="text-sm text-studio-muted">{msg}</div>}
    </div>
  );
}

function AutomationTab({ channelId }: { channelId: string }) {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      setRules(asList(await api.get<AutomationRule[]>(`/channels/${channelId}/automation-rules`).catch(() => [] as AutomationRule[])));
      setLoading(false);
    })();
  }, [channelId]);
  if (loading) return <div className="text-studio-muted text-sm">Loading rules…</div>;
  return (
    <div className="space-y-3">
      {rules.length === 0 ? (
        <p className="text-sm text-studio-faint">
          No automation rules for this channel. Create them from <a href="/automation" className="text-accent hover:underline">Automation Workflows</a>.
        </p>
      ) : (
        rules.map((r) => (
          <div key={r.id} className="bg-studio-panel border border-studio-border rounded-lg p-4 flex items-center justify-between">
            <div>
              <div className="text-sm text-studio-text font-medium">{r.name}</div>
              <div className="text-xs text-studio-faint">trigger: {r.trigger}</div>
            </div>
            <StatusBadge status={r.enabled ? "HEALTHY" : "PAUSED"} />
          </div>
        ))
      )}
    </div>
  );
}

function PublishingSettingsTab({ channel }: { channel: Channel }) {
  const [policy, setPolicy] = useState(JSON.stringify(channel.publishing_policy || {}, null, 2));
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    setMsg(null);
    try {
      await api.patch(`/channels/${channel.id}/settings`, { publishing_policy: JSON.parse(policy) });
      setMsg("Publishing policy saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
    }
  };
  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-5 space-y-3">
      <p className="text-xs text-studio-faint">Publishing policy (JSON) — default visibility, approval requirements, scheduling windows.</p>
      <textarea
        value={policy}
        onChange={(e) => setPolicy(e.target.value)}
        rows={10}
        spellCheck={false}
        className="w-full bg-studio-bg border border-studio-border rounded-md p-3 font-mono text-xs text-studio-text"
      />
      <button onClick={save} className="text-sm bg-accent text-black font-medium px-4 py-1.5 rounded-md">Save policy</button>
      {msg && <div className="text-sm text-studio-muted">{msg}</div>}
    </div>
  );
}

function Info({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-studio-panel2 border border-studio-border rounded p-3">
      <div className="text-[11px] text-studio-faint">{k}</div>
      <div className="text-studio-text mt-0.5">{v || "—"}</div>
    </div>
  );
}
