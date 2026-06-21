import { useCallback, useEffect, useMemo, useState } from "react";
import { useChatSessionState } from "@/context/ChatSessionContext";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import { calendarEventBookingKey } from "@/lib/bookingIdentity";
import { savePrePaymentState } from "@/lib/paymentSessionPersistence";
import type { ChatMode } from "@/lib/api";
import type { BookingOption } from "@/types/athlete";

/** An externally triggered question (e.g. a section's Ask-AI button). */
export interface ChatSeed {
  id: number;
  text: string;
  replyId?: string;
}

/**
 * Thin per-surface adapter over the singleton chat engine in ChatSessionContext.
 * The thread, loading flag, and send engine are shared, so the compact dashboard
 * rail (AIChatPanel) and the full-page assistant (AssistantPage) drive ONE
 * conversation that survives navigation and the booking/payment flow. Only the
 * composer `input` is local to each surface.
 *
 * Booking opens the checkout confirmation modal, then redirects to Stripe in
 * the same tab. The calendar/chat contexts preserve the handoff state until
 * Stripe returns.
 */
export function useChatSession(opts: { seed?: ChatSeed | null; mode?: ChatMode } = {}) {
  const { seed, mode = "full" } = opts;
  const { messages, loading, send: sendMessage, lastSeedIdRef } = useChatSessionState();
  const { events, startPayment, pendingPayment } = useCalendarEvents();

  const [input, setInput] = useState("");

  const send = useCallback(
    (text: string) => sendMessage(text, { mode }),
    [mode, sendMessage]
  );

  const book = useCallback(
    (option: BookingOption) => {
      savePrePaymentState({ chatMessages: messages });
      startPayment(option);
    },
    [messages, startPayment]
  );

  // Submit the composer: clear the field, then send. Safe to clear optimistically
  // because the composer + suggested prompts are disabled while a reply is loading.
  const submit = useCallback(() => {
    const text = input;
    setInput("");
    void send(text);
  }, [input, send]);

  // Respond to externally-seeded questions (section Ask-AI buttons). Deduped by
  // seed id through a shared ref so co-mounted surfaces never double-send.
  useEffect(() => {
    if (seed?.text && seed.id !== lastSeedIdRef.current) {
      lastSeedIdRef.current = seed.id;
      void send(seed.text);
    }
  }, [seed?.id, seed?.text, send, lastSeedIdRef]);

  // The button for the option currently in checkout shows as busy/disabled.
  const bookingBusy = pendingPayment?.option.title ?? null;
  const paidBookingKeys = useMemo(
    () =>
      new Set(
        events
          .filter((event) => event.source === "payment" && (event.paymentStatus === "paid" || event.status === "Paid"))
          .map(calendarEventBookingKey)
      ),
    [events]
  );

  return { messages, input, setInput, loading, send, submit, book, bookingBusy, paidBookingKeys };
}
