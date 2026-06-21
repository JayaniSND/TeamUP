import type { BookingOption, ChatMessage, SharedCalendarEvent } from "@/types/athlete";

export const CHECKOUT_ACTIVE_STORAGE_KEY = "teamup:checkout:active";

const PAYMENT_SESSION_STATE_KEY = "teamup:payment:session-state";
const PAYMENT_HANDLED_SESSIONS_KEY = "teamup:payment:handled-sessions";

export interface PaymentSessionPendingBooking {
  option: BookingOption;
  type?: string;
  title?: string;
  start?: string;
  end?: string;
  location?: string;
  details?: string;
  price?: number;
  currency?: string;
  stripeSessionId?: string;
  bookingId?: string;
}

export interface PaymentSessionState {
  paymentSessionId?: string;
  chatMessages?: ChatMessage[];
  chatSessionId?: string;
  calendarEvents?: SharedCalendarEvent[];
  pendingBooking?: PaymentSessionPendingBooking;
  currentBookingType?: string;
  pendingPaymentSessionId?: string;
  returnRoute?: string;
  sourcePage?: "dashboard" | "chat" | "calendar" | "checkout" | "other";
  pageContext?: string;
  selectedCalendarDate?: string;
  selectedCalendarWeek?: string;
  selectedCalendarMonth?: string;
  savedAt: number;
}

const safeSessionStorage = () => {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
};

const readHandledSessionIds = (): string[] => {
  const storage = safeSessionStorage();
  if (!storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(PAYMENT_HANDLED_SESSIONS_KEY) || "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    storage.removeItem(PAYMENT_HANDLED_SESSIONS_KEY);
    return [];
  }
};

export const isPaymentSessionActive = () =>
  safeSessionStorage()?.getItem(CHECKOUT_ACTIVE_STORAGE_KEY) === "1";

export function restorePaymentSessionState(): PaymentSessionState | null {
  const storage = safeSessionStorage();
  if (!storage) return null;
  const raw = storage.getItem(PAYMENT_SESSION_STATE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<PaymentSessionState>;
    if (!parsed || typeof parsed !== "object") return null;
    return {
      ...parsed,
      savedAt: typeof parsed.savedAt === "number" ? parsed.savedAt : Date.now(),
    };
  } catch {
    storage.removeItem(PAYMENT_SESSION_STATE_KEY);
    return null;
  }
}

export function savePaymentSessionState(state: Partial<PaymentSessionState>) {
  const storage = safeSessionStorage();
  if (!storage) return null;

  const previous = restorePaymentSessionState();
  const pendingBooking =
    state.pendingBooking || previous?.pendingBooking
      ? ({
          ...previous?.pendingBooking,
          ...state.pendingBooking,
        } as PaymentSessionPendingBooking)
      : undefined;
  const next: PaymentSessionState = {
    ...previous,
    ...state,
    pendingBooking,
    savedAt: Date.now(),
  };

  storage.setItem(PAYMENT_SESSION_STATE_KEY, JSON.stringify(next));
  storage.setItem(CHECKOUT_ACTIVE_STORAGE_KEY, "1");
  return next;
}

export function clearPaymentSessionState(options: { clearHandled?: boolean } = {}) {
  const storage = safeSessionStorage();
  if (!storage) return;
  storage.removeItem(PAYMENT_SESSION_STATE_KEY);
  storage.removeItem(CHECKOUT_ACTIVE_STORAGE_KEY);
  if (options.clearHandled) storage.removeItem(PAYMENT_HANDLED_SESSIONS_KEY);
}

export function markPaymentHandled(paymentSessionId?: string | null) {
  if (!paymentSessionId) return;
  const storage = safeSessionStorage();
  if (!storage) return;

  const handled = new Set(readHandledSessionIds());
  handled.add(paymentSessionId);
  storage.setItem(PAYMENT_HANDLED_SESSIONS_KEY, JSON.stringify([...handled]));
}

export function hasPaymentAlreadyBeenHandled(paymentSessionId?: string | null) {
  if (!paymentSessionId) return false;
  return readHandledSessionIds().includes(paymentSessionId);
}

export const savePrePaymentState = savePaymentSessionState;

export function getPrePaymentState(paymentSessionId?: string | null) {
  const state = restorePaymentSessionState();
  if (!paymentSessionId) return state;
  const storedId = state?.paymentSessionId ?? state?.pendingPaymentSessionId ?? state?.pendingBooking?.stripeSessionId;
  return storedId === paymentSessionId ? state : null;
}

export function restorePrePaymentState(paymentSessionId?: string | null) {
  return getPrePaymentState(paymentSessionId);
}

export function clearPrePaymentState(_paymentSessionId?: string | null) {
  clearPaymentSessionState();
}

export const hasPaymentBeenHandled = hasPaymentAlreadyBeenHandled;
