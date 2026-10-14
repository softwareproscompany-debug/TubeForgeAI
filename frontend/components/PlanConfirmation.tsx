"use client";

import type { Plan } from "../lib/types";
import { fmtUsd } from "../lib/api";

// Safety: a generated plan is a draft only. It becomes durable and
// executes consequential actions ONLY after the operator presses Start,
// which calls POST /workflows. Consequential steps (publish, paid spend)
// keep their approval checkpoints regardless of plan confirmation.

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
  return (
    <div className="bg-studio-panel border border-accent/40 rounded-lg p-5 space-y-5">
      <div>
        <div className="text-xs uppercase tracking-wider text-studio-muted">Interpreted goal</div>
        <p className="mt-1 text-studio-text">{plan.interpreted_goal}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Stat label="Expected duration" value={`${Math.round(plan.expected_duration_s)}s`} />
        <Stat label="Estimated cost" value={fmtUsd(plan.estimated_cost_usd)} />
        <Stat label="Models" value={plan.models.length ? plan.models.join(", ") : "—"} />
        <Stat label="Project" value={projectId.slice(0, 8) + "…"} />
      </div>

      <div>
        <div className="text-xs uppercase tracking-wider text-studio-muted mb-2">Stages</div>
        <ol className="space-y-1.5">
          {plan.stages.map((s, i) => (
            <li key={i} className="flex items-start gap-3 text-sm bg-studio-panel2 border border-studio-border rounded p-2.5">
              <span className="text-accent font-mono">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <div className="text-studio-text font-medium">{s.stage}</div>
                <div className="text-studio-muted text-xs">{s.description}</div>
                <div className="text-studio-faint text-xs mt-0.5">
                  {s.model ? `model: ${s.model}` : ""}
                  {s.estimated_duration_s ? ` · ${Math.round(s.estimated_duration_s)}s` : ""}
                  {s.estimated_cost_usd ? ` · ${fmtUsd(s.estimated_cost_usd)}` : ""}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {plan.approval_checkpoints.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wider text-studio-muted mb-2">Approval checkpoints</div>
          <ul className="space-y-1">
            {plan.approval_checkpoints.map((c, i) => (
              <li key={i} className="text-sm text-amber-400 flex gap-2">
                <span>⏸</span> {c}
              </li>
            ))}
          </ul>
          <p className="text-xs text-studio-faint mt-2">
            Consequential actions (publishing, paid spend) require confirmation at these checkpoints even after Start.
          </p>
        </div>
      )}

      {Object.keys(plan.resource_requirements).length > 0 && (
        <div className="text-xs text-studio-faint">
          Resources: {Object.entries(plan.resource_requirements).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}
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
