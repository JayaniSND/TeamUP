import { useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { getAgentFormationPositions } from "@/lib/agents/agentFormationLayout";
import { nodeStatusFor, type AgentActivityState } from "@/lib/agents/agentActivityStore";
import type { AgentId } from "@/lib/agents/backendAgentRegistry";
import { FloatingAgentNode } from "./FloatingAgentNode";
import { AgentConnectionLine3D } from "./AgentConnectionLine3D";

// Normalized formation radius (~1) -> compact world units for the right rail.
const SCALE = 1.55;
type Vec3 = [number, number, number];
const scale = (p: Vec3): Vec3 => [p[0] * SCALE, p[1] * SCALE, p[2] * SCALE];
const radiusFor = (count: number) => Math.max(0.62, 0.92 - Math.max(0, count - 3) * 0.055);

/**
 * Renders one frame whenever the activity changes. Needed because the Canvas
 * drops to `frameloop="demand"` while paused (offscreen / reduced-motion), so a
 * new formation would otherwise not paint until motion resumes.
 */
function Invalidate({ dep }: { dep: number }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    invalidate();
  }, [dep, invalidate]);
  return null;
}

/**
 * The 3D Live Agent network (lazy-loaded). Renders ONLY the agents in the
 * current activity, positioned by the shared formation layout, with connection
 * lines for the agents actually communicating. Soft lighting, glassy spheres,
 * gentle floating motion — paused entirely when not visible.
 */
export default function AgentNetwork3D({
  activity,
  paused = false,
}: {
  activity: AgentActivityState;
  paused?: boolean;
}) {
  const positions = getAgentFormationPositions(activity.agents, { radius: radiusFor(activity.agents.length) });
  const scaled: Partial<Record<AgentId, Vec3>> = {};
  for (const id of activity.agents) {
    const p = positions[id];
    if (p) scaled[id] = scale(p);
  }

  return (
    <Canvas
      dpr={[1, 1.8]}
      frameloop={paused ? "demand" : "always"}
      camera={{ position: [0, 0, 6.2], fov: 34 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ width: "100%", height: "100%" }}
    >
      <Invalidate dep={activity.lastUpdated} />
      <ambientLight intensity={0.85} />
      <directionalLight position={[3, 4, 5]} intensity={0.55} />
      <pointLight position={[-4, -2, 3]} intensity={0.5} color="#6fcf97" />

      {activity.connections.map((c) => {
        const a = scaled[c.from];
        const b = scaled[c.to];
        if (!a || !b) return null;
        return (
          <AgentConnectionLine3D key={`${c.from}-${c.to}`} from={a} to={b} status={c.status} paused={paused} />
        );
      })}

      {activity.agents.map((id, i) => {
        const p = scaled[id];
        if (!p) return null;
        return (
          <FloatingAgentNode
            key={id}
            id={id}
            position={p}
            status={nodeStatusFor(id, activity)}
            active={activity.activeAgent === id}
            center={id === "orchestrator"}
            paused={paused}
            phase={i * 1.7}
          />
        );
      })}
    </Canvas>
  );
}
