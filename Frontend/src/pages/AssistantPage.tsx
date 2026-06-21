import { Link } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  Bot,
  HeartPulse,
  Hotel,
  Plane,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { ChatComposer, ChatThread } from "@/components/dashboard/ChatThread";
import { useChatSession } from "@/components/dashboard/useChatSession";
import { athleteData } from "@/data/mockAthleteData";
import { cn } from "@/lib/utils";

// Sidebar is shared with the dashboard; section clicks self-navigate via the
// router, so its onSelect is a no-op here. Module-level keeps the identity
// stable for the memoized Sidebar.
const NOOP = () => {};

// Example prompts for the empty state. These are plain text sent verbatim to the
// orchestrator — the backend decides which specialist (recovery / performance /
// travel / schedule / booking) handles each one.
const EXAMPLE_PROMPTS: { icon: typeof HeartPulse; label: string }[] = [
  { icon: HeartPulse, label: "Analyze today's recovery status" },
  { icon: TrendingUp, label: "Summarize my recent performance" },
  { icon: Activity, label: "Check injury risk based on recent logs" },
  { icon: Target, label: "What should I focus on this week?" },
  { icon: HeartPulse, label: "Create a recovery plan after today's training" },
  { icon: Plane, label: "Plan travel for my next match" },
  { icon: Hotel, label: "Help me find a hotel near the event" },
  { icon: Plane, label: "Prepare a flight booking plan" },
];

/**
 * Dedicated full-page AI assistant (route: /assistant). Chat is the whole page
 * here, not a dashboard widget. It reuses the exact same chat brain as the
 * compact rail (useChatSession) and the same message/composer components
 * (ChatThread / ChatComposer, variant="full"), so every request still goes to
 * the single orchestrator endpoint and nothing about routing changes — only the
 * layout expands.
 */
export default function AssistantPage() {
  const { messages, input, setInput, loading, send, submit, book, bookingBusy } = useChatSession({ mode: "full" });

  // Only the greeting present → show the welcome / example-prompt hero instead
  // of a one-line thread, so the page never opens looking empty.
  const isEmpty = messages.length <= 1;

  return (
    <div className="relative h-[100dvh] overflow-hidden p-3 text-text sm:p-4 lg:p-4">
      <div className="app-aurora" />

      <div className="aurora-shell relative z-10 mx-auto flex h-[calc(100dvh-1.5rem)] max-w-[1540px] overflow-hidden rounded-[2rem] sm:h-[calc(100dvh-2rem)] lg:h-[calc(100vh-2rem)]">
        <Sidebar active="ai" onSelect={NOOP} profile={athleteData.profile} />

        <div className="flex min-w-0 flex-1 flex-col">
          {/* mobile top bar (sidebar is hidden < lg) */}
          <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-white/85 px-4 py-2.5 backdrop-blur-md lg:hidden">
            <Link
              to="/dashboard"
              className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-accent"
              aria-label="Back to dashboard"
            >
              <ArrowLeft className="size-4" />
            </Link>
            <span className="text-sm font-semibold text-text">Athlete Assistant</span>
          </div>

          <main className="flex min-h-0 flex-1 px-3 py-4 sm:px-5 lg:px-6 lg:py-6">
            <div className="mx-auto flex min-h-0 w-full max-w-[920px] flex-col">
              {/* header */}
              <header className="fade-up mb-4 flex shrink-0 flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-ai/20 to-accent/20 text-ai ring-1 ring-ai/30">
                    <Bot className="size-5.5" strokeWidth={1.9} />
                  </span>
                  <div className="min-w-0">
                    <h1 className="text-xl font-semibold tracking-tight text-text">Athlete Assistant</h1>
                    <p
                      className={cn(
                        "mt-0.5 flex items-center gap-1.5 text-sm",
                        loading ? "text-warning" : "text-text-muted"
                      )}
                    >
                      <span
                        className={cn(
                          "size-1.5 rounded-full",
                          loading ? "animate-pulse bg-warning" : "bg-positive"
                        )}
                      />
                      {loading ? "Thinking…" : "Recovery · performance · schedule · travel — all in one chat"}
                    </p>
                  </div>
                </div>
                <Link to="/dashboard" className="hidden lg:block">
                  <span className="glass-chip card-hover inline-flex h-8 items-center gap-1.5 rounded-2xl px-3 text-xs font-semibold text-text">
                    <ArrowLeft className="size-3.5" strokeWidth={1.9} />
                    Dashboard
                  </span>
                </Link>
              </header>

              {/* chat card — fills remaining height; thread scrolls, composer sticks */}
              <section className="glass-card fade-up flex min-h-0 flex-1 flex-col rounded-[1.65rem] p-3 sm:p-4">
                {isEmpty ? (
                  <div className="scroll-thin flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-2 py-6 text-center">
                    <span className="grid size-14 place-items-center rounded-3xl bg-gradient-to-br from-ai/15 to-accent/15 text-ai ring-1 ring-ai/25">
                      <Sparkles className="size-6" strokeWidth={1.8} />
                    </span>
                    <h2 className="mt-4 text-lg font-semibold text-text">How can I help you train smarter?</h2>
                    <p className="mt-1 max-w-md text-sm leading-relaxed text-text-muted">
                      Ask anything about your recovery, performance, and schedule — or have me plan travel, hotels,
                      and flights for your next event. Try one of these:
                    </p>
                    <div className="mt-5 grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
                      {EXAMPLE_PROMPTS.map((p) => (
                        <button
                          key={p.label}
                          onClick={() => send(p.label)}
                          disabled={loading}
                          className="glass-card card-hover group flex items-center gap-2.5 rounded-2xl px-3.5 py-3 text-left disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-accent/8 text-accent ring-1 ring-accent/14 transition-colors group-hover:bg-accent/12">
                            <p.icon className="size-4" strokeWidth={1.9} />
                          </span>
                          <span className="text-[13px] font-medium leading-snug text-text-muted group-hover:text-text">
                            {p.label}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <ChatThread
                    messages={messages}
                    loading={loading}
                    onSend={send}
                    onBook={book}
                    bookingBusy={bookingBusy}
                    variant="full"
                  />
                )}

                <div className="mt-3 shrink-0">
                  <ChatComposer
                    value={input}
                    onChange={setInput}
                    onSubmit={submit}
                    loading={loading}
                    variant="full"
                    placeholder={loading ? "Thinking…" : "Ask about recovery, performance, schedule, or travel…"}
                  />
                  <p className="mt-2 px-1 text-center text-[11px] text-text-dim">
                    Bookings open a secure checkout — nothing is charged until you confirm payment.
                  </p>
                </div>
              </section>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
