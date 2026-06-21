import { useEffect, useRef } from "react";
import { Loader2, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import type { BookingOption, ChatMessage } from "@/types/athlete";

type Variant = "compact" | "full";

const money = (cents: number, currency = "usd") => {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(
      cents / 100
    );
  } catch {
    return `$${(cents / 100).toFixed(2)}`;
  }
};

/**
 * The scrolling message list shared by the compact rail and the full-page
 * assistant. It auto-scrolls to the newest message and renders the orchestrator
 * extras (grounding chips, agents used, bookable options, follow-up actions).
 * `variant` only changes spacing/type scale, never behaviour.
 */
export function ChatThread({
  messages,
  loading,
  onSend,
  onBook,
  bookingBusy,
  variant = "compact",
}: {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (text: string) => void;
  onBook: (option: BookingOption) => void;
  bookingBusy: string | null;
  variant?: Variant;
}) {
  const full = variant === "full";
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div
      ref={scrollRef}
      className={cn(
        "scroll-thin min-h-0 flex-1 overflow-y-auto overflow-x-hidden",
        full ? "space-y-4 px-0.5 py-1" : "-mr-2 space-y-3 pr-2"
      )}
    >
      {messages.map((m) => (
        <div
          key={m.id}
          className={cn("fade-up flex flex-col gap-1.5", m.role === "user" ? "items-end" : "items-start")}
        >
          <div
            className={cn(
              "whitespace-pre-wrap break-words rounded-2xl leading-relaxed shadow-[inset_0_1px_0_rgba(255,255,255,0.58)]",
              full ? "max-w-[88%] px-4 py-3 text-sm sm:max-w-[80%]" : "max-w-[85%] px-3.5 py-2.5 text-xs",
              m.role === "user"
                ? "bg-accent/10 text-text ring-1 ring-accent/18"
                : m.isError
                  ? "bg-negative/8 text-text ring-1 ring-negative/25"
                  : "bg-white/95 text-text-muted ring-1 ring-line"
            )}
          >
            {m.isError && (
              <span aria-hidden className="mr-1">
                ⚠️
              </span>
            )}
            {m.text}
            {(m.agents?.length || m.sources?.length) && (
              <div className="mt-2 flex flex-wrap items-center gap-1">
                {m.agents?.map((a) => (
                  <span
                    key={`a-${a}`}
                    className="rounded-lg bg-ai/10 px-1.5 py-0.5 text-[10px] font-medium capitalize text-ai"
                  >
                    via {a}
                  </span>
                ))}
                {m.sources?.map((s) => (
                  <span
                    key={`s-${s}`}
                    className="rounded-lg bg-accent/8 px-1.5 py-0.5 text-[10px] font-medium text-text-dim"
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>

          {m.role === "assistant" && m.options?.length ? (
            <div className={cn("flex w-full flex-col gap-1.5", full ? "max-w-[88%] sm:max-w-[80%]" : "max-w-[92%]")}>
              {m.options.map((o) => (
                <div
                  key={o.title}
                  className="glass-inset flex items-center gap-2 rounded-2xl bg-white/95 p-2 ring-1 ring-line"
                >
                  <div className="min-w-0 flex-1">
                    <div className={cn("truncate font-semibold text-text", full ? "text-xs" : "text-[11px]")}>
                      {o.title}
                    </div>
                    {o.description && (
                      <div className={cn("truncate text-text-dim", full ? "text-[11px]" : "text-[10px]")}>
                        {o.description}
                      </div>
                    )}
                  </div>
                  <div className={cn("tnum shrink-0 font-semibold text-text", full ? "text-xs" : "text-[11px]")}>
                    {money(o.amountCents, o.currency)}
                  </div>
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={bookingBusy !== null}
                    onClick={() => onBook(o)}
                    className="shrink-0"
                  >
                    {bookingBusy === o.title ? <Loader2 className="size-3.5 animate-spin" /> : "Book & Pay"}
                  </Button>
                </div>
              ))}
            </div>
          ) : null}

          {m.role === "assistant" && m.actions?.length ? (
            <div className={cn("flex flex-wrap gap-1.5", full ? "max-w-[88%] sm:max-w-[80%]" : "max-w-[92%]")}>
              {m.actions.slice(0, full ? 4 : 3).map((a) => (
                <button
                  key={a}
                  onClick={() => onSend(a)}
                  disabled={loading}
                  className="glass-chip rounded-xl px-2 py-1 text-left text-[11px] text-text-muted transition-colors hover:border-ai/30 hover:bg-accent/7 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {a}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ))}

      {loading && (
        <div className="fade-up flex justify-start" aria-live="polite">
          <div className="flex items-center gap-1.5 rounded-2xl bg-white/95 px-3.5 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.58)] ring-1 ring-line">
            <span className="size-1.5 animate-bounce rounded-full bg-ai/70 [animation-delay:-0.2s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-ai/70 [animation-delay:-0.1s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-ai/70" />
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * The message composer shared by both surfaces. Built to never clip the input:
 * the row is `w-full box-border`, the text field is `min-w-0 flex-1` (so it can
 * shrink without pushing the button off-edge), and the send button is `shrink-0`
 * so it can never overlap the text.
 */
export function ChatComposer({
  value,
  onChange,
  onSubmit,
  loading,
  variant = "compact",
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  variant?: Variant;
  placeholder?: string;
}) {
  const full = variant === "full";
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className={cn(
        "glass-inset box-border flex w-full items-center gap-2 rounded-2xl bg-white/95 ring-1 ring-accent/14 focus-within:ring-accent/35",
        full ? "p-2 pl-3" : "p-1.5 pl-2.5"
      )}
    >
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? (loading ? "Thinking…" : "Ask about your performance…")}
        aria-label="Message the assistant"
        className={cn(
          "min-w-0 flex-1 bg-transparent text-text placeholder:text-text-dim focus:outline-none",
          full ? "py-1.5 text-[15px]" : "text-sm"
        )}
      />
      <Button
        type="submit"
        variant="primary"
        size="icon"
        disabled={loading || !value.trim()}
        aria-label="Send message"
        className={cn("shrink-0", full && "size-9")}
      >
        {loading ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
      </Button>
    </form>
  );
}
