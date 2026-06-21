import { useCallback, useEffect, useState } from "react";
import { useChatSessionState } from "@/context/ChatSessionContext";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
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
 * Booking no longer redirects to a hosted checkout page — `book` opens the
 * in-app PaymentModal (via the calendar context), so the app never reloads and
 * the chat history + originating route are preserved.
 */
export function useChatSession(opts: { seed?: ChatSeed | null } = {}) {
  const { seed } = opts;
  const { messages, loading, send, lastSeedIdRef } = useChatSessionState();
  const { startPayment, pendingPayment } = useCalendarEvents();

  const [input, setInput] = useState("");

  const book = useCallback(
    (option: BookingOption) => {
      startPayment(option);
    },
    [startPayment]
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

  return { messages, input, setInput, loading, send, submit, book, bookingBusy };
}
