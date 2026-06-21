import { memo } from "react";
import type { AgentActivityStatus } from "@/lib/agents/agentActivityStore";

/**
 * One agent→agent connection line, drawn inside the parent `<svg>` (viewBox
 * 0 0 100 100). Color is status driven (idle = neutral, in_progress = muted
 * rose, completed = emerald) via `.agent-line[data-status]`. While
 * communicating, an animated dashed overlay creates the "flow" effect.
 */
export const AgentConnectionLine = memo(function AgentConnectionLine({
  x1,
  y1,
  x2,
  y2,
  status,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  status: AgentActivityStatus;
}) {
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        className="agent-line"
        data-status={status}
        strokeWidth={status === "idle" ? 0.55 : 0.75}
      />
      {status === "in_progress" && (
        <line x1={x1} y1={y1} x2={x2} y2={y2} className="agent-line-flow" strokeWidth={0.9} />
      )}
    </g>
  );
});
