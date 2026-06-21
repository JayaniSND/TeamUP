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

// ── AI chat → orchestrator ───────────────────────────────────────────────────
//
// The frontend sends EVERY chat message to ONE endpoint and never decides which
// agent answers — routing to specialists (Recovery / Performance / Sponsorship /
// Travel / Librarian) is the backend orchestrator's responsibility.
//
// Backend architecture (verified against Backend/):
//   • POST /orchestrator/chat (main.py → services/orchestrator_service.py) is the
//     orchestrator brain over HTTP. It loads the athlete's real Supabase context,
//     classifies intent (log / ask / action), routes to the matching specialist
//     analysis function, and returns one structured reply.
//       request:  { user_id, message, session_id?, context? }
//       response: { message, intent, agents_used[], athlete_context_summary,
//                   warnings[], suggested_actions[], sources[] }
//   • The canonical Orchestrator uAgent (agents/orchestrator.py) speaks the ASI:One
//     chat protocol for Agentverse; /orchestrator/chat runs the same brain inline
//     so a browser can reach it synchronously.
//   • POST /chat remains as the standalone RAG "ask" path (shared implementation).

/** Athlete the dashboard acts as. Mirrors the backend's DEFAULT_USER_ID. */
export const USER_ID = (import.meta.env.VITE_USER_ID ?? "demo-athlete").trim();

/** Chat endpoint — the orchestrator brain. Override with VITE_CHAT_ENDPOINT. */
const CHAT_ENDPOINT = (import.meta.env.VITE_CHAT_ENDPOINT ?? "/orchestrator/chat").trim();

/** A bookable travel option the orchestrator surfaced (flight/hotel/entry). */
export interface BookingOption {
  kind: string; // 'flight' | 'hotel' | 'tournament_entry'
  title: string;
  location?: string;
  amountCents: number;
  currency: string;
  description?: string;
  startDate?: string;
  startTime?: string;
  endDate?: string;
  endTime?: string;
  provider?: string;
}

export interface BookingRecord extends BookingOption {
  id?: string;
  status?: string;
  provider?: string;
  createdAt?: string;
}

export interface BookingEventPayload {
  id?: string;
  title?: string;
  startDate?: string;
  startTime?: string;
  endDate?: string;
  endTime?: string;
  type?: string;
  bookingType?: string;
  location?: string;
  notes?: string;
  status?: string;
  paymentStatus?: string;
  provider?: string;
}

const _str = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim() ? value : undefined;

const _bookingOption = (o: Record<string, unknown>): BookingOption => ({
  kind: String(o.kind ?? "booking"),
  title: String(o.title ?? "Booking"),
  location: _str(o.location),
  amountCents: Number(o.amount_cents) || 0,
  currency: String(o.currency ?? "usd"),
  description: _str(o.description),
  startDate: _str(o.startDate) ?? _str(o.start_date),
  startTime: _str(o.startTime) ?? _str(o.start_time),
  endDate: _str(o.endDate) ?? _str(o.end_date),
  endTime: _str(o.endTime) ?? _str(o.end_time),
  provider: _str(o.provider),
});

const _bookingRecord = (o: Record<string, unknown>): BookingRecord => ({
  ..._bookingOption({
    kind: o.kind,
    title: o.title,
    location: o.location,
    amount_cents: o.amount_cents,
    currency: o.currency,
    description: typeof o.description === "string" ? o.description : (o.metadata as Record<string, unknown> | undefined)?.description,
    start_date: (o.metadata as Record<string, unknown> | undefined)?.start_date,
    start_time: (o.metadata as Record<string, unknown> | undefined)?.start_time,
    end_date: (o.metadata as Record<string, unknown> | undefined)?.end_date,
    end_time: (o.metadata as Record<string, unknown> | undefined)?.end_time,
    provider: (o.metadata as Record<string, unknown> | undefined)?.provider,
  }),
  id: o.id != null ? String(o.id) : undefined,
  status: o.status != null ? String(o.status) : undefined,
  provider: _str((o.metadata as Record<string, unknown> | undefined)?.provider) ?? _str(o.provider),
  createdAt: o.created_at != null ? String(o.created_at) : undefined,
});

