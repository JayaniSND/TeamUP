import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Bot, Hexagon } from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { OverviewCards } from "@/components/dashboard/OverviewCards";
import { PerformanceChart } from "@/components/dashboard/PerformanceChart";
import { RecoveryPanel } from "@/components/dashboard/RecoveryPanel";
import { WeeklyCalendar } from "@/components/dashboard/WeeklyCalendar";
import { AgentInsightsStrip } from "@/components/dashboard/AgentInsightsStrip";
import { AIChatPanel } from "@/components/dashboard/AIChatPanel";
import { cn } from "@/lib/utils";
import { athleteData } from "@/data/mockAthleteData";

const MOBILE_NAV = [
  ["overview", "Overview"],
  ["calendar", "Calendar"],
  ["performance", "Load"],
  ["recovery", "Recovery"],
  ["upload", "Upload"],
  ["insights", "AI"],
] as const;

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
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
  const openCalendar = useCallback(() => navigate("/calendar"), [navigate]);

  const h = useMemo(
    () => ({
      overview: () => askAI("What should I focus on next week?", "p1"),
      explainTrend: () => askAI("Explain my recent performance trend.", "p6"),
      recovery: () => askAI("Check my recovery risk.", "p3"),
      agent: (prompt: string, replyId?: string) => askAI(prompt, replyId),
    }),
    [askAI]
  );

  const recoveryInsight = useMemo(() => data.insights.find((i) => i.agent === "Recovery"), [data.insights]);

  const onSelect = useCallback(
    (id: string) => {
      if (id === "calendar") {
        navigate("/calendar");
        return;
      }
      if (id === "upload") {
        navigate("/upload");
        return;
      }
      setActive(id);
      if (id === "ai") {
        setChatOpen(true);
        return;
      }
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [navigate]
  );

  // Arriving from another page (e.g. the Upload page) via a sidebar section:
  // honor the requested target once the dashboard has mounted.
  useEffect(() => {
    const target = (location.state as { scrollTo?: string } | null)?.scrollTo;
    if (target) requestAnimationFrame(() => onSelect(target));
    // run once on mount; location.state is read at arrival time
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-hidden p-3 text-text sm:p-4 lg:h-screen lg:overflow-hidden lg:p-4">
      <div className="app-aurora" />

      <div className="aurora-shell relative z-10 mx-auto flex min-h-[calc(100vh-1.5rem)] max-w-[1540px] overflow-hidden rounded-[2rem] sm:min-h-[calc(100vh-2rem)] lg:h-[calc(100vh-2rem)] lg:min-h-0">
        <Sidebar active={active} onSelect={onSelect} profile={data.profile} />

        <div className="min-w-0 flex-1">
          <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-white/85 px-4 py-2.5 backdrop-blur-md lg:hidden">
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
                    active === id ? "bg-accent/10 text-accent ring-1 ring-accent/18" : "text-text-muted hover:bg-accent/7 hover:text-text"
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
                <div className="board-surface grid min-h-0 grid-cols-1 gap-3 rounded-[1.6rem] p-2.5 lg:h-full xl:grid-cols-12 xl:grid-rows-[auto_minmax(0,1fr)_auto]">
                  {/* Top band — high-impact KPIs + next agent action */}
                  <div id="overview" className="scroll-mt-24 xl:col-span-8 lg:scroll-mt-8">
                    <OverviewCards metrics={data.overview} onCalendarOpen={openCalendar} />
                  </div>

                  <div className="xl:col-span-4">
                    <AgentInsightsStrip insights={data.insights} onAsk={h.agent} delay={0.03} />
                  </div>

                  {/* Center band — the Weekly Calendar is the focus and grows to fill */}
                  <div className="min-h-[280px] xl:col-span-12 xl:min-h-0">
                    <WeeklyCalendar calendar={data.weeklyCalendar} onOpenCalendar={openCalendar} />
                  </div>

                  {/* Bottom band — Performance + Recovery, secondary */}
                  <div className="h-[260px] xl:col-span-8 xl:h-[244px]">
                    <PerformanceChart data={data.performance} onExplainTrend={h.explainTrend} />
                  </div>

                  <div className="h-[260px] xl:col-span-4 xl:h-[244px]">
                    <RecoveryPanel recovery={data.recovery} insight={recoveryInsight} onAction={h.recovery} />
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
            className="card-hover fixed bottom-5 right-5 z-40 grid size-14 place-items-center rounded-3xl bg-accent text-white shadow-[0_18px_42px_-16px_rgba(47,160,132,0.6)]"
            aria-label="Open AI chat"
          >
            <Bot className="size-6" strokeWidth={2} />
          </button>
        )}
      </div>
    </div>
  );
}
