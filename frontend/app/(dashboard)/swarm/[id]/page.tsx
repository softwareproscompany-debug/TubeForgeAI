"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, fmtDate } from "../../../../lib/api";
import type {
  AgentMessage,
  SwarmRun,
} from "../../../../lib/types";
import StatusBadge from "../../../../components/StatusBadge";

const TYPE_STYLES: Record<string, string> = {
  task: "bg-sky-500/15 text-sky-400 border-sky-500/40",
  result: "bg-emerald-500/15 text-emerald-400 border-emerald-500/40",
  question: "bg-amber-500/15 text-amber-400 border-amber-500/40",
  answer: "bg-violet-500/15 text-violet-400 border-violet-500/40",
  revision_request: "bg-red-500/15 text-red-400 border-red-500/40",
};

const STATE_STYLES: Record<string, string> = {
  working: "border-accent bg-accent/15 text-accent",
  done: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  idle: "border-studio-border bg-studio-panel2 text-studio-muted",
};

function TypeBadge({ type }: { type: string }) {
  const cls =
    TYPE_STYLES[type] ?? "bg-studio-panel2 text-studio-muted border-studio-border";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${cls}`}
    >
      {type.replace(/_/g, " ")}
    </span>
  );
}

function agentLabel(m: AgentMessage): string {
  const from = m.from_agent ? m.from_agent.name : "system";
  const to = m.to_agent ? m.to_agent.name : "all agents";
  return `${from} → ${to}`;
}

function ReadableContent({ content }: { content: Record<string, unknown> }) {
  const { stage, output, verdict, feedback, topic, request, attempt, max_attempts } =
    content as {
      stage?: string;
      output?: unknown;
      verdict?: unknown;
      feedback?: string;
      topic?: string;
      request?: string;
      attempt?: number;
      max_attempts?: number;
    };
  return (
    <div className="space-y-2 text-sm break-words min-w-0">
      {stage && (
        <div className="text-xs uppercase tracking-wide text-studio-muted">
          Stage: {stage}
        </div>
      )}
      {topic && <p className="text-studio-text">“{topic}”</p>}
      {request && <p className="text-studio-text">{request}</p>}
      {typeof attempt === "number" && (
        <p className="text-studio-text">
          Revision {attempt}
          {typeof max_attempts === "number" ? ` of ${max_attempts}` : ""}
        </p>
      )}
      {feedback && (
        <p className="text-studio-text">
          <span className="text-studio-muted">Feedback: </span>
          {feedback}
        </p>
      )}
      {verdict !== undefined && (
        <pre className="rounded-lg bg-black/30 border border-studio-border p-3 text-xs text-studio-text overflow-x-auto whitespace-pre-wrap break-words">
          {JSON.stringify(verdict, null, 2)}
        </pre>
      )}
      {output !== undefined && (
        <pre className="rounded-lg bg-black/30 border border-studio-border p-3 text-xs text-studio-text overflow-x-auto whitespace-pre-wrap break-words">
          {typeof output === "string" ? output : JSON.stringify(output, null, 2)}
        </pre>
      )}
    </div>
  );
}

function elapsedLabel(run: SwarmRun, now: number): string {
  const start = new Date(run.started_at).getTime();
  const end = run.completed_at ? new Date(run.completed_at).getTime() : now;
  const secs = Math.max(0, Math.floor((end - start) / 1000));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}m ${s}s`;
}

