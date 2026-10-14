"use client";

import { useEffect, useMemo, useState } from "react";
import { api, asList, fmtDate } from "../../../lib/api";
import type { PublicationJob } from "../../../lib/types";
import StatusBadge from "../../../components/StatusBadge";

export default function CalendarPage() {
  const [pubs, setPubs] = useState<PublicationJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(() => {
    const d = new Date();
    return { year: d.getFullYear(), month: d.getMonth() };
  });
  const [selected, setSelected] = useState<PublicationJob | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setPubs(asList(await api.get<PublicationJob[]>("/publications")));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load publications.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const scheduled = useMemo(
    () => pubs.filter((p) => p.scheduled_at && new Date(p.scheduled_at).getTime() > 0),
    [pubs]
  );

  const cells = useMemo(() => {
    const first = new Date(cursor.year, cursor.month, 1);
    const startDay = first.getDay();
    const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate();
    const arr: (Date | null)[] = [];
    for (let i = 0; i < startDay; i++) arr.push(null);
    for (let d = 1; d <= daysInMonth; d++) arr.push(new Date(cursor.year, cursor.month, d));
    return arr;
  }, [cursor]);

  const byDay = (day: Date) =>
    scheduled.filter((p) => {
      const s = new Date(p.scheduled_at!);
      return s.getFullYear() === day.getFullYear() && s.getMonth() === day.getMonth() && s.getDate() === day.getDate();
    });

  const monthName = new Date(cursor.year, cursor.month, 1).toLocaleString("en", { month: "long", year: "numeric" });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-studio-text">Content Calendar</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCursor((c) => ({ year: c.month === 0 ? c.year - 1 : c.year, month: (c.month + 11) % 12 }))}
            className="px-3 py-1.5 text-sm border border-studio-border rounded-md text-studio-text hover:border-accent/60"
          >
            ←
          </button>
          <span className="text-sm text-studio-text w-40 text-center">{monthName}</span>
          <button
            onClick={() => setCursor((c) => ({ year: c.month === 11 ? c.year + 1 : c.year, month: (c.month + 1) % 12 }))}
            className="px-3 py-1.5 text-sm border border-studio-border rounded-md text-studio-text hover:border-accent/60"
          >
            →
          </button>
        </div>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300">{error}</div>}
      {loading && <div className="text-studio-muted text-sm">Loading calendar…</div>}

      {!loading && scheduled.length === 0 && !error && (
        <div className="bg-studio-panel border border-studio-border rounded-lg p-8 text-center">
          <p className="text-studio-text font-medium">Nothing scheduled</p>
          <p className="text-sm text-studio-muted mt-1">Schedule a publication from the Publishing page and it will appear here.</p>
        </div>
      )}

      <div className="grid grid-cols-7 gap-px bg-studio-border border border-studio-border rounded-lg overflow-hidden">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="bg-studio-panel2 text-xs text-studio-muted text-center py-2">{d}</div>
        ))}
        {cells.map((day, i) => (
          <div key={i} className="bg-studio-panel min-h-24 p-1.5">
            {day && (
              <>
                <div className="text-xs text-studio-faint">{day.getDate()}</div>
                <div className="space-y-1 mt-1">
                  {byDay(day).map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setSelected(p)}
                      className="block w-full text-left text-[11px] bg-accent/15 border border-accent/40 text-accent rounded px-1.5 py-0.5 truncate hover:bg-accent/25"
                      title={p.title}
                    >
                      {new Date(p.scheduled_at!).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" })} {p.title}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/60" onClick={() => setSelected(null)} />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-studio-panel border border-studio-border rounded-lg p-5">
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-semibold text-studio-text">{selected.title}</h2>
              <button onClick={() => setSelected(null)} className="text-studio-muted hover:text-studio-text text-xl" aria-label="Close">×</button>
            </div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-studio-faint">Scheduled</span><span className="text-studio-text">{fmtDate(selected.scheduled_at)}</span></div>
              <div className="flex justify-between"><span className="text-studio-faint">Visibility</span><span className="text-studio-text">{selected.visibility}</span></div>
              <div className="flex justify-between items-center"><span className="text-studio-faint">Status</span><StatusBadge status={selected.status} /></div>
              <div className="flex justify-between"><span className="text-studio-faint">Attempts</span><span className="text-studio-text">{selected.attempt_count}</span></div>
              {selected.last_error && (
                <div><span className="text-studio-faint">Last error</span><div className="text-red-400 text-xs mt-1">{selected.last_error}</div></div>
              )}
              <a href="/publishing" className="inline-block text-accent text-sm hover:underline mt-2">Manage in Publishing →</a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
