/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API (defaults to the local mock backend). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
