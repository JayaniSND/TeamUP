import { Activity, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentActivityState } from "@/lib/agents/agentActivityStore";
import { AGENT_BY_ID } from "@/lib/agents/backendAgentRegistry";

const STATUS_META = {
  idle: { label: "Idle", dot: "bg-text-dim", text: "text-text-muted" },
  in_progress: { label: "Working", dot: "bg-negative", text: "text-negative" },
  completed: { label: "Completed", dot: "bg-positive", text: "text-positive" },
  error: { label: "Attention", dot: "bg-negative", text: "text-negative" },
} as const;

/**
 * Plain-text status box above the network. Narrates the current step in words so
 * the flow is legible even without the graphic (and under reduced-motion). The
 * footer copy is honest about the source: a real backend hand-off trace vs an
 * inferred best-effort view.
 */
export function AgentActivityStatus({ activity }: { activity: AgentActivityState }) {
  const meta = STATUS_META[activity.status];
  const activeNode = activity.activeAgent ? AGENT_BY_ID[activity.activeAgent] : null;
  const ActiveIcon = activeNode?.icon;
  const pulse = activity.status === "in_progress";

  const sourceNote =
    activity.source === "trace"
      ? "Backend runtime trace — only the agents and system steps that actually ran."
      : activity.source === "idle"
        ? "Waiting for the next backend runtime trace."
        : "Inferred from your message — emergency fallback only, not a backend trace.";

  return (
    <div className="glass-inset rounded-2xl p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          <Activity className="size-3.5 text-accent" strokeWidth={2} />
          Live Agent Activity
        </div>
        <span className={cn("inline-flex items-center gap-1 text-[10px] font-semibold", meta.text)}>
          <span className={cn("size-1.5 rounded-full", meta.dot, pulse && "animate-pulse")} />
          {meta.label}
        </span>
      </div>

      <div className="mt-2.5 text-sm font-medium leading-snug text-text">{activity.activeStep}</div>

      {(activeNode || activity.currentFlow) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {activeNode && ActiveIcon && (
            <span className="glass-chip inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-semibold text-text">
              <ActiveIcon className={cn("size-3", meta.text)} strokeWidth={2} aria-hidden />
              {activeNode.label}
            </span>
          )}
          {activity.currentFlow && (
            <span className="text-[11px] text-text-dim">{activity.currentFlow}</span>
          )}
        </div>
      )}

      <div className="mt-2.5 flex items-start gap-1 text-[10px] leading-snug text-text-dim">
        <Info className="mt-px size-3 shrink-0" strokeWidth={2} aria-hidden />
        <span>{sourceNote}</span>
      </div>
    </div>
  );
}