const _bookingEventPayload = (o: Record<string, unknown> | null | undefined): BookingEventPayload | undefined => {
  if (!o) return undefined;
  return {
    id: o.id != null ? String(o.id) : undefined,
    title: o.title != null ? String(o.title) : undefined,
    startDate:
      (typeof o.startDate === "string" && o.startDate) ||
      (typeof o.start_date === "string" && o.start_date) ||
      (typeof o.date === "string" && o.date) ||
      undefined,
    startTime:
      (typeof o.startTime === "string" && o.startTime) ||
      (typeof o.start_time === "string" && o.start_time) ||
      (typeof o.time === "string" && o.time) ||
      undefined,
    endDate:
      (typeof o.endDate === "string" && o.endDate) ||
      (typeof o.end_date === "string" && o.end_date) ||
      undefined,
    endTime:
      (typeof o.endTime === "string" && o.endTime) ||
      (typeof o.end_time === "string" && o.end_time) ||
      undefined,
    type:
      (typeof o.type === "string" && o.type) ||
      (typeof o.kind === "string" && o.kind) ||
      (typeof o.event_type === "string" && o.event_type) ||
      undefined,
    bookingType:
      (typeof o.bookingType === "string" && o.bookingType) ||
      (typeof o.booking_type === "string" && o.booking_type) ||
      (typeof o.kind === "string" && o.kind) ||
      undefined,
    location: typeof o.location === "string" ? o.location : undefined,
    notes:
      (typeof o.notes === "string" && o.notes) ||
      (typeof o.description === "string" && o.description) ||
      undefined,
    status: typeof o.status === "string" ? o.status : undefined,
    paymentStatus:
      (typeof o.paymentStatus === "string" && o.paymentStatus) ||
      (typeof o.payment_status === "string" && o.payment_status) ||
      undefined,
    provider: typeof o.provider === "string" ? o.provider : undefined,
  };
};

/** Normalized orchestrator reply the UI renders. */
export interface ChatReply {
  /** the final assistant message to show. */
  message: string;
  /** log | ask | action | none | error — backend's routing decision. */
  intent: string;
  /** which specialist(s) the orchestrator used (e.g. ["recovery"]). */
  agentsUsed: string[];
  /** one-liner of the real Supabase data the answer was grounded in. */
  contextSummary: string;
  /** non-fatal notices (missing data, booking-not-connected, etc.). */
  warnings: string[];
  /** tappable follow-up prompts the orchestrator suggests. */
  suggestedActions: string[];
  /** backend entry ids the answer was grounded in (may be empty). */
  sources: string[];
  /** bookable travel options (rendered as Book & Pay cards). */
  options: BookingOption[];
}

const _strArray = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x) => x != null).map(String) : [];

/**
 * Send one user message to the orchestrator and return its structured reply.
 *
 * The frontend forwards only the raw message + identity/context — it does NOT
 * choose an agent. If the user asks something needing a specialist, the request
 * still goes to this single endpoint and the backend orchestrator routes it.
 */
export async function sendChatMessage(
  message: string,
  opts: { userId?: string; sessionId?: string; context?: Record<string, unknown>; signal?: AbortSignal } = {}
): Promise<ChatReply> {
  const body = {
    user_id: opts.userId ?? USER_ID,
    message,
    session_id: opts.sessionId,
    context: opts.context ?? {},
  };

  if (import.meta.env.DEV) console.debug("[chat] →", CHAT_ENDPOINT, body);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${CHAT_ENDPOINT}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    // Network-level failure (backend down, CORS, offline) — fetch rejects.
    throw new ApiError(
      `Could not reach the AI service at ${API_BASE}. Is the backend running? (uvicorn main:app --port 8000)`,
      0
    );
  }

  const payload = (await res.json().catch(() => null)) as Record<string, unknown> | null;

  if (!res.ok) {
    const detail = payload?.detail;
    const msg =
      (typeof detail === "string" ? detail : undefined) ??
      (typeof payload?.error === "string" ? payload.error : undefined) ??
      `AI request failed (${res.status})`;
    throw new ApiError(msg, res.status);
  }

  // Prefer the orchestrator shape (`message`); fall back to the /chat shape
  // (`answer`) so the helper still works if pointed at the plain RAG endpoint.
  const text =
    (typeof payload?.message === "string" && payload.message.trim()) ||
    (typeof payload?.answer === "string" && payload.answer.trim()) ||
    "I couldn't find an answer for that yet.";

  const reply: ChatReply = {
    message: text,
    intent: typeof payload?.intent === "string" ? payload.intent : "",
    agentsUsed: _strArray(payload?.agents_used),
    contextSummary: typeof payload?.athlete_context_summary === "string" ? payload.athlete_context_summary : "",
    warnings: _strArray(payload?.warnings),
    suggestedActions: _strArray(payload?.suggested_actions),
    sources: _strArray(payload?.sources),
    options: Array.isArray(payload?.options)
      ? (payload.options as Record<string, unknown>[]).map(_bookingOption)
      : [],
  };

  if (import.meta.env.DEV) {
    console.debug("[chat] ←", {
      intent: reply.intent,
      agents: reply.agentsUsed,
      message: reply.message.slice(0, 80),
      warnings: reply.warnings.length,
      options: reply.options.length,
    });
  }

  return reply;
}

