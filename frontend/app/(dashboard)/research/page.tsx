"use client";

import { useEffect, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { Channel, ContentIdea, Project, ResearchRun } from "../../../lib/types";

export default function ResearchPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [channelId, setChannelId] = useState("");
  const [query, setQuery] = useState("");
  const [runs, setRuns] = useState<ResearchRun[]>([]);
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [minConfidence, setMinConfidence] = useState(0);

  useEffect(() => {
    (async () => {
      const ch = asList(await api.get<Channel[]>("/channels").catch(() => [] as Channel[]));
      setChannels(ch);
      if (ch.length > 0) setChannelId(ch[0].id);
      setRuns(asList(await api.get<ResearchRun[]>("/research-runs").catch(() => [] as ResearchRun[])));
    })();
  }, []);

  useEffect(() => {
    if (!channelId) return;
    (async () => {
      setIdeas(asList(await api.get<ContentIdea[]>(`/channels/${channelId}/ideas`).catch(() => [] as ContentIdea[])));
    })();
  }, [channelId]);

  const startRun = async () => {
    if (!channelId || !query.trim()) return;
    setRunning(true);
    setMsg(null);
    try {
      // Backend ResearchRunCreateSerializer takes `channel`, not `channel_id`.
      const run = await api.post<ResearchRun>("/research-runs", {
        channel: channelId,
        query: query.trim(),
        parameters: {},
      });
      setRuns((r) => [run, ...r]);
      setMsg(`Research run ${run.id.slice(0, 8)}… started — ideas will appear below when ready.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Research run failed.");
    } finally {
      setRunning(false);
    }
  };

  const cancelRun = async (id: string) => {
    try {
      await api.post(`/research-runs/${id}/cancel`);
      setRuns((r) => r.map((x) => (x.id === id ? { ...x, status: "CANCELED" } : x)));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Cancel failed.");
    }
  };

  const createProject = async (ideaId: string) => {
    setMsg(null);
    try {
      const p = await api.post<Project>(`/ideas/${ideaId}/create-project`);
      setMsg(`Project "${p.title}" created.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed.");
    }
  };

  const filtered = ideas
    .filter((i) => i.confidence_score >= minConfidence)
    .filter((i) => !filter || i.format === filter)
    .sort((a, b) => b.priority - a.priority || b.confidence_score - a.confidence_score);

  const formats = Array.from(new Set(ideas.map((i) => i.format))).filter(Boolean);

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-studio-text">Research</h1>
      {msg && <div className="text-sm text-studio-muted bg-studio-panel border border-studio-border rounded p-3">{msg}</div>}

      <div className="bg-studio-panel border border-studio-border rounded-lg p-4 flex flex-wrap gap-3 items-end">
        <label className="text-sm">
          <span className="text-studio-muted block mb-1">Channel</span>
          <select value={channelId} onChange={(e) => setChannelId(e.target.value)}
            className="bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 text-studio-text">
            {channels.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </label>
        <label className="text-sm flex-1 min-w-64">
          <span className="text-studio-muted block mb-1">Research query</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. AI tools for small business 2026"
            className="w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text placeholder:text-studio-faint" />
        </label>
        <button onClick={startRun} disabled={running || !query.trim() || !channelId}
          className="bg-accent text-black font-medium text-sm px-4 py-2 rounded-md disabled:opacity-50">
          {running ? "Starting…" : "Run research"}
        </button>
      </div>

      <div className="grid lg:grid-cols-[260px_1fr] gap-5">
        {/* left filters */}
        <aside className="bg-studio-panel border border-studio-border rounded-lg p-4 h-fit space-y-4">
          <h2 className="text-sm font-medium text-studio-text">Filters</h2>
          <label className="block text-sm">
            <span className="text-studio-muted text-xs">Format</span>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}
              className="mt-1 w-full bg-studio-panel2 border border-studio-border rounded-md px-2 py-1.5 text-studio-text">
              <option value="">All formats</option>
              {formats.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-studio-muted text-xs">Min confidence: {(minConfidence * 100).toFixed(0)}%</span>
            <input type="range" min={0} max={1} step={0.05} value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))} className="w-full mt-1" />
          </label>
          <div>
            <h3 className="text-xs font-medium text-studio-muted mb-2">Recent runs</h3>
            {runs.length === 0 ? (
              <p className="text-xs text-studio-faint">No research runs yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {runs.slice(0, 6).map((r) => (
                  <li key={r.id} className="text-xs bg-studio-panel2 border border-studio-border rounded p-2 flex justify-between gap-2">
                    <span className="text-studio-text truncate">{r.query}</span>
                    {["QUEUED", "RUNNING", "RESEARCHING"].includes(r.status.toUpperCase()) ? (
                      <button onClick={() => cancelRun(r.id)} className="text-red-400 hover:underline shrink-0">Cancel</button>
                    ) : (
                      <span className="text-studio-faint shrink-0">{r.status}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        {/* ranked opportunity cards */}
        <div className="space-y-3">
          {filtered.length === 0 ? (
            <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
              <p className="text-studio-text font-medium">No opportunities yet</p>
              <p className="text-sm text-studio-muted mt-1">Run a research query above to discover ranked content opportunities for this channel.</p>
            </div>
          ) : (
            filtered.map((idea) => <IdeaCard key={idea.id} idea={idea} onCreate={() => createProject(idea.id)} />)
          )}
        </div>
      </div>
    </div>
  );
}

function IdeaCard({ idea, onCreate }: { idea: ContentIdea; onCreate: () => void }) {
  const ev = idea.supporting_evidence;
  return (
    <div className="bg-studio-panel border border-studio-border rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-studio-text font-medium">{idea.title}</div>
          <div className="text-xs text-studio-faint mt-0.5">{idea.topic} · {idea.format} · priority {idea.priority}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-accent font-semibold">{(idea.confidence_score * 100).toFixed(0)}%</div>
          <div className="text-[11px] text-studio-faint">confidence</div>
        </div>
      </div>
      <ConfidenceBar score={idea.confidence_score} />
      <div className="mt-3 text-xs">
        <div className="text-studio-muted font-medium mb-1">Why this opportunity</div>
        <EvidenceBlock evidence={ev} />
      </div>
      <div className="mt-3 flex gap-2">
        <button onClick={onCreate} className="text-xs bg-accent/15 border border-accent/40 text-accent px-3 py-1.5 rounded-md hover:bg-accent/25">
          Create project
        </button>
      </div>
    </div>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  return (
    <div className="mt-2 h-1.5 bg-studio-panel2 rounded overflow-hidden">
      <div className="h-full bg-accent" style={{ width: `${Math.round(score * 100)}%` }} />
    </div>
  );
}

function EvidenceBlock({ evidence }: { evidence: ContentIdea["supporting_evidence"] }) {
  if (!evidence) return <p className="text-studio-faint">No evidence recorded.</p>;
  if (Array.isArray(evidence)) {
    return (
      <ul className="space-y-1">
        {evidence.map((e, i) => (
          <li key={i} className="text-studio-muted">
            <span className="text-studio-faint">observed:</span> {typeof e === "string" ? e : JSON.stringify(e)}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <dl className="grid sm:grid-cols-2 gap-1.5">
      {Object.entries(evidence).map(([k, v]) => (
        <div key={k} className="bg-studio-panel2 border border-studio-border rounded p-2">
          <dt className="text-studio-faint">{k} <span className="italic">(estimate vs observed — see source)</span></dt>
          <dd className="text-studio-text">{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
