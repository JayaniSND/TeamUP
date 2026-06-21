import { Component, type ReactNode } from "react";

let cachedWebGLSupport: boolean | null = null;

/** True when the browser can create a WebGL context (so we can mount the 3D). */
export function supportsWebGL(): boolean {
  if (cachedWebGLSupport !== null) return cachedWebGLSupport;
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl = window.WebGLRenderingContext
      ? ((canvas.getContext("webgl") ||
          canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null)
      : null;
    cachedWebGLSupport = !!gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return cachedWebGLSupport;
  } catch {
    cachedWebGLSupport = false;
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
