import { memo } from "react";
import { nodeStatusFor, type AgentActivityState } from "@/lib/agents/agentActivityStore";
import { getAgentFormationPositions, type Vec3 } from "@/lib/agents/agentFormationLayout";
import { AgentNode } from "./AgentNode";
import { AgentConnectionLine } from "./AgentConnectionLine";

// Project normalized formation coords (radius ~1, +y up) into the 0..100 SVG
// arena. Scale leaves margin for the node radius so nothing clips at the edge.
const CENTER = 50;
const SCALE = 27;
const project = (p: Vec3) => ({ x: CENTER + p[0] * SCALE, y: CENTER - p[1] * SCALE });
const radiusFor = (count: number) => Math.max(0.62, 0.92 - Math.max(0, count - 3) * 0.055);

/**
 * Dynamic agent network (SVG/HTML fallback). Renders ONLY the agents in the
 * current activity state, arranged by the shared formation layout, with
 * connection lines for the agents actually communicating. Used under
 * reduced-motion and as the Suspense/error fallback for the 3D renderer, so its
 * data model matches `AgentNetwork3D` exactly.
 */
export const AgentNetwork = memo(function AgentNetwork({
  activity,
}: {
  activity: AgentActivityState;
}) {
  const { agents, connections } = activity;
  const positions = getAgentFormationPositions(agents, { radius: radiusFor(agents.length) });
  const pt = (id: string) => {
    const p = positions[id];
    return p ? project(p) : null;
  };

  if (agents.length === 0) {
    return (
      <div className="grid aspect-square w-full max-w-[320px] place-items-center">
        <span className="text-[11px] font-medium text-text-dim">Waiting for your request</span>
      </div>
    );
  }

  return (
    <div className="relative mx-auto aspect-square w-full max-w-[320px]">
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full overflow-visible" aria-hidden>
        {connections.map((c) => {
          const a = pt(c.from);
          const b = pt(c.to);
          if (!a || !b) return null;
          return (
            <AgentConnectionLine
              key={`${c.from}-${c.to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              status={c.status}
            />
          );
        })}
      </svg>

      {agents.map((id) => {
        const p = pt(id);
        if (!p) return null;
        return (
          <AgentNode
            key={id}
            id={id}
            status={nodeStatusFor(id, activity)}
            xPct={p.x}
            yPct={p.y}
            center={id === "orchestrator"}
          />
        );
      })}
    </div>
  );
});
