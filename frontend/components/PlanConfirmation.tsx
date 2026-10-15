"use client";

import type { Plan } from "../lib/types";
import { fmtUsd } from "../lib/api";

// Safety: a generated plan is a draft only. It becomes durable and
// executes consequential actions ONLY after the operator presses Start,
// which calls POST /projects/{id}/workflows. Consequential steps (publish,
// paid spend) keep their approval checkpoints regardless of plan confirmation.

export default function PlanConfirmation({
  plan,
  projectId,
  onStart,
  onDiscard,
  starting,
}: {
  plan: Plan;
  projectId: string;
  onStart: () => void;
  onDiscard: () => void;
  starting: boolean;
}) {
  const stages = [...(plan.stages || [])].sort((a, b) => a.order - b.order);
  return (
    <div className="bg-studio-panel border border-accent/40 rounded-lg p-5 space-y-5">
      <div>
        <div className="text-xs uppercase tracking-wider text-studio-muted">Plan summary</div>
        <p className="mt-1 text-studio-text">
          {plan.scene_count_estimate} estimated scene{plan.scene_count_estimate === 1 ? "" : "s"} ·{" "}
          {plan.estimated_duration.estimate ? "heuristic estimate" : "estimate"} via{" "}
          <span className="font-mono text-xs">{plan.estimated_duration.method}</span>
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Stat label="Expected duration" value={`${plan.estimated_duration.total_minutes} min`} />
        <Stat label="Estimated cost" value={fmtUsd(plan.estimated_cost.amount_usd)} />
        <Stat label="Models" value={plan.models.length ? plan.models.join(", ") : "—"} />
        <Stat label="Project" value={projectId.slice(0, 8) + "…"} />
      </div>

      <div>
        <div className="text-xs uppercase tracking-wider text-studio-muted mb-2">Stages</div>
        <ol className="space-y-1.5">
          {stages.map((s) => (
            <li key={s.order} className="flex items-start gap-3 text-sm bg-studio-panel2 border border-studio-border rounded p-2.5">
              <span className="text-accent font-mono">{String(s.order + 1).padStart(2, "0")}</span>
              <div>
                <div className="text-studio-text font-medium">{s.name.replace(/_/g, " ")}</div>
                <div className="text-studio-faint text-xs mt-0.5">
                  {s.requires_approval ? "approval checkpoint" : "automatic"}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {plan.approvals.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wider text-studio-muted mb-2">Approval checkpoints</div>
          <ul className="space-y-1">
            {plan.approvals.map((c, i) => (
              <li key={i} className="text-sm text-amber-400 flex gap-2">
                <span>⏸</span> {c.replace(/_/g, " ")}
              </li>
            ))}
          </ul>
          <p className="text-xs text-studio-faint mt-2">
            Consequential actions (publishing, paid spend) require confirmation at these checkpoints even after Start.
          </p>
        </div>
      )}

      {plan.estimated_cost.disclaimer && (
        <div className="text-xs text-studio-faint">
          Cost basis: <span className="font-mono">{plan.estimated_cost.method}</span> — {plan.estimated_cost.disclaimer}
        </div>
      )}

      <div className="flex gap-3 pt-1">
        <button
          onClick={onStart}
          disabled={starting}
          className="bg-accent text-black font-medium px-5 py-2 rounded-md hover:brightness-110 disabled:opacity-50"
        >
          {starting ? "Starting…" : "Start production"}
        </button>
        <button
          onClick={onDiscard}
          disabled={starting}
          className="px-5 py-2 rounded-md border border-studio-border text-studio-text hover:border-red-400/60 disabled:opacity-50"
        >
          Discard plan
        </button>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-studio-panel2 border border-studio-border rounded p-2.5">
      <div className="text-[11px] text-studio-faint">{label}</div>
      <div className="text-studio-text font-medium mt-0.5 break-words">{value}</div>
    </div>
  );
}
