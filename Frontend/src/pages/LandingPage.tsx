import { lazy, Suspense, useEffect, useLayoutEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  ArrowRight,
  Bot,
  CalendarDays,
  Database,
  FileText,
  Handshake,
  HeartPulse,
  LockKeyhole,
  Plane,
  Search,
  Sparkles,
  Trophy,
  UploadCloud,
  Waypoints,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AgentCanvasBoundary, supportsWebGL } from "@/components/agents/AgentCanvasBoundary";

const LandingAgentConstellation3D = lazy(() => import("@/components/landing/LandingAgentConstellation3D"));

gsap.registerPlugin(ScrollTrigger);

type StoryStep = {
  kicker: string;
  title: string;
  body: string;
  icon: LucideIcon;
};

type AgentCard = {
  title: string;
  body: string;
  icon: LucideIcon;
};

const heroBadges = ["Voice", "Photo", "Text", "ASI:One", "Dashboard"];

const revealSteps = [
  "The athlete dumps what happened.",
  "The Librarian turns it into structured entries.",
  "The Orchestrator routes the next best agent.",
];

const workflow: StoryStep[] = [
  {
    kicker: "01 Normalize",
    title: "Raw athlete input becomes text.",
    body: "Voice uses Deepgram, notebook photos use Claude vision, and typed notes enter directly.",
    icon: UploadCloud,
  },
  {
    kicker: "02 Classify",
    title: "The Librarian files the dump.",
    body: "A single note can split into training, performance, match, recovery, logistics, sponsorship, goals, or media entries.",
    icon: FileText,
  },
  {
    kicker: "03 Route",
    title: "The Orchestrator chooses log, ask, or action.",
    body: "Questions go to grounded RAG. Specialist work goes to Recovery, Performance, Scout, Sponsorship, or Logistics.",
    icon: Waypoints,
  },
  {
    kicker: "04 Surface",
    title: "Everything returns to one athlete record.",
    body: "Supabase backs entries, metrics, recovery logs, agent outputs, sponsorship drafts, and calendar events.",
    icon: Database,
  },
];

const agents: AgentCard[] = [
  {
    title: "Recovery",
    body: "Flags wellness risk patterns from recent entries, training, recovery logs, and metrics.",
    icon: HeartPulse,
  },
  {
    title: "Performance",
    body: "Reads matches, sessions, and metrics to return trend direction and a focus area.",
    icon: Trophy,
  },
  {
    title: "Scout",
    body: "Researches opponents and files tactical coaching reports from match context.",
    icon: Search,
  },
  {
    title: "Sponsorship",
    body: "Finds brand-fit opportunities and drafts outreach. Sending remains user-approved.",
    icon: Handshake,
  },
  {
    title: "Logistics",
    body: "Finds tournaments, coordinates travel, adds calendar context, and gates entry review with Stripe test mode.",
    icon: Plane,
  },
];

const outcomeTiles: AgentCard[] = [
  {
    title: "Grounded AI chat",
    body: "Ask from ASI:One or the dashboard and get answers from the athlete's own history.",
    icon: Bot,
  },
  {
    title: "Calendar-aware logistics",
    body: "Tournament search, travel pressure, booking status, and schedule context stay visible.",
    icon: CalendarDays,
  },
  {
    title: "Careful actions",
    body: "Sponsor emails draft first. Tournament entry screens are shown, never auto-submitted.",
    icon: LockKeyhole,
  },
];

