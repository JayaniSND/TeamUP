/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API (defaults to http://127.0.0.1:8000). */
  readonly VITE_API_BASE?: string;
  /** Chat endpoint path (defaults to /orchestrator/chat). */
  readonly VITE_CHAT_ENDPOINT?: string;
  /** Athlete id the dashboard acts as (defaults to demo-athlete). */
  readonly VITE_USER_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
