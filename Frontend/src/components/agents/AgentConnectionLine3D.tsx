import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import type { AgentActivityStatus } from "@/lib/agents/agentActivityStore";

const ROSE = "#c2607a";
const GREEN = "#2fa084";
const DIM = "#88a89c";
const PLANNED = "#7ea6c4"; // predicted / queued edge

/**
 * A 3D connection line between two agents. Color is status driven:
 *   in_progress → rose, animated dashes flowing toward the target ("communicating")
 *   completed   → solid green
 *   idle        → faint neutral
 * The dash flow + per-frame work are gated by `paused`.
 */
export function AgentConnectionLine3D({
  from,
  to,
  status,
  paused = false,
}: {
  from: [number, number, number];
  to: [number, number, number];
  status: AgentActivityStatus;
  paused?: boolean;
}) {
  // drei <Line> forwards its ref to a Line2 whose material exposes dashOffset.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ref = useRef<any>(null);

  // Flow the dashes toward the target so an edge reads as live communication.
  // in_progress flows fast (actively talking); planned flows slowly (engaging).
  useFrame((_, delta) => {
    if (paused || (status !== "in_progress" && status !== "planned")) return;
    const mat = ref.current?.material;
    if (mat && typeof mat.dashOffset === "number") {
      mat.dashOffset -= delta * (status === "in_progress" ? 0.9 : 0.4);
    }
  });

  const flowing = status === "in_progress";
  const planned = status === "planned";
  const color =
    flowing || status === "error" ? ROSE : status === "completed" ? GREEN : planned ? PLANNED : DIM;

  return (
    <Line
      ref={ref}
      points={[from, to]}
      color={color}
      lineWidth={status === "idle" ? 1.6 : planned ? 2.2 : 3}
      transparent
      opacity={status === "idle" ? 0.48 : planned ? 0.72 : 0.92}
      // planned shows STATIC dashes (queued); in_progress animates them (flowing).
      dashed={flowing || planned}
      dashScale={6}
      dashSize={0.18}
      gapSize={0.12}
    />
  );
}