export default function LandingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const heroRef = useRef<HTMLElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const storyRef = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();
  const canUse3D = !reducedMotion && supportsWebGL();

  const { scrollYProgress } = useScroll();
  const ambientY = useTransform(scrollYProgress, [0, 1], reducedMotion ? ["0px", "0px"] : ["0px", "-90px"]);
  const ambientOpacity = useTransform(scrollYProgress, [0, 0.35, 1], [0.85, 1, 0.72]);
  const { scrollYProgress: storyProgress } = useScroll({
    target: storyRef,
    offset: ["start end", "end start"],
  });
  const dashboardLift = useTransform(storyProgress, [0, 1], reducedMotion ? ["0px", "0px"] : ["42px", "-36px"]);
  const voiceLift = useTransform(storyProgress, [0, 1], reducedMotion ? ["0px", "0px"] : ["30px", "-48px"]);

  useEffect(() => {
    if (location.search.includes("booking=")) {
      navigate(`/dashboard${location.search}`, { replace: true });
    }
  }, [location.search, navigate]);

  useLayoutEffect(() => {
    const hero = heroRef.current;
    const video = videoRef.current;
    if (!hero || !video) return undefined;

    video.pause();
    video.load();

    const syncVideoToScroll = (progress: number) => {
      if (!video.duration) return;
      video.currentTime = video.duration * Math.min(progress / 0.65, 1);
    };

    const refreshOnMetadata = () => ScrollTrigger.refresh();
    video.addEventListener("loadedmetadata", refreshOnMetadata);

    const copyIn = { opacity: 1, y: 0, yPercent: -50, duration: 0.08 };
    const copyOut = { opacity: 0, y: -20, yPercent: -50, duration: 0.06 };

    const ctx = gsap.context(() => {
      const heroTL = gsap.timeline({
        scrollTrigger: {
          trigger: hero,
          start: "top top",
          end: "+=5200",
          scrub: true,
          pin: true,
          anticipatePin: 1,
          onUpdate: (self) => syncVideoToScroll(self.progress),
        },
      });

      heroTL
        .fromTo(".copy-1", { opacity: 0, y: 30, yPercent: -50 }, copyIn, 0.03)
        .to(".copy-1", copyOut, 0.18)
        .fromTo(".copy-2", { opacity: 0, y: 30, yPercent: -50 }, copyIn, 0.22)
        .to(".copy-2", copyOut, 0.38)
        .fromTo(".copy-3", { opacity: 0, y: 30, yPercent: -50 }, copyIn, 0.42)
        .to(".copy-3", copyOut, 0.6)
        .fromTo(".impact-flash", { opacity: 0 }, { opacity: 1, duration: 0.03 }, 0.66)
        .to(".impact-flash", { opacity: 0, duration: 0.08 }, 0.69)
        .fromTo(
          ".racket-wipe",
          { xPercent: -130, opacity: 0 },
          { xPercent: 125, opacity: 1, duration: 0.12 },
          0.66
        )
        .to(".racket-wipe", { opacity: 0, duration: 0.06 }, 0.76)
        .to(".serve-video", { opacity: 0.28, filter: "blur(7px) brightness(0.54)", duration: 0.16 }, 0.72)
        .fromTo(".product-reveal-copy", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.12 }, 0.73)
        .fromTo(
          ".real-dashboard-layer",
          { opacity: 0, y: 70, scale: 0.96 },
          { opacity: 1, y: 0, scale: 1, duration: 0.2 },
          0.74
        )
        .fromTo(
          ".hero-floating-card",
          { opacity: 0, y: 28 },
          { opacity: 1, y: 0, stagger: 0.018, duration: 0.11 },
          0.78
        );
    }, hero);

    return () => {
      video.removeEventListener("loadedmetadata", refreshOnMetadata);
      ctx.revert();
    };
  }, []);

  return (
    <main className="landing-page relative min-h-screen overflow-x-hidden bg-[#f6faf7] text-[#10251f]">
      <motion.div
        className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(42rem_30rem_at_20%_12%,rgba(111,207,151,0.16),transparent_64%),radial-gradient(48rem_34rem_at_88%_18%,rgba(47,160,132,0.11),transparent_62%),linear-gradient(180deg,#f9fcfa,#eef7f2)]"
        style={{ y: ambientY, opacity: ambientOpacity }}
      />

      <section ref={heroRef} className="serve-hero relative z-10 h-screen overflow-hidden">
        <video
          ref={videoRef}
          id="heroVideo"
          className="serve-video absolute inset-0 h-full w-full object-cover"
          muted
          playsInline
          preload="auto"
          poster="/hero-poster.jpg"
        >
          <source src="/hero-serve-720.mp4" type="video/mp4" />
        </video>

        <div className="absolute inset-0 bg-[radial-gradient(circle_at_52%_28%,rgba(255,255,255,0.16),transparent_34%),linear-gradient(90deg,rgba(6,18,14,0.84),rgba(8,24,19,0.5)_48%,rgba(5,15,12,0.72))]" />
        <div className="impact-flash pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_52%_42%,rgba(255,255,255,0.98),rgba(111,207,151,0.52)_28%,transparent_58%)] opacity-0" />
        <div className="racket-wipe pointer-events-none absolute -left-1/4 top-[-18%] h-[140%] w-1/3 rotate-[18deg] bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.86),rgba(111,207,151,0.42),transparent)] opacity-0 blur-[1px]" />

        <div className="relative z-10 mx-auto flex h-full max-w-[1440px] flex-col px-5 py-5 sm:px-8 lg:px-10">
          <nav className="flex shrink-0 items-center justify-between">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/10 px-3 py-2 text-sm font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-md"
            >
              <span className="grid size-7 place-items-center rounded-full bg-[#6FCF97]/18 text-[#6FCF97]">
                <Sparkles className="size-3.5" />
              </span>
              SportsMom
            </Link>
            <div className="flex items-center gap-2">
              <Link
                to="/upload"
                className="hidden rounded-full border border-white/18 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/18 sm:inline-flex"
              >
                Upload
              </Link>
              <Link
                to="/dashboard"
                className="rounded-full border border-white/18 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/18"
              >
                Dashboard
              </Link>
            </div>
          </nav>

          <div className="relative min-h-0 flex-1">
            <div className="hero-copy copy-1">A support team for athletes who train alone.</div>
            <div className="hero-copy copy-2">Voice, photo, and text logs become structured memory.</div>
            <div className="hero-copy copy-3">Specialist agents turn that memory into decisions.</div>

            <div className="product-reveal-stage absolute inset-0 grid content-center gap-5 py-8 sm:gap-7 lg:grid-cols-[minmax(300px,0.76fr)_minmax(0,1.24fr)] lg:items-center lg:py-10">
              <div className="product-reveal-copy relative z-20 max-w-[34rem] opacity-0">
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-[#9de5ba]">SportsMom</p>
                <h1 className="mt-3 text-balance text-[2.4rem] font-semibold leading-[1.01] tracking-tight text-white sm:text-5xl lg:text-[3.7rem]">
                  Multi-agent sports intelligence for the self-managed athlete.
                </h1>
                <p className="mt-5 max-w-[31rem] text-sm leading-6 text-white/78 sm:text-base">
                  Drop in a practice note, notebook photo, or match recap. The system transcribes it, files it, routes it, and surfaces the next useful signal.
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Link
                    to="/upload"
                    className="inline-flex items-center gap-2 rounded-full bg-[#6FCF97] px-5 py-3 text-sm font-semibold text-[#10251f] shadow-[0_18px_44px_-22px_rgba(111,207,151,0.9)] transition-colors hover:bg-[#82daa8]"
                  >
                    Upload a log
                    <ArrowRight className="size-4" />
                  </Link>
                  <Link
                    to="/dashboard"
                    className="inline-flex items-center gap-2 rounded-full border border-white/18 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/18"
                  >
                    View dashboard
                  </Link>
                </div>
                <div className="mt-7 flex flex-wrap gap-2">
                  {heroBadges.map((badge) => (
                    <span
                      key={badge}
                      className="rounded-full border border-white/12 bg-white/8 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70 backdrop-blur-md"
                    >
                      {badge}
                    </span>
                  ))}
                </div>
              </div>

              <div className="real-dashboard-layer relative z-10 min-w-0 opacity-0 lg:justify-self-end">
                <div className="relative rounded-[2rem] border border-white/20 bg-white/82 p-2 shadow-[0_38px_120px_-70px_rgba(0,0,0,0.9)] backdrop-blur-xl sm:p-3">
                  <img
                    src="/dashboard.png"
                    alt="SportsMom athlete analytics dashboard with calendar, recovery insights, and AI chat"
                    className="block max-h-[33vh] w-full rounded-[1.35rem] border border-[#dce5de] bg-[#f7fbf8] object-contain shadow-[0_18px_54px_-34px_rgba(16,37,31,0.48)] sm:max-h-[42vh] lg:max-h-[61vh]"
                    loading="eager"
                    decoding="async"
                  />
                  <HeroFloatCard className="hero-floating-card -left-3 top-8 hidden xl:block" icon={HeartPulse} title="Recovery" value="Risk pattern" />
                  <HeroFloatCard className="hero-floating-card -right-3 bottom-8 hidden xl:block" icon={Bot} title="AI Coach" value="Grounded reply" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div ref={storyRef} className="relative z-10">
        <section className="relative overflow-hidden px-5 pb-20 pt-24 sm:px-8 lg:px-10 lg:pb-28 lg:pt-32">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-[#f6faf7] to-transparent" />
          <div className="mx-auto max-w-[1440px]">
            <Reveal className="mx-auto max-w-4xl text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.32em] text-[#2FA084]">The product layer</p>
              <h2 className="mt-4 text-balance text-4xl font-semibold leading-[1.04] tracking-tight text-[#10251f] sm:text-5xl lg:text-6xl">
                One athlete record. Two ways to use it.
              </h2>
              <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-[#5d726b]">
                ASI:One is the conversation. The dashboard is the command center for the days you would rather scan than talk.
              </p>
            </Reveal>

            <div className="relative mt-16 grid gap-8 lg:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.28fr)] lg:gap-12">
              <div className="lg:sticky lg:top-10 lg:h-fit">
                <GlassPanel className="p-6 sm:p-7">
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#2FA084]">Dashboard preview</p>
                  <h3 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-[#10251f]">
                    Every panel is an agent output made legible.
                  </h3>
                  <p className="mt-4 text-sm leading-6 text-[#60766f]">
                    Recovery signals, performance trends, calendar context, and AI chat all read from the same Supabase-backed data.
                  </p>
                  <div className="mt-6 space-y-3">
                    {revealSteps.map((step, index) => (
                      <div key={step} className="flex items-center gap-3">
                        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-[#2FA084]/10 text-xs font-semibold text-[#1F6F5F]">
                          {index + 1}
                        </span>
                        <span className="text-sm font-medium text-[#34584f]">{step}</span>
                      </div>
                    ))}
                  </div>
                </GlassPanel>
              </div>

              <div className="space-y-10 lg:space-y-16">
                <motion.div style={{ y: dashboardLift }}>
                  <ProductFrame
                    image="/dashboard.png"
                    alt="SportsMom dashboard preview"
                    eyebrow="Scan mode"
                    title="Dashboard intelligence"
                    description="Use it to see the latest recovery signal, next match, shared calendar, performance trend, and AI coach state at once."
                    labels={[
                      { text: "Agent outputs", className: "left-4 top-4" },
                      { text: "Calendar + AI", className: "bottom-4 right-4" },
                    ]}
                  />
                </motion.div>

                <motion.div style={{ y: voiceLift }}>
                  <ProductFrame
                    image="/voice_upload.png"
                    alt="SportsMom voice upload flow"
                    eyebrow="Capture mode"
                    title="Voice upload that becomes structured memory"
                    description="Record or upload audio, convert it to text, then submit it through the backend Librarian flow."
                    labels={[
                      { text: "Voice Entry", className: "left-4 top-4" },
                      { text: "Converted Text", className: "right-4 top-4" },
                      { text: "Submit entry", className: "bottom-4 right-4" },
                    ]}
                  />
                </motion.div>
              </div>
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden px-5 py-20 sm:px-8 lg:px-10 lg:py-28">
          <div className="mx-auto grid max-w-[1440px] gap-10 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:items-center">
            <Reveal className="relative min-h-[430px] overflow-hidden rounded-[2.5rem] border border-[#cfe2d8] bg-[linear-gradient(145deg,rgba(255,255,255,0.82),rgba(232,246,238,0.62))] p-4 shadow-[0_42px_120px_-82px_rgba(16,37,31,0.45)] backdrop-blur-xl sm:min-h-[540px]">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(111,207,151,0.22),transparent_52%)]" />
              <div className="absolute left-6 top-6 rounded-full border border-[#dce5de] bg-white/76 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#2FA084]">
                Live agent network
              </div>
              <div className="relative h-[360px] sm:h-[470px]">
                {canUse3D ? (
                  <AgentCanvasBoundary fallback={<ConstellationFallback />}>
                    <Suspense fallback={<ConstellationFallback />}>
                      <LandingAgentConstellation3D paused={!!reducedMotion} />
                    </Suspense>
                  </AgentCanvasBoundary>
                ) : (
                  <ConstellationFallback />
                )}
              </div>
              <FloatingSystemLabel className="left-6 bottom-6" title="Orchestrator" body="classifies log · ask · action" />
              <FloatingSystemLabel className="right-6 top-20" title="Librarian" body="files structured entries" />
              <FloatingSystemLabel className="right-6 bottom-6" title="Specialists" body="reason over athlete data" />
            </Reveal>

            <div>
              <Reveal>
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-[#2FA084]">System structure</p>
                <h2 className="mt-4 max-w-2xl text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-[#10251f] sm:text-5xl">
                  The support team is software.
                </h2>
                <p className="mt-5 max-w-xl text-base leading-7 text-[#60766f]">
                  SportsMom is not a static dashboard. It is a network of uAgents that turns raw athlete context into filed entries, grounded answers, and safe next actions.
                </p>
              </Reveal>

              <div className="relative mt-10 space-y-4 pl-5">
                <div className="absolute left-[1.05rem] top-4 h-[calc(100%-2rem)] w-px bg-gradient-to-b from-[#2FA084]/20 via-[#2FA084]/34 to-transparent" />
                {workflow.map((step, index) => (
                  <Reveal key={step.title} delay={index * 0.04}>
                    <WorkflowRow {...step} />
                  </Reveal>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="relative px-5 py-20 sm:px-8 lg:px-10 lg:py-28">
          <div className="mx-auto max-w-[1440px]">
            <Reveal className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.32em] text-[#2FA084]">Specialists</p>
              <h2 className="mt-4 text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-[#10251f] sm:text-5xl">
                Focused agents, one coherent athlete story.
              </h2>
              <p className="mt-5 max-w-2xl text-base leading-7 text-[#60766f]">
                Each agent works on a narrow job, then writes its result back to the same record the dashboard and chat use.
              </p>
            </Reveal>

            <div className="mt-12 grid gap-4 lg:grid-cols-5">
              {agents.map((agent, index) => (
                <Reveal key={agent.title} delay={index * 0.035}>
                  <AgentTile {...agent} />
                </Reveal>
              ))}
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-3">
              {outcomeTiles.map((tile, index) => (
                <Reveal key={tile.title} delay={index * 0.04}>
                  <OutcomeTile {...tile} />
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="relative px-5 pb-24 pt-10 sm:px-8 lg:px-10 lg:pb-32">
          <Reveal className="mx-auto max-w-[1120px] overflow-hidden rounded-[2.75rem] border border-[#cfe2d8] bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(232,246,238,0.76))] p-6 text-center shadow-[0_46px_140px_-92px_rgba(16,37,31,0.52)] backdrop-blur-xl sm:p-10 lg:p-14">
            <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-[#2FA084]/10 text-[#2FA084] ring-1 ring-[#2FA084]/18">
              <Sparkles className="size-6" />
            </div>
            <h2 className="mx-auto mt-6 max-w-3xl text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-[#10251f] sm:text-5xl">
              Start with the next log. Let the agents build the system around it.
            </h2>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-[#60766f]">
              Upload voice, photo, or text. Then open the dashboard to see filed entries become recovery signals, trends, calendar context, sponsor drafts, and grounded AI answers.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link
                to="/upload"
                className="inline-flex items-center gap-2 rounded-full bg-[#2FA084] px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_44px_-22px_rgba(47,160,132,0.72)] transition-colors hover:bg-[#268a73]"
              >
                Upload a log
                <ArrowRight className="size-4" />
              </Link>
              <Link
                to="/assistant"
                className="inline-flex items-center gap-2 rounded-full border border-[#dce5de] bg-white/78 px-5 py-3 text-sm font-semibold text-[#10251f] shadow-[0_18px_44px_-34px_rgba(16,37,31,0.32)] transition-colors hover:bg-white"
              >
                Ask AI
              </Link>
            </div>
          </Reveal>
        </section>
      </div>

      <style>{`
        .landing-page .hero-copy {
          position: absolute;
          left: 0;
          top: 50%;
          z-index: 15;
          max-width: min(820px, 92vw);
          color: white;
          font-size: clamp(2.55rem, 7.2vw, 7.35rem);
          line-height: 0.94;
          letter-spacing: 0;
          font-weight: 650;
          opacity: 0;
          text-wrap: balance;
        }

        .landing-page .serve-video {
          filter: blur(0px) brightness(0.78);
          will-change: filter, opacity;
        }

        @media (max-width: 1023px) {
          .landing-page .product-reveal-stage {
            align-content: center;
          }

          .landing-page .product-reveal-copy {
            max-width: 44rem;
          }
        }

        @media (max-width: 640px) {
          .landing-page .hero-copy {
            top: 48%;
            font-size: clamp(2.35rem, 13vw, 4rem);
          }
        }
      `}</style>
    </main>
  );
}

function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px" }}
      transition={{ duration: 0.65, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function GlassPanel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-[2rem] border border-[#dce5de] bg-white/78 shadow-[0_34px_100px_-76px_rgba(16,37,31,0.5)] backdrop-blur-xl ${className}`}
    >
      {children}
    </div>
  );
}

function ProductFrame({
  image,
  alt,
  eyebrow,
  title,
  description,
  labels,
}: {
  image: string;
  alt: string;
  eyebrow: string;
  title: string;
  description: string;
  labels: { text: string; className: string }[];
}) {
  return (
    <GlassPanel className="overflow-hidden p-3 sm:p-4">
      <div className="grid gap-5 lg:grid-cols-[0.74fr_1.26fr] lg:items-center">
        <div className="px-2 py-2 sm:px-4">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#2FA084]">{eyebrow}</p>
          <h3 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-[#10251f]">{title}</h3>
          <p className="mt-4 text-sm leading-6 text-[#60766f]">{description}</p>
        </div>
        <div className="relative min-w-0 rounded-[1.55rem] border border-[#dce5de] bg-[#f7fbf8] p-2 shadow-[0_20px_70px_-46px_rgba(16,37,31,0.45)]">
          <img src={image} alt={alt} className="block max-h-[520px] w-full rounded-[1.2rem] object-contain" loading="lazy" decoding="async" />
          {labels.map((label) => (
            <span
              key={label.text}
              className={`pointer-events-none absolute rounded-full border border-white/70 bg-white/82 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#1F6F5F] shadow-[0_16px_44px_-28px_rgba(16,37,31,0.45)] backdrop-blur-md ${label.className}`}
            >
              {label.text}
            </span>
          ))}
        </div>
      </div>
    </GlassPanel>
  );
}

function HeroFloatCard({
  icon: Icon,
  title,
  value,
  className,
}: {
  icon: LucideIcon;
  title: string;
  value: string;
  className: string;
}) {
  return (
    <div
      className={`absolute rounded-2xl border border-white/34 bg-white/82 p-3 text-[#10251f] opacity-0 shadow-[0_20px_70px_-44px_rgba(0,0,0,0.75)] backdrop-blur-xl ${className}`}
    >
      <div className="flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-xl bg-[#2FA084]/10 text-[#2FA084]">
          <Icon className="size-4" />
        </span>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#60766f]">{title}</div>
          <div className="text-sm font-semibold">{value}</div>
        </div>
      </div>
    </div>
  );
}

function WorkflowRow({ kicker, title, body, icon: Icon }: StoryStep) {
  return (
    <div className="relative rounded-[1.5rem] border border-[#dce5de] bg-white/78 p-5 pl-6 shadow-[0_20px_60px_-48px_rgba(16,37,31,0.42)] backdrop-blur-xl">
      <span className="absolute -left-[1.18rem] top-6 grid size-9 place-items-center rounded-full border border-[#cfe2d8] bg-white text-[#2FA084] shadow-[0_12px_36px_-24px_rgba(16,37,31,0.45)]">
        <Icon className="size-4.5" />
      </span>
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2FA084]">{kicker}</p>
      <h3 className="mt-2 text-lg font-semibold tracking-tight text-[#10251f]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#60766f]">{body}</p>
    </div>
  );
}

function AgentTile({ title, body, icon: Icon }: AgentCard) {
  return (
    <article className="group relative min-h-[230px] overflow-hidden rounded-[1.7rem] border border-[#dce5de] bg-white/76 p-5 shadow-[0_24px_74px_-56px_rgba(16,37,31,0.42)] backdrop-blur-xl transition-transform duration-200 hover:-translate-y-1">
      <div className="absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_70%_0%,rgba(111,207,151,0.24),transparent_62%)]" />
      <span className="relative grid size-11 place-items-center rounded-2xl bg-[#6FCF97]/14 text-[#2FA084] ring-1 ring-[#2FA084]/12">
        <Icon className="size-5" strokeWidth={1.8} />
      </span>
      <h3 className="relative mt-8 text-lg font-semibold tracking-tight text-[#10251f]">{title}</h3>
      <p className="relative mt-3 text-sm leading-6 text-[#60766f]">{body}</p>
    </article>
  );
}

function OutcomeTile({ title, body, icon: Icon }: AgentCard) {
  return (
    <article className="rounded-[1.7rem] border border-[#dce5de] bg-[linear-gradient(145deg,rgba(255,255,255,0.86),rgba(240,249,244,0.72))] p-5 shadow-[0_24px_80px_-64px_rgba(16,37,31,0.4)] backdrop-blur-xl">
      <div className="flex items-start gap-4">
        <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-[#2FA084]/10 text-[#2FA084]">
          <Icon className="size-5" />
        </span>
        <div>
          <h3 className="text-base font-semibold tracking-tight text-[#10251f]">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-[#60766f]">{body}</p>
        </div>
      </div>
    </article>
  );
}

function FloatingSystemLabel({ className, title, body }: { className: string; title: string; body: string }) {
  return (
    <div className={`absolute max-w-[11rem] rounded-2xl border border-[#dce5de] bg-white/78 p-3 shadow-[0_20px_70px_-52px_rgba(16,37,31,0.5)] backdrop-blur-xl ${className}`}>
      <div className="text-xs font-semibold text-[#10251f]">{title}</div>
      <div className="mt-1 text-[11px] leading-4 text-[#60766f]">{body}</div>
    </div>
  );
}

function ConstellationFallback() {
  return (
    <div className="relative grid h-full place-items-center">
      <div className="size-40 rounded-full border border-[#2FA084]/20 bg-[#2FA084]/8 shadow-[0_0_80px_rgba(111,207,151,0.22)]" />
      <div className="absolute size-72 rounded-full border border-dashed border-[#2FA084]/18" />
      <div className="absolute size-96 rounded-full border border-dashed border-[#2FA084]/10" />
    </div>
  );
}
