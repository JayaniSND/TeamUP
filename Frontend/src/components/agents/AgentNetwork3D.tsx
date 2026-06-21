import { useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import type { PerspectiveCamera } from "three";
import { getAgentFormationPositions } from "@/lib/agents/agentFormationLayout";
import { nodeStatusFor, type AgentActivityState } from "@/lib/agents/agentActivityStore";
import type { AgentId } from "@/lib/agents/backendAgentRegistry";
import { FloatingAgentNode } from "./FloatingAgentNode";
import { AgentConnectionLine3D } from "./AgentConnectionLine3D";

// Normalized formation radius (~1) -> world units. The fit-camera below frames
// whatever this produces, so this only sets RELATIVE node spacing, not on-screen
// size.
const SCALE = 1.55;
type Vec3 = [number, number, number];
const scale = (p: Vec3): Vec3 => [p[0] * SCALE, p[1] * SCALE, p[2] * SCALE];
const radiusFor = (count: number) => Math.max(0.62, 0.92 - Math.max(0, count - 3) * 0.055);

// Node/label footprint (world units) the camera must keep inside the frame.
const NODE_R = 0.34; // largest sphere (orchestrator)
const LABEL_BELOW = 0.6; // HTML label sits below each node
const MARGIN = 0.4; // breathing room so nothing kisses the edge

/**
 * Frame the whole formation to the current canvas size — every message and on
 * every resize. Computes the formation's extent and pushes the perspective camera
 * back just enough that the widest/tallest case fits (accounting for the labels
 * that hang below each node), centered on the content. This is what makes the
 * scene fill the panel without ever clipping at the bottom, for any agent count
 * and any (portrait/landscape) panel aspect.
 */
function FitCamera({ maxRadius }: { maxRadius: number }) {
  const camera = useThree((s) => s.camera);
  const width = useThree((s) => s.size.width);
  const height = useThree((s) => s.size.height);
  const invalidate = useThree((s) => s.invalidate);

  useEffect(() => {
    const cam = camera as PerspectiveCamera;
    if (!cam.isPerspectiveCamera || width === 0 || height === 0) return;

    // Content spans wider than tall once labels hang below, so center on cy.
    const halfW = maxRadius + NODE_R + MARGIN;
    const halfH = maxRadius + NODE_R + LABEL_BELOW / 2 + MARGIN;
    const cy = -LABEL_BELOW / 2;

    const vfov = (cam.fov * Math.PI) / 180;
    const aspect = width / height;
    const distForHeight = halfH / Math.tan(vfov / 2);
    const distForWidth = halfW / (Math.tan(vfov / 2) * aspect);
    const dist = Math.max(distForHeight, distForWidth, 2.8);

    cam.position.set(0, cy, dist);
    cam.lookAt(0, cy, 0);
    cam.updateProjectionMatrix();
    invalidate();
  }, [maxRadius, width, height, camera, invalidate]);

  return null;
}

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
 * lines for the agents actually communicating. An auto-fit camera frames the
 * formation to the panel so it fills the space and never clips. Soft lighting,
 * glassy spheres, gentle floating motion — paused entirely when not visible.
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
  let maxRadius = 0.45;
  for (const id of activity.agents) {
    const p = positions[id];
    if (!p) continue;
    const s = scale(p);
    scaled[id] = s;
    maxRadius = Math.max(maxRadius, Math.hypot(s[0], s[1]));
  }

  return (
    <Canvas
      dpr={[1, 1.8]}
      frameloop={paused ? "demand" : "always"}
      camera={{ position: [0, 0, 6], fov: 32 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ width: "100%", height: "100%" }}
    >
      <FitCamera maxRadius={maxRadius} />
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
