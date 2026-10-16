"use client";

import { useEffect, useState } from "react";
import { api, asList } from "../../../lib/api";
import type { AutomationRule, Channel } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

export default function AutomationPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [channelId, setChannelId] = useState("");
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<AutomationRule | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", trigger_type: "", conditions: "{}", actions: "{}", enabled: true });
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const ch = asList(await api.get<Channel[]>("/channels").catch(() => [] as Channel[]));
      setChannels(ch);
      if (ch.length > 0) setChannelId(ch[0].id);
      setLoading(false);
    })();
  }, []);

  const loadRules = async (cid: string) => {
    if (!cid) return;
    try {
      setRules(asList(await api.get<AutomationRule[]>(`/channels/${cid}/automation-rules`)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load rules.");
    }
  };

  useEffect(() => { loadRules(channelId); }, [channelId]);

  const openNew = () => {
    setEditing(null);
    setForm({ name: "", trigger_type: "", conditions: "{}", actions: "{}", enabled: true });
    setFormError(null);
    setShowForm(true);
  };

  const openEdit = (r: AutomationRule) => {
    setEditing(r);
    setForm({
      name: r.name,
      trigger_type: r.trigger_type,
      conditions: JSON.stringify(r.conditions || {}, null, 2),
      actions: JSON.stringify(r.actions || {}, null, 2),
      enabled: r.enabled,
    });
    setFormError(null);
    setShowForm(true);
  };

  const save = async () => {
    setFormError(null);
    let conditions: Record<string, unknown>, actions: Record<string, unknown>;
    try {
      conditions = JSON.parse(form.conditions);
      actions = JSON.parse(form.actions);
    } catch {
      setFormError("Conditions and actions must be valid JSON.");
      return;
    }
    try {
      if (editing) {
        await api.patch(`/channels/${channelId}/automation-rules/${editing.id}`, {
          name: form.name, trigger_type: form.trigger_type, conditions, actions, enabled: form.enabled,
        });
      } else {
        await api.post(`/channels/${channelId}/automation-rules`, {
          name: form.name, trigger_type: form.trigger_type, conditions, actions, enabled: form.enabled,
        });
      }
      setShowForm(false);
      await loadRules(channelId);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Save failed.");
    }
  };

  const toggle = async (r: AutomationRule) => {
    try {
      await api.patch(`/channels/${channelId}/automation-rules/${r.id}`, { enabled: !r.enabled });
      await loadRules(channelId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed.");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-studio-text">Automation Workflows</h1>
        <div className="flex flex-wrap gap-3 items-center">
          <select value={channelId} onChange={(e) => setChannelId(e.target.value)}
            className="bg-studio-panel2 border border-studio-border rounded-md px-3 py-2 min-h-[44px] text-sm text-studio-text">
            {channels.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
          <button onClick={openNew} disabled={!channelId}
            className="bg-accent text-black font-medium text-sm px-4 py-2 min-h-[44px] rounded-md hover:brightness-110 disabled:opacity-50">
            + New rule
          </button>
        </div>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading…</div>}

      {!loading && !channelId && (
        <p className="text-sm text-studio-faint">Connect a channel first to manage its automation rules.</p>
      )}

      <div className="space-y-3">
        {channelId && rules.length === 0 && (
          <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
            <p className="text-studio-text font-medium">No automation rules</p>
            <p className="text-sm text-studio-muted mt-1">Create a rule: when a trigger fires and conditions match, the actions run automatically.</p>
          </div>
        )}
        {rules.map((r) => (
          <div key={r.id} className="bg-studio-panel border border-studio-border rounded-lg p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-studio-text font-medium">{r.name}</div>
                <div className="text-xs text-studio-faint mt-0.5">trigger: <span className="font-mono break-all">{r.trigger_type}</span></div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={r.enabled ? "HEALTHY" : "PAUSED"} />
                <button onClick={() => openEdit(r)} className="text-xs text-accent hover:underline min-h-[44px] inline-flex items-center">Edit</button>
                <button onClick={() => toggle(r)} className="text-xs text-studio-muted hover:text-studio-text min-h-[44px] inline-flex items-center">
                  {r.enabled ? "Disable" : "Enable"}
                </button>
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-2 mt-3">
              <div>
                <div className="text-[11px] text-studio-faint mb-1">Conditions</div>
                <pre className="bg-studio-bg border border-studio-border rounded p-2 text-xs text-studio-text overflow-x-auto">{JSON.stringify(r.conditions || {}, null, 2)}</pre>
              </div>
              <div>
                <div className="text-[11px] text-studio-faint mb-1">Actions</div>
                <pre className="bg-studio-bg border border-studio-border rounded p-2 text-xs text-studio-text overflow-x-auto">{JSON.stringify(r.actions || {}, null, 2)}</pre>
              </div>
            </div>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="fixed inset-0 z-40 p-4">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[calc(100vw-2rem)] sm:max-w-lg max-h-[90vh] overflow-y-auto bg-studio-panel border border-studio-border rounded-lg p-6">
            <h2 className="font-semibold text-studio-text mb-4">{editing ? "Edit rule" : "New automation rule"}</h2>
            <div className="space-y-3 text-sm">
              <label className="block">
                <span className="text-studio-muted text-xs">Name</span>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={cls} />
              </label>
              <label className="block">
                <span className="text-studio-muted text-xs">Trigger</span>
                <input value={form.trigger_type} onChange={(e) => setForm({ ...form, trigger_type: e.target.value })}
                  placeholder="e.g. video_published, schedule_tick" className={cls} />
              </label>
              <label className="block">
                <span className="text-studio-muted text-xs">Conditions (JSON)</span>
                <textarea value={form.conditions} onChange={(e) => setForm({ ...form, conditions: e.target.value })}
                  rows={4} spellCheck={false} className={`${cls} font-mono text-xs`} />
              </label>
              <label className="block">
                <span className="text-studio-muted text-xs">Actions (JSON)</span>
                <textarea value={form.actions} onChange={(e) => setForm({ ...form, actions: e.target.value })}
                  rows={4} spellCheck={false} className={`${cls} font-mono text-xs`} />
              </label>
              <label className="flex items-center gap-2 text-sm text-studio-text">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                Enabled
              </label>
            </div>
            {formError && <div className="text-sm text-red-400 mt-3">{formError}</div>}
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setShowForm(false)} className="text-sm px-4 py-2 min-h-[44px] rounded-md border border-studio-border text-studio-text">Cancel</button>
              <button onClick={save} disabled={!form.name.trim() || !form.trigger_type.trim()}
                className="text-sm bg-accent text-black font-medium px-4 py-2 min-h-[44px] rounded-md disabled:opacity-50">
                Save rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const cls = "mt-1 w-full bg-studio-bg border border-studio-border rounded-md px-3 py-2 text-studio-text placeholder:text-studio-faint";
