/**
 * Dynamic formation layout for the Live Agent network.
 *
 * `getAgentFormationPositions` returns a STABLE normalized 3D position per agent
 * (radius ~1, z is a gentle depth offset). The shape is recalculated from the
 * number of agents actually involved in the current message:
 *
 *   1 agent   → centered
 *   2 agents  → across from each other (clean connecting line)
 *   3 agents  → triangle
 *   4 agents  → diamond / square
 *   5+ agents → orbital ring
 *
 * When the Orchestrator is present it anchors the center and the called agents
 * arrange around it. Positions are keyed by AgentId and ordered by registry
 * index (not arrival), so a node keeps its slot as the set grows/shrinks and the
 * renderers can transition smoothly.
 */
import { agentIndex, ORCHESTRATOR_ID, type AgentId } from "./backendAgentRegistry";

export type Vec3 = [number, number, number];

export interface FormationOptions {
  /** ring radius in normalized units (renderers scale this up). */
  radius?: number;
}

const TOP = Math.PI / 2; // start at the top, go clockwise

/** Gentle, deterministic depth so the ring reads as 3D without churn. */
const depthFor = (i: number, count: number): number =>
  count <= 1 ? 0.16 : 0.13 * Math.sin((i / count) * Math.PI * 2 + 0.6);

export function getAgentFormationPositions(
  agents: AgentId[],
  options: FormationOptions = {}
): Record<string, Vec3> {
  const radius = options.radius ?? 1;
  const positions: Record<string, Vec3> = {};

  // Stable order: registry index. Orchestrator (if present) is pulled to center.
  const ordered = [...agents].sort((a, b) => agentIndex(a) - agentIndex(b));
  const hasOrchestrator = ordered.includes(ORCHESTRATOR_ID);
  const others = ordered.filter((id) => id !== ORCHESTRATOR_ID);
  const n = others.length;

  if (hasOrchestrator) {
    positions[ORCHESTRATOR_ID] = [0, 0, 0.18];
  }

  if (n === 0) {
    // Orchestrator only (or nothing) — already centered above.
    return positions;
  }

  if (!hasOrchestrator && n === 1) {
    positions[others[0]] = [0, 0, 0.16];
    return positions;
  }

  // Orchestrator + one specialist → place it cleanly to the right for a level line.
  if (hasOrchestrator && n === 1) {
    positions[others[0]] = [radius, 0, 0.06];
    return positions;
  }

  // Two specialists with no orchestrator → across from each other.
  if (!hasOrchestrator && n === 2) {
    positions[others[0]] = [-radius, 0, 0.08];
    positions[others[1]] = [radius, 0, -0.08];
    return positions;
  }

  // 3 → triangle, 4 → diamond, 5+ → orbital ring. Evenly spaced on a circle.
  others.forEach((id, i) => {
    const angle = TOP - (i * 2 * Math.PI) / n;
    positions[id] = [Math.cos(angle) * radius, Math.sin(angle) * radius, depthFor(i, n)];
  });

  return positions;
}
