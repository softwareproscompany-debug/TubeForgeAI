"use client";

import { useEffect, useState } from "react";
import { api, asList, fmtDate } from "../../../lib/api";
import type { Channel, Project, PublicationJob } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

export default function PublishingPage() {
  const [pubs, setPubs] = useState<PublicationJob[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [acting, setActing] = useState<string | null>(null);
  const [form, setForm] = useState({
    project_id: "", channel_id: "", title: "", description: "", tags: "",
    visibility: "private", scheduled_at: "",
  });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, pr, ch] = await Promise.all([
        api.get<PublicationJob[]>("/publications"),
        api.get<Project[]>("/projects").catch(() => [] as Project[]),
        api.get<Channel[]>("/channels").catch(() => [] as Channel[]),
      ]);
      setPubs(asList(p));
      setProjects(asList(pr));
      setChannels(asList(ch));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load publications.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const action = async (id: string, act: "validate" | "approve" | "schedule" | "cancel") => {
    setActing(id + act);
    try {
      await api.post(`/publications/${id}/${act}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${act} failed.`);
    } finally {
      setActing(null);
    }
  };

  const create = async () => {
    setActing("create");
    try {
      await api.post<PublicationJob>("/publications", {
        project_id: form.project_id || undefined,
        channel_id: form.channel_id || undefined,
        title: form.title,
        description: form.description,
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        visibility: form.visibility,
        scheduled_at: form.scheduled_at || null,
        idempotency_key: `pub-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      });
      setShowNew(false);
      setForm({ project_id: "", channel_id: "", title: "", description: "", tags: "", visibility: "private", scheduled_at: "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Creation failed.");
    } finally {
      setActing(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-studio-text">Publishing</h1>
        <button onClick={() => setShowNew(true)}
          className="bg-accent text-black font-medium text-sm px-4 py-2 rounded-md hover:brightness-110">
          + New publication
        </button>
      </div>
      <p className="text-xs text-studio-faint">
        Every publish request carries an idempotency key — retrying a request never creates a duplicate upload.
      </p>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading publications…</div>}

      {!loading && pubs.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">No publications yet</p>
          <p className="text-sm text-studio-muted mt-1">Create a publication job from a rendered project asset.</p>
        </div>
      )}

      <div className="space-y-2">
        {pubs.map((p) => (
          <div key={p.id} className="bg-studio-panel border border-studio-border rounded-lg p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-studio-text font-medium truncate">{p.title}</div>
                <div className="text-xs text-studio-faint mt-0.5">
                  {p.visibility} · attempts {p.attempt_count}
                  {p.youtube_video_id ? ` · youtube: ${p.youtube_video_id}` : ""}
                  {p.scheduled_at ? ` · scheduled ${fmtDate(p.scheduled_at)}` : ""}
                  {p.published_at ? ` · published ${fmtDate(p.published_at)}` : ""}
                </div>
                {p.last_error && <div className="text-xs text-red-400 mt-1">{p.last_error}</div>}
              </div>
              <StatusBadge status={p.status} />
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {(["validate", "approve", "schedule", "cancel"] as const).map((a) => (
                <button
                  key={a}
                  disabled={acting === p.id + a}
                  onClick={() => action(p.id, a)}
                  className="text-xs px-3 py-1.5 rounded-md border border-studio-border text-studio-text hover:border-accent/60 disabled:opacity-50"
                >
                  {a[0].toUpperCase() + a.slice(1)}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {showNew && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowNew(false)} />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-studio-panel border border-studio-border rounded-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="font-semibold text-studio-text mb-4">New publication</h2>
            <div className="space-y-3 text-sm">
              <Field label="Project">
                <select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className={inputCls}>
                  <option value="">—</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                </select>
              </Field>
              <Field label="Channel">
                <select value={form.channel_id} onChange={(e) => setForm({ ...form, channel_id: e.target.value })} className={inputCls}>
                  <option value="">—</option>
                  {channels.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              </Field>
              <Field label="Title">
                <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={inputCls} />
              </Field>
              <Field label="Description">
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} className={inputCls} />
              </Field>
              <Field label="Tags (comma-separated)">
                <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} className={inputCls} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Visibility">
                  <select value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value })} className={inputCls}>
                    <option value="private">Private</option>
                    <option value="unlisted">Unlisted</option>
                    <option value="public">Public</option>
                  </select>
                </Field>
                <Field label="Schedule for (optional)">
                  <input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} className={inputCls} />
                </Field>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setShowNew(false)} className="text-sm px-4 py-2 rounded-md border border-studio-border text-studio-text">Cancel</button>
              <button onClick={create} disabled={!form.title.trim() || acting === "create"}
                className="text-sm bg-accent text-black font-medium px-4 py-2 rounded-md disabled:opacity-50">
                {acting === "create" ? "Creating…" : "Create (draft)"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const inputCls = "mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-studio-muted text-xs">{label}</span>
      {children}
    </label>
  );
}
