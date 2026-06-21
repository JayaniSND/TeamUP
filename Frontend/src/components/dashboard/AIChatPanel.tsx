import { memo } from "react";
import { Bot, Sparkles, X, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { athleteData } from "@/data/mockAthleteData";
import { ChatComposer, ChatThread } from "@/components/dashboard/ChatThread";
import { useChatSession, type ChatSeed } from "@/components/dashboard/useChatSession";

/**
 * Compact right-rail AI command panel for the dashboard. Suggested prompts are
 * tagged with the dashboard section they connect to, so the assistant feels
 * wired into the data. All chat logic lives in `useChatSession` and is shared
 * 1:1 with the dedicated full-page assistant (pages/AssistantPage) — the panel
 * never picks an agent itself; every message goes to the single orchestrator
 * endpoint and the panel just renders the backend's answer.
 */
export const AIChatPanel = memo(function AIChatPanel({
  open,
  onClose,
  seed,
}: {
  open: boolean;
  onClose: () => void;
  /** an externally triggered question (e.g. a section's Ask-AI button) */
  seed?: ChatSeed | null;
}) {
  const { messages, input, setInput, loading, send, submit, book, bookingBusy } = useChatSession({ seed });

  if (!open) return null;

  return (
    <aside className="glass-card fade-up fixed bottom-3 right-3 top-3 z-40 flex min-h-0 w-[calc(100vw-1.5rem)] max-w-[380px] flex-col overflow-hidden rounded-[2rem] p-3.5 xl:relative xl:inset-auto xl:z-auto xl:h-full xl:w-full xl:max-w-none xl:p-4">
      <header className="flex shrink-0 items-center gap-2.5 border-b border-line pb-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-ai/20 to-accent/20 text-ai ring-1 ring-ai/30">
          <Bot className="size-4.5" strokeWidth={2} />
        </span>
        <div className="min-w-0 leading-tight">
          <div className="text-sm font-semibold text-text">AI Coach</div>
          <div className={cn("flex items-center gap-1 text-[11px]", loading ? "text-warning" : "text-positive")}>
            <span
              className={cn("size-1.5 rounded-full", loading ? "animate-pulse bg-warning" : "bg-positive")}
            />
            {loading ? "Thinking…" : "Connected to dashboard"}
          </div>
        </div>
        <button
          onClick={onClose}
          className="ml-auto grid size-8 place-items-center rounded-xl text-text-dim transition-colors hover:bg-accent/7 hover:text-text"
          aria-label="Close AI panel"
        >
          <X className="size-4" />
        </button>
      </header>

      <div className="grid shrink-0 grid-cols-2 gap-2 py-3">
        <div className="glass-inset rounded-2xl p-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim">Load</div>
          <div className="tnum mt-1 text-2xl font-semibold text-text">290m</div>
          <div className="mt-1 text-[11px] text-warning">High week</div>
        </div>
        <div className="glass-inset rounded-2xl p-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim">Recovery</div>
          <div className="tnum mt-1 text-2xl font-semibold text-text">55</div>
          <div className="mt-1 text-[11px] text-positive">Connected</div>
        </div>
      </div>

      <ChatThread
        messages={messages}
        loading={loading}
        onSend={send}
        onBook={book}
        bookingBusy={bookingBusy}
        variant="compact"
      />

      <div className="shrink-0 border-t border-line pt-3">
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-dim">
          <Sparkles className="size-3" /> Suggested
        </div>
        <div className="scroll-thin mb-3 flex max-h-[4.5rem] flex-wrap gap-1.5 overflow-y-auto pr-1">
          {athleteData.suggestedPrompts.map((p) => (
            <button
              key={p.id}
              onClick={() => send(p.text)}
              disabled={loading}
              className="glass-chip group flex items-center gap-1 rounded-xl px-2 py-1.5 text-left text-[11px] text-text-muted transition-colors hover:border-ai/30 hover:bg-accent/7 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
            >
              {p.text}
              <ArrowUpRight className="size-3 text-text-dim group-hover:text-ai" />
            </button>
          ))}
        </div>

        <ChatComposer value={input} onChange={setInput} onSubmit={submit} loading={loading} variant="compact" />
      </div>
    </aside>
  );
});
