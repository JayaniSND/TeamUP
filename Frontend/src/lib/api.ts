/**
 * Thin client for the backend conversion endpoints used by the Upload page.
 *
 * These endpoints do NOT touch any database — they take a file, run it through
 * the existing processing modules (phototext.py / voicetotext.py), and return
 * the extracted/transcribed text as `{ "text": "..." }`.
 *
 * The base URL defaults to the bundled mock backend; override with
 * `VITE_API_BASE` (e.g. in a `.env` file) if the backend runs elsewhere.
 */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** Error carrying the backend's HTTP status so the UI can tailor its message. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function postFile(path: string, file: Blob, filename: string): Promise<string> {
  const form = new FormData();
  form.append("file", file, filename);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  } catch {
    // Network-level failure (backend down, CORS, offline) — fetch rejects.
    throw new ApiError(
      `Could not reach the backend at ${API_BASE}. Is it running? (uvicorn mock_backend:app)`,
      0
    );
  }

  // Both success and error responses are JSON; tolerate a non-JSON body.
  const payload = (await res.json().catch(() => null)) as
    | { text?: string; detail?: unknown; error?: string }
    | null;

  if (!res.ok) {
    const detail =
      (payload && (typeof payload.detail === "string" ? payload.detail : payload.error)) ||
      `Request failed (${res.status})`;
    throw new ApiError(detail, res.status);
  }

  return payload?.text ?? "";
}

/** Upload an image or note file → extracted text (Claude vision OCR). */
export function convertPhoto(file: File): Promise<string> {
  return postFile("/convert/photo", file, file.name || "upload");
}

/** Upload/record audio → transcript (Deepgram). */
export function convertVoice(file: Blob, filename = "recording.webm"): Promise<string> {
  return postFile("/convert/voice", file, filename);
}