// ── Travel booking → Stripe Checkout (test mode) ─────────────────────────────

export interface CheckoutResult {
  ok: boolean;
  /** false when the backend has no Stripe key yet (show a friendly note). */
  configured?: boolean;
  /** Stripe hosted checkout URL to redirect to when ok. */
  checkoutUrl?: string;
  bookingId?: string;
  sessionId?: string;
  error?: string;
}

/** Open a Stripe test Checkout Session for one option. Redirect to `checkoutUrl`. */
export async function createBookingCheckout(
  option: BookingOption,
  opts: { userId?: string } = {}
): Promise<CheckoutResult> {
  const body = {
    user_id: opts.userId ?? USER_ID,
    option: {
      kind: option.kind,
      title: option.title,
      location: option.location,
      amount_cents: option.amountCents,
      currency: option.currency,
      description: option.description,
      start_date: option.startDate,
      start_time: option.startTime,
      end_date: option.endDate,
      end_time: option.endTime,
      provider: option.provider,
    },
  };

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/bookings/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(`Could not reach the booking service at ${API_BASE}.`, 0);
  }

  const payload = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  if (!res.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : `Checkout failed (${res.status})`;
    throw new ApiError(detail, res.status);
  }
  return {
    ok: Boolean(payload?.ok),
    configured: payload?.configured as boolean | undefined,
    checkoutUrl: typeof payload?.checkout_url === "string" ? payload.checkout_url : undefined,
    bookingId: payload?.booking_id != null ? String(payload.booking_id) : undefined,
    sessionId: typeof payload?.session_id === "string" ? payload.session_id : undefined,
    error: typeof payload?.error === "string" ? payload.error : undefined,
  };
}

export interface ConfirmBookingResult {
  paid: boolean;
  status?: string;
  bookingId?: string;
  booking?: BookingRecord;
  event?: BookingEventPayload;
}

/** Verify a returned Stripe Checkout Session and mark the booking paid. */
export async function confirmBooking(sessionId: string): Promise<ConfirmBookingResult> {
  const res = await fetch(`${API_BASE}/bookings/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  const payload = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  const bookingPayload = payload?.booking && typeof payload.booking === "object" ? payload.booking as Record<string, unknown> : undefined;
  const eventPayload =
    (payload?.calendar_event && typeof payload.calendar_event === "object" ? payload.calendar_event as Record<string, unknown> : undefined) ??
    (payload?.event && typeof payload.event === "object" ? payload.event as Record<string, unknown> : undefined);
  return {
    paid: Boolean(payload?.paid),
    status: typeof payload?.status === "string" ? payload.status : undefined,
    bookingId: payload?.booking_id != null ? String(payload.booking_id) : undefined,
    booking: bookingPayload ? _bookingRecord(bookingPayload) : undefined,
    event: _bookingEventPayload(eventPayload),
  };
}

export async function listBookings(opts: { userId?: string } = {}): Promise<BookingRecord[]> {
  const params = new URLSearchParams({ user_id: opts.userId ?? USER_ID });
  const res = await fetch(`${API_BASE}/bookings?${params.toString()}`);
  const payload = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  const rows = Array.isArray(payload?.bookings) ? payload.bookings as Record<string, unknown>[] : [];
  return rows.map(_bookingRecord);
}
