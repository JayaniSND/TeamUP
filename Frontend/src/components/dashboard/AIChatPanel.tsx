import { memo, useCallback, useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, X, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { athleteData, cannedReplies } from "@/data/mockAthleteData";
import type { ChatMessage } from "@/types/athlete";

let idSeq = 0;
const nextId = () => `c${++idSeq}`;

/**
 * Right-rail AI command panel. Suggested prompts are tagged with the dashboard
 * section they connect to, so the assistant feels wired into the data. Replies
 * are canned (see cannedReplies) and cite the backend `sections` they'd draw on,
 * standing in for the real `/chat` endpoint.
 */
export const AIChatPanel = memo(function AIChatPanel({
  open,
  onClose,
  seed,
}: {
  open: boolean;
  onClose: () => void;
  /** an externally triggered question (e.g. a section's Ask-AI button) */
  seed?: { id: number; text: string; replyId?: string } | null;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: nextId(),
      role: "assistant",
      text: "I'm wired into your training, recovery, match and sponsorship data. Ask me anything — or tap a suggested question below.",
    },
  ]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const send = useCallback((text: string, replyId?: string) => {
    if (!text.trim()) return;
    const userMsg: ChatMessage = { id: nextId(), role: "user", text };
    const canned = replyId ? cannedReplies[replyId] : undefined;
    const reply: ChatMessage = {
      id: nextId(),
      role: "assistant",
      text:
        canned?.text ??
        "Here's what your data shows: load is trending high while recovery is dipping. I'd protect the knee this week and keep serve work technical. (Connect a backend to ground this in your live entries.)",
      sources: canned?.sources,
    };
    setMessages((m) => [...m, userMsg, reply]);
    setInput("");
  }, []);

  // respond to externally-seeded questions from section Ask-AI buttons
  useEffect(() => {
    if (seed?.text) send(seed.text, seed.replyId);
  }, [seed?.id, seed?.replyId, seed?.text, send]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  if (!open) return null;

  return (
    <aside className="glass-card fade-up fixed bottom-3 right-3 top-3 z-40 flex w-[calc(100vw-1.5rem)] max-w-[380px] min-h-0 flex-col overflow-hidden rounded-[2rem] p-3.5 xl:relative xl:inset-auto xl:z-auto xl:h-full xl:w-full xl:max-w-none xl:p-4">
      <header className="flex shrink-0 items-center gap-2.5 border-b border-line pb-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-ai/20 to-accent/20 text-ai ring-1 ring-ai/30">
          <Bot className="size-4.5" strokeWidth={2} />
        </span>
        <div className="min-w-0 leading-tight">
          <div className="text-sm font-semibold text-text">AI Coach</div>
          <div className="flex items-center gap-1 text-[11px] text-positive">
            <span className="size-1.5 rounded-full bg-positive" /> Connected to dashboard
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

      <div ref={scrollRef} className="scroll-thin -mr-2 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2">
        {messages.map((m) => (
          <div key={m.id} className={cn("fade-up flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed shadow-[inset_0_1px_0_rgba(255,255,255,0.58)]",
                m.role === "user" ? "bg-accent/10 text-text ring-1 ring-accent/18" : "bg-white/95 text-text-muted ring-1 ring-line"
              )}
            >
              {m.text}
              {m.sources && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {m.sources.map((s) => (
                    <span key={s} className="rounded-lg bg-ai/10 px-1.5 py-0.5 text-[10px] font-medium text-ai">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="shrink-0 border-t border-line pt-3">
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-dim">
          <Sparkles className="size-3" /> Suggested
        </div>
        <div className="scroll-thin mb-3 flex max-h-[4.5rem] flex-wrap gap-1.5 overflow-y-auto pr-1">
          {athleteData.suggestedPrompts.map((p) => (
            <button
              key={p.id}
              onClick={() => send(p.text, p.id)}
              className="glass-chip group flex items-center gap-1 rounded-xl px-2 py-1.5 text-left text-[11px] text-text-muted transition-colors hover:border-ai/30 hover:bg-accent/7 hover:text-text"
            >
              {p.text}
              <ArrowUpRight className="size-3 text-text-dim group-hover:text-ai" />
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="glass-inset flex h-11 items-center gap-2 rounded-2xl bg-white/95 p-1.5 ring-1 ring-accent/14 focus-within:border-accent/40 focus-within:ring-accent/35"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your performance…"
            className="min-w-0 flex-1 bg-transparent px-2 text-sm text-text placeholder:text-text-dim focus:outline-none"
          />
          <Button type="submit" variant="primary" size="icon">
            <Send className="size-3.5" />
          </Button>
        </form>
      </div>
    </aside>
  );
});
