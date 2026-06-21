import { Component, type ReactNode } from "react";

/** True when the browser can create a WebGL context (so we can mount the 3D). */
export function supportsWebGL(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

/**
 * Catches any runtime error from the lazily-loaded 3D scene (chunk load failure,
 * WebGL context loss, etc.) and renders the SVG fallback instead, so the Live
 * Agent panel degrades gracefully and never blanks the page.
 */
export class AgentCanvasBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    if (import.meta.env.DEV) console.warn("[agents] 3D scene failed; using SVG fallback:", error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
