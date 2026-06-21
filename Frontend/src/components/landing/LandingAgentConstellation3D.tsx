import { useRef } from "react";
import { Line } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import type { Group } from "three";

type Vec3 = [number, number, number];

const nodes: { name: string; position: Vec3; color: string; size: number }[] = [
  { name: "Orchestrator", position: [0, 0, 0], color: "#1f9f68", size: 0.2 },
  { name: "Librarian", position: [-1.55, 0.85, -0.2], color: "#6fcf97", size: 0.13 },
  { name: "Recovery", position: [1.45, 0.82, 0.05], color: "#b9861e", size: 0.12 },
  { name: "Performance", position: [1.62, -0.75, -0.1], color: "#2fa084", size: 0.12 },
  { name: "Scout", position: [-1.28, -0.88, 0.1], color: "#4e9a7f", size: 0.12 },
  { name: "Logistics", position: [0.1, 1.55, -0.28], color: "#7ccfac", size: 0.11 },
  { name: "Sponsorship", position: [-0.1, -1.55, 0.18], color: "#55b991", size: 0.11 },
];

const links: [number, number][] = [
  [0, 1],
  [0, 2],
  [0, 3],
  [0, 4],
  [0, 5],
  [0, 6],
  [1, 2],
  [3, 4],
  [5, 6],
];

function AgentConstellation({ paused }: { paused: boolean }) {
  const group = useRef<Group>(null);

  useFrame(({ clock }) => {
    if (paused || !group.current) return;
    const t = clock.getElapsedTime();
    group.current.rotation.y = Math.sin(t * 0.24) * 0.18;
    group.current.rotation.x = Math.cos(t * 0.18) * 0.08;
  });

  return (
    <group ref={group}>
      {links.map(([from, to]) => (
        <Line
          key={`${from}-${to}`}
          points={[nodes[from].position, nodes[to].position]}
          color="#7ccfac"
          lineWidth={1}
          transparent
          opacity={0.34}
        />
      ))}

      {nodes.map((node, index) => (
        <mesh key={node.name} position={node.position}>
          <sphereGeometry args={[node.size, 32, 32]} />
          <meshStandardMaterial
            color={node.color}
            roughness={0.32}
            metalness={0.12}
            transparent
            opacity={index === 0 ? 0.92 : 0.78}
          />
        </mesh>
      ))}
    </group>
  );
}

export default function LandingAgentConstellation3D({ paused = false }: { paused?: boolean }) {
  return (
    <Canvas
      dpr={[1, 1.6]}
      frameloop={paused ? "demand" : "always"}
      camera={{ position: [0, 0, 4.8], fov: 34 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ width: "100%", height: "100%" }}
    >
      <ambientLight intensity={0.88} />
      <directionalLight position={[3, 4, 5]} intensity={0.7} />
      <pointLight position={[-2.4, -1.4, 2.8]} intensity={0.8} color="#6fcf97" />
      <AgentConstellation paused={paused} />
    </Canvas>
  );
}
