import { useCallback, useMemo, useRef, useState } from "react";
import { Bot, Hexagon } from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { OverviewCards } from "@/components/dashboard/OverviewCards";
import { PerformanceChart } from "@/components/dashboard/PerformanceChart";
import { FormResultsCard } from "@/components/dashboard/FormResultsCard";
import { RecoveryPanel } from "@/components/dashboard/RecoveryPanel";
import { AgentInsightsStrip } from "@/components/dashboard/AgentInsightsStrip";
import { AIChatPanel } from "@/components/dashboard/AIChatPanel";
import { cn } from "@/lib/utils";
import { athleteData } from "@/data/mockAthleteData";

const MOBILE_NAV = [
  ["overview", "Overview"],
  ["performance", "Load"],
  ["form", "Form"],
  ["recovery", "Recovery"],
  ["insights", "AI"],
] as const;

export default function App() {
  const [active, setActive] = useState("overview");
  const [chatOpen, setChatOpen] = useState(() => typeof window !== "undefined" && window.innerWidth >= 1440);
  const [seed, setSeed] = useState<{ id: number; text: string; replyId?: string } | null>(null);
  const seqRef = useRef(0);

  const data = athleteData;

  const askAI = useCallback((text: string, replyId?: string) => {
    seqRef.current += 1;
    setSeed({ id: seqRef.current, text, replyId });
    setChatOpen(true);
  }, []);

  const closeChat = useCallback(() => setChatOpen(false), []);
  const openChat = useCallback(() => setChatOpen(true), []);

  const h = useMemo(
    () => ({
      overview: () => askAI("What should I focus on next week?", "p1"),
      explainForm: () => askAI("Explain my recent form and results.", "p6"),
      explainTrend: () => askAI("Explain my recent performance trend.", "p6"),
      recovery: () => askAI("Check my recovery risk.", "p3"),
      agent: (prompt: string, replyId?: string) => askAI(prompt, replyId),
    }),
    [askAI]
  );

  const recoveryInsight = useMemo(() => data.insights.find((i) => i.agent === "Recovery"), [data.insights]);

  const onSelect = useCallback((id: string) => {
    setActive(id);
    if (id === "ai") {
      setChatOpen(true);
      return;
    }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-hidden p-3 text-text sm:p-4 lg:h-screen lg:overflow-hidden lg:p-4">
      <div className="app-aurora" />

      <div className="aurora-shell relative z-10 mx-auto flex min-h-[calc(100vh-1.5rem)] max-w-[1540px] overflow-hidden rounded-[2rem] sm:min-h-[calc(100vh-2rem)] lg:h-[calc(100vh-2rem)] lg:min-h-0">
        <Sidebar active={active} onSelect={onSelect} profile={data.profile} />

        <div className="min-w-0 flex-1">
          <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-white/15 bg-white/[0.08] px-4 py-2.5 backdrop-blur-xl lg:hidden">
            <span className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-accent">
              <Hexagon className="size-4" strokeWidth={2} />
            </span>
            <div className="scroll-thin -mx-1 flex flex-1 gap-1.5 overflow-x-auto px-1">
              {MOBILE_NAV.map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => onSelect(id)}
                  className={cn(
                    "shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
                    active === id ? "bg-white/22 text-white ring-1 ring-white/30" : "text-text-muted hover:bg-white/12"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <main className="px-3 py-3 sm:px-4 lg:h-full lg:overflow-hidden lg:px-4 xl:px-5">
            <div className="mx-auto flex h-full max-w-[1280px] flex-col">
              <DashboardHeader profile={data.profile} onAskAI={h.overview} />

              <div
                className={cn(
                  "mt-3 grid min-h-0 flex-1 grid-cols-1 gap-3",
                  chatOpen ? "xl:grid-cols-[minmax(0,1fr)_300px] 2xl:grid-cols-[minmax(0,1fr)_330px]" : "xl:grid-cols-1"
                )}
              >
                <div className="grid min-h-0 grid-cols-1 gap-3 xl:grid-cols-12 xl:grid-rows-[auto_minmax(0,1fr)]">
                  <div id="overview" className="scroll-mt-24 xl:col-span-8 lg:scroll-mt-8">
                    <OverviewCards metrics={data.overview} />
                  </div>

                  <div className="xl:col-span-4">
                    <AgentInsightsStrip insights={data.insights} onAsk={h.agent} delay={0.03} />
                  </div>

                  <div className="min-h-0 xl:col-span-8">
                    <PerformanceChart data={data.performance} onAction={h.explainTrend} />
                  </div>

                  <div className="grid min-h-0 grid-cols-1 gap-3 xl:col-span-4 xl:grid-rows-[auto_minmax(0,1fr)]">
                    <RecoveryPanel recovery={data.recovery} insight={recoveryInsight} onAction={h.recovery} />
                    <FormResultsCard form={data.form} onAction={h.explainForm} />
                  </div>
                </div>

                {chatOpen && (
                  <div className="hidden h-full min-h-0 xl:block">
                    <AIChatPanel open={chatOpen} onClose={closeChat} seed={seed} />
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </div>

      <div className="xl:hidden">
        <AIChatPanel open={chatOpen} onClose={closeChat} seed={seed} />
        {!chatOpen && (
          <button
            onClick={openChat}
            className="card-hover fixed bottom-5 right-5 z-40 grid size-14 place-items-center rounded-3xl bg-ai text-white shadow-[0_18px_42px_-16px_rgba(135,92,246,0.72)]"
            aria-label="Open AI chat"
          >
            <Bot className="size-6" strokeWidth={2} />
          </button>
        )}
      </div>
    </div>
  );
}
