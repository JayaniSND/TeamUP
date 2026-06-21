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
import { LiveAgentPanel } from "@/components/agents/LiveAgentPanel";
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
  const { messages, input, setInput, loading, send, submit, book, bookingBusy, paidBookingKeys } = useChatSession({ mode: "full" });

  // Only the greeting present → show the welcome / example-prompt hero instead
  // of a one-line thread, so the page never opens looking empty.
  const isEmpty = messages.length <= 1;

  return (
    <div className="relative min-h-[100dvh] overflow-x-hidden p-3 text-text sm:p-4 lg:p-4 xl:h-[100dvh] xl:overflow-hidden">
      <div className="app-aurora" />

      <div className="aurora-shell relative z-10 mx-auto flex min-h-[calc(100dvh-1.5rem)] max-w-[1540px] overflow-hidden rounded-[2rem] sm:min-h-[calc(100dvh-2rem)] xl:h-[calc(100vh-2rem)] xl:min-h-0">
        <Sidebar active="ai" onSelect={NOOP} profile={athleteData.profile} />

        <div className="flex min-w-0 flex-1 flex-col">
          <Link
            to="/dashboard"
            className="glass-chip card-hover absolute right-5 top-5 z-40 hidden h-8 items-center gap-1.5 rounded-2xl px-3 text-xs font-semibold text-text lg:inline-flex"
          >
            <ArrowLeft className="size-3.5" strokeWidth={1.9} />
            Dashboard
          </Link>

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

          <main className="flex min-h-0 flex-1 flex-col px-3 py-4 sm:px-5 lg:px-6 lg:py-6">
            <div className="mx-auto grid min-h-0 w-full max-w-[1400px] flex-1 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.78fr)] xl:grid-rows-[auto_minmax(0,1fr)]">
              {/* LEFT — chat column (stacks first on smaller screens) */}
              <div className="flex min-w-0 flex-col xl:contents">
              {/* header */}
              <header className="fade-up mb-4 flex shrink-0 flex-wrap items-start justify-between gap-3 xl:col-start-1 xl:row-start-1 xl:mb-0">
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
              </header>

              {/* chat card — fills remaining height; thread scrolls, composer sticks */}
              <section className="glass-card fade-up flex h-[68vh] min-h-0 w-full flex-col rounded-[1.65rem] p-3 sm:p-4 xl:col-start-1 xl:row-start-2 xl:h-auto xl:flex-1">
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
                    paidBookingKeys={paidBookingKeys}
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

              {/* RIGHT — live agent system panel */}
              <div className="box-border flex min-w-0 flex-col xl:col-start-2 xl:row-start-2 xl:min-h-0">
                <LiveAgentPanel />
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
