"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, asList } from "../lib/api";
import type { Channel, WorkflowRun } from "../lib/types";
import ResourceMeters from "./ResourceMeters";

const ACTIVE_WORKFLOW_STATUSES = [
  "PLANNING","QUEUED","RESEARCHING","SCRIPTING","STORYBOARDING",
  "GENERATING_ASSETS","GENERATING_NARRATION","ASSEMBLING","RENDERING",
  "VALIDATING","UPLOADING",
];

export default function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [activeJobs, setActiveJobs] = useState<number | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const ch = asList(await api.get<Channel[]>("/channels"));
        if (!alive) return;
        setChannels(ch);
        if (ch.length > 0) setSelected(ch[0].id);
      } catch {
        /* topbar degrades silently; pages show errors */
      }
      try {
        const runs = asList(await api.get<WorkflowRun[]>("/workflows"));
        if (!alive) return;
        setActiveJobs(runs.filter((r) => ACTIVE_WORKFLOW_STATUSES.includes(r.status)).length);
      } catch {
        if (alive) setActiveJobs(null);
      }
    })();
    return () => { alive = false; };
  }, []);

  return (
    <header className="sticky top-0 z-20 h-16 bg-studio-panel/95 backdrop-blur border-b border-studio-border flex items-center gap-2 md:gap-4 px-4 md:px-6 min-w-0">
      {/* Mobile hamburger opens the sidebar drawer */}
      <button
        onClick={onMenuClick}
        aria-label="Open navigation"
        className="md:hidden shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center text-studio-text hover:text-accent"
      >
        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
        </svg>
      </button>

      <div className="font-medium text-studio-text truncate min-w-0 shrink hidden sm:block">
        Production Workspace
      </div>

      <select
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        className="shrink min-w-0 max-w-[7rem] md:max-w-xs truncate bg-studio-panel2 border border-studio-border rounded-md text-sm text-studio-text px-2 md:px-3 py-1.5 min-h-[44px] md:min-h-0"
        aria-label="Channel selector"
      >
        {channels.length === 0 && <option value="">No channels</option>}
        {channels.map((c) => (
          <option key={c.id} value={c.id}>{c.title}</option>
        ))}
      </select>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search projects, videos, assets…"
        className="hidden md:block flex-1 max-w-md bg-studio-bg border border-studio-border rounded-md text-sm px-3 py-1.5 text-studio-text placeholder:text-studio-faint focus:border-accent/60 outline-none"
      />

      {/* Full text button on sm+, icon-only button on xs */}
      <Link
        href="/command-center"
        className="hidden sm:inline-flex items-center text-sm bg-accent text-black font-medium px-4 py-1.5 rounded-md hover:brightness-110 shrink-0 min-h-[44px] md:min-h-0"
      >
        + Quick create
      </Link>
      <Link
        href="/command-center"
        aria-label="Quick create"
        className="sm:hidden inline-flex items-center justify-center shrink-0 min-h-[44px] min-w-[44px] text-xl bg-accent text-black font-medium rounded-md hover:brightness-110"
      >
        +
      </Link>

      <div className="flex items-center gap-1.5 text-sm text-studio-muted shrink-0 min-w-0" title="Active workflow runs">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        <span className="hidden sm:inline truncate">
          {activeJobs === null ? "—" : `${activeJobs} active jobs`}
        </span>
      </div>

      {/* ResourceMeters (compact) is already hidden below xl internally */}
      <ResourceMeters compact />

      <button
        className="relative shrink-0 min-h-[44px] min-w-[44px] md:min-h-0 md:min-w-0 flex items-center justify-center text-studio-muted hover:text-studio-text"
        aria-label="Notifications"
      >
        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8M10 21a2 2 0 004 0" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <div className="shrink-0 w-8 h-8 rounded-full bg-studio-panel2 border border-studio-border flex items-center justify-center text-sm text-studio-muted">
        ⌾
      </div>
    </header>
  );
}
