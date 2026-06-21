import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { Group, Mesh } from "three";
import { AGENT_BY_ID, type AgentId } from "@/lib/agents/backendAgentRegistry";
import type { AgentActivityStatus } from "@/lib/agents/agentActivityStore";

// Status → accent, on the live palette. "Red" is the brand's muted rose so the
// scene stays premium rather than neon.
const ROSE = "#c2607a"; // communicating / in progress
const GREEN = "#2fa084"; // completed
const ACCENT = "#1f8e76"; // orchestrator idle emphasis
const DIM = "#9fb7ad"; // idle
const PLANNED = "#7ea6c4"; // predicted / queued (soft slate-blue, distinct from active/done)

function accentFor(status: AgentActivityStatus, center: boolean): string {
  if (status === "in_progress" || status === "error") return ROSE;
  if (status === "completed") return GREEN;
  if (status === "planned") return PLANNED;
  return center ? ACCENT : DIM;
}

/**
 * One glassy 3D agent sphere. Floats gently (sine drift), pulses softly while
 * active, and carries a soft additive glow only when active/completed. The label
 * is a constant-size HTML overlay so it stays crisp and uses the site font.
 * All per-frame work is gated by `paused` (offscreen / hidden / reduced-motion).
 */
export function FloatingAgentNode({
  id,
  position,
  status,
  active,
  center = false,
  paused = false,
  phase = 0,
}: {
  id: AgentId;
  position: [number, number, number];
  status: AgentActivityStatus;
  active: boolean;
  center?: boolean;
  paused?: boolean;
  phase?: number;
}) {
  const group = useRef<Group>(null);
  const core = useRef<Mesh>(null);

  useFrame((state) => {
    if (paused || !group.current) return;
    const t = state.clock.elapsedTime;
    group.current.position.x = position[0] + Math.cos(t * 0.5 + phase) * 0.018;
    group.current.position.y = position[1] + Math.sin(t * 0.8 + phase) * 0.03;
    group.current.position.z = position[2] + Math.sin(t * 0.6 + phase) * 0.02;
    if (core.current) {
      // active node pulses strongly; a queued ("planned") node breathes gently so
      // the whole predicted network looks alive while the request is in flight.
      const s = active
        ? 1 + Math.sin(t * 3) * 0.05
        : status === "planned"
          ? 1 + Math.sin(t * 2 + phase) * 0.03
          : 1;
      core.current.scale.setScalar(s);
    }
  });

  const color = accentFor(status, center);
  const radius = center ? 0.42 : 0.36;
  const emissiveIntensity = active
    ? 1.05
    : status === "completed"
      ? 0.64
      : status === "planned"
        ? 0.36
        : status === "idle"
          ? 0.2
          : 0.52;
  const showGlow = active || status === "completed" || status === "error" || status === "planned";
  const dimIdle = status === "idle" && !center;

  return (
    <group ref={group} position={position}>
      {showGlow && (
        <mesh scale={1.9}>
          <sphereGeometry args={[radius, 20, 20]} />
          <meshBasicMaterial color={color} transparent opacity={active ? 0.24 : 0.13} depthWrite={false} />
        </mesh>
      )}

      <mesh scale={1.08}>
        <sphereGeometry args={[radius, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={emissiveIntensity * 0.42}
          metalness={0.1}
          roughness={0.18}
          transparent
          opacity={dimIdle ? 0.52 : 0.82}
        />
      </mesh>

      <mesh ref={core}>
        <sphereGeometry args={[radius * 0.54, 28, 28]} />
        <meshStandardMaterial
          color="#ffffff"
          emissive={color}
          emissiveIntensity={emissiveIntensity}
          metalness={0.12}
          roughness={0.22}
          transparent
          opacity={dimIdle ? 0.66 : 0.96}
        />
      </mesh>

      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius * 1.18, radius * 0.035, 10, 48]} />
        <meshBasicMaterial color={color} transparent opacity={dimIdle ? 0.38 : 0.78} />
      </mesh>

      <Html
        center
        position={[0, -(radius + 0.3), 0]}
        zIndexRange={[10, 0]}
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        <div
          className="max-w-[82px] truncate whitespace-nowrap rounded-full bg-white/75 px-1.5 py-0.5 text-[8px] font-semibold tracking-tight shadow-[0_4px_14px_rgba(31,100,78,0.10)] ring-1 ring-line/70 backdrop-blur"
          title={AGENT_BY_ID[id].label}
          style={{
            color: dimIdle ? "rgba(60,86,77,0.55)" : "#17332b",
            opacity: dimIdle ? 0.8 : 1,
          }}
        >
          {AGENT_BY_ID[id].shortLabel}
        </div>
      </Html>
    </group>
  );
}