export default function SwarmRunPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [run, setRun] = useState<SwarmRun | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [cancelling, setCancelling] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, msgs] = await Promise.all([
        api.get<SwarmRun>(`/swarm/runs/${id}`),
        api.get<AgentMessage[]>(`/swarm/runs/${id}/messages`),
      ]);
      setRun(r);
      setMessages(msgs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Tick the elapsed-time clock every second.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Poll every 5s while the run is still going.
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (run && run.status === "running") {
      pollRef.current = setInterval(load, 5000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [run?.status, load]);

  async function cancelRun() {
    setCancelling(true);
    try {
      const updated = await api.post<SwarmRun>(`/swarm/runs/${id}/cancel`);
      setRun(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to cancel");
    } finally {
      setCancelling(false);
    }
  }

  if (error && !run) {
    return (
      <div className="p-4 sm:p-8">
        <div className="rounded border border-red-500/40 bg-red-500/10 text-red-400 px-4 py-3 text-sm">
          {error}
        </div>
        <Link href="/swarm" className="text-accent text-sm mt-4 inline-block">
          ← Back to swarm
        </Link>
      </div>
    );
  }
  if (!run) {
    return <div className="p-4 sm:p-8 text-studio-muted">Loading run…</div>;
  }

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto space-y-6 min-w-0">
      <Link href="/swarm" className="text-accent text-sm">
        ← Back to swarm
      </Link>

      {/* Status header */}
      <div className="rounded-xl border border-studio-border bg-studio-panel p-4 sm:p-6 min-w-0">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold text-studio-text">{run.topic}</h1>
            <p className="text-studio-muted text-sm mt-1">
              {run.project_title} · started {fmtDate(run.started_at)}
            </p>
          </div>
          <StatusBadge
            status={
              run.status === "cancelled" ? "CANCELED" : run.status.toUpperCase()
            }
          />
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mt-4 text-sm">
          <div>
            <span className="text-studio-muted">Stage: </span>
            <span className="text-studio-text font-medium capitalize">
              {run.current_stage.replace(/_/g, " ")}
            </span>
          </div>
          <div>
            <span className="text-studio-muted">Elapsed: </span>
            <span className="text-studio-text font-medium">
              {elapsedLabel(run, now)}
            </span>
          </div>
          {run.status === "running" && (
            <button
              onClick={cancelRun}
              disabled={cancelling}
              className="ml-auto min-h-[44px] rounded-lg border border-red-500/40 text-red-400 px-4 py-1.5 text-sm disabled:opacity-50 touch-manipulation"
            >
              {cancelling ? "Cancelling…" : "Cancel run"}
            </button>
          )}
        </div>
        {run.error && (
          <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 text-red-400 px-4 py-3 text-sm">
            {run.error}
          </div>
        )}
      </div>

      {/* Agent status row */}
      <div>
        <h2 className="text-sm font-semibold text-studio-muted uppercase tracking-wide mb-2">
          Agents
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {run.agents.map((a) => (
            <div
              key={a.role}
              className={`rounded-xl border px-3 py-3 text-center ${STATE_STYLES[a.state]}`}
            >
              <div className="font-semibold capitalize text-sm">{a.role}</div>
              <div className="text-xs mt-1 capitalize flex items-center justify-center gap-1.5">
                {a.state === "working" && (
                  <span className="inline-block w-2 h-2 rounded-full bg-accent animate-pulse" />
                )}
                {a.state}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Agent activity feed */}
      <div>
        <h2 className="text-sm font-semibold text-studio-muted uppercase tracking-wide mb-2">
          Agent activity
        </h2>
        {messages.length === 0 ? (
          <p className="text-studio-muted text-sm">No messages yet.</p>
        ) : (
          <div className="space-y-3">
            {messages.map((m) => (
              <div
                key={m.id}
                className="rounded-xl border border-studio-border bg-studio-panel p-3 sm:p-4 min-w-0 w-full"
              >
                <div className="flex items-center gap-2 flex-wrap mb-2 min-w-0">
                  <span className="w-7 h-7 shrink-0 rounded-full bg-accent/15 border border-accent/40 flex items-center justify-center text-accent text-xs font-bold">
                    {(m.from_agent ? m.from_agent.name : "S").charAt(0).toUpperCase()}
                  </span>
                  <span className="text-sm text-studio-text font-medium break-words min-w-0">
                    {agentLabel(m)}
                  </span>
                  <TypeBadge type={m.message_type} />
                  <span className="ml-auto text-xs text-studio-muted">
                    {fmtDate(m.created_at)}
                  </span>
                </div>
                <div className="pl-0 sm:pl-9 min-w-0">
                  <ReadableContent content={m.content} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
