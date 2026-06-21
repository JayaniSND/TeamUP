import { memo } from "react";
import { cn } from "@/lib/utils";
import { AGENT_BY_ID, type AgentId } from "@/lib/agents/backendAgentRegistry";
import type { AgentActivityStatus } from "@/lib/agents/agentActivityStore";

/**
 * One circular "glass sphere" agent node (SVG/HTML fallback renderer). Purely
 * presentational — `data-status` drives the glow/pulse via `.agent-node` rules
 * in index.css. Position is supplied by the parent as a percentage of the square
 * arena, and transitions smoothly as the formation changes between messages.
 */
export const AgentNode = memo(function AgentNode({
  id,
  status,
  xPct,
  yPct,
  center = false,
}: {
  id: AgentId;
  status: AgentActivityStatus;
  xPct: number;
  yPct: number;
  center?: boolean;
}) {
  const meta = AGENT_BY_ID[id];
  const Icon = meta.icon;
  const active = status === "in_progress";
  const done = status === "completed";

  const tone = active
    ? "text-negative"
    : done
      ? "text-positive"
      : center
        ? "text-accent"
        : "text-text-muted";

  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{
        left: `${xPct}%`,
        top: `${yPct}%`,
        transition: "left 0.45s cubic-bezier(0.22,1,0.36,1), top 0.45s cubic-bezier(0.22,1,0.36,1)",
      }}
    >
      <div
        className={cn(
          "agent-node relative grid place-items-center rounded-full text-center",
          center && "agent-node--center"
        )}
        data-status={status}
        style={{
          width: center ? "clamp(54px, 19%, 74px)" : "clamp(42px, 15%, 58px)",
          height: center ? "clamp(54px, 19%, 74px)" : "clamp(42px, 15%, 58px)",
        }}
        role="img"
        aria-label={`${meta.label} — ${status.replace("_", " ")}`}
        title={`${meta.label} · ${meta.source}`}
      >
        <span className="agent-pulse-ring" aria-hidden />
        <span className="flex flex-col items-center gap-0.5 px-1 leading-none">
          <Icon
            className={cn("transition-colors", center ? "size-5" : "size-4", tone)}
            strokeWidth={1.9}
            aria-hidden
          />
          <span
            className={cn(
              "max-w-full truncate font-semibold tracking-tight transition-colors",
              center ? "text-[9px]" : "text-[8px]",
              active || done ? "text-text" : "text-text-dim"
            )}
          >
            {meta.shortLabel}
          </span>
        </span>
      </div>
    </div>
  );
});
