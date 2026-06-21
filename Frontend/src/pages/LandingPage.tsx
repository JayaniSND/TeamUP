import { useEffect, useLayoutEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  ArrowRight,
  Bot,
  Camera,
  CalendarDays,
  FileText,
  Handshake,
  HeartPulse,
  Mic,
  Plane,
  ShieldCheck,
  Sparkles,
  Trophy,
  Zap,
} from "lucide-react";

gsap.registerPlugin(ScrollTrigger);

const dashboardCards = [
  { label: "Weekly Load", value: "238m", detail: "3 focused sessions", icon: Zap },
  { label: "Recovery Risk", value: "Low", detail: "Sleep + mobility stable", icon: HeartPulse },
  { label: "Serve Trend", value: "+8%", detail: "First-serve accuracy", icon: Trophy },
  { label: "Recent Result", value: "6-4", detail: "Closed second set cleanly", icon: ShieldCheck },
  { label: "Next Event", value: "Jun 28", detail: "San Jose tune-up", icon: CalendarDays },
  { label: "AI Focus", value: "Serve", detail: "Protect knee load", icon: Bot },
  { label: "Match History", value: "5-2", detail: "Last seven matches", icon: FileText },
  { label: "Sponsorship Fit", value: "92%", detail: "Baseline Athletics", icon: Handshake },
];

const flowSteps = ["Raw Input", "Parser", "Entries", "Database"];

const agentCards = [
  { title: "Recovery", body: "Flags soreness patterns before they become training blockers.", icon: HeartPulse },
  { title: "Performance", body: "Connects match results with session load and technical focus.", icon: Trophy },
  { title: "Logistics", body: "Keeps events, travel, and schedule pressure visible.", icon: Plane },
  { title: "Sponsorship", body: "Finds brand-fit opportunities from real athlete momentum.", icon: Handshake },
  { title: "Coaching", body: "Turns recurring notes into next-session priorities.", icon: Sparkles },
];

export default function LandingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const heroRef = useRef<HTMLElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

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
      const videoProgress = Math.min(progress / 0.65, 1);
      video.currentTime = video.duration * videoProgress;
    };

    const refreshOnMetadata = () => ScrollTrigger.refresh();
    video.addEventListener("loadedmetadata", refreshOnMetadata);

    const ctx = gsap.context(() => {
      const heroTL = gsap.timeline({
        scrollTrigger: {
          trigger: hero,
          start: "top top",
          end: "+=5000",
          scrub: true,
          pin: true,
          anticipatePin: 1,
          onUpdate: (self) => syncVideoToScroll(self.progress),
        },
      });

      heroTL
        .fromTo(".copy-1", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.08 }, 0.03)
        .to(".copy-1", { opacity: 0, y: -20, duration: 0.06 }, 0.18)
        .fromTo(".copy-2", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.08 }, 0.22)
        .to(".copy-2", { opacity: 0, y: -20, duration: 0.06 }, 0.38)
        .fromTo(".copy-3", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.08 }, 0.42)
        .to(".copy-3", { opacity: 0, y: -20, duration: 0.06 }, 0.6)
        .fromTo(".impact-flash", { opacity: 0 }, { opacity: 1, duration: 0.03 }, 0.66)
        .to(".impact-flash", { opacity: 0, duration: 0.08 }, 0.69)
        .fromTo(
          ".racket-wipe",
          { xPercent: -130, opacity: 0 },
          { xPercent: 125, opacity: 1, duration: 0.12 },
          0.66
        )
        .to(".racket-wipe", { opacity: 0, duration: 0.06 }, 0.76)
        .to(".serve-video", { opacity: 0.35, filter: "blur(6px) brightness(0.52)", duration: 0.16 }, 0.72)
        .fromTo(".product-reveal-copy", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.12 }, 0.73)
        .fromTo(
          ".real-dashboard-layer",
          { opacity: 0, y: 80, scale: 0.96 },
          { opacity: 1, y: 0, scale: 1, duration: 0.2 },
          0.74
        );
    }, hero);

    return () => {
      video.removeEventListener("loadedmetadata", refreshOnMetadata);
      ctx.revert();
    };
  }, []);

  return (
    <main className="landing-page min-h-screen bg-[#f4f7f4] text-[#0d211b]">
      <section ref={heroRef} className="serve-hero relative h-screen overflow-hidden">
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

        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(255,255,255,0.1),transparent_34%),linear-gradient(90deg,rgba(5,15,12,0.78),rgba(8,25,20,0.42)_48%,rgba(5,15,12,0.72))]" />
        <div className="impact-flash pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_52%_42%,rgba(255,255,255,0.98),rgba(111,207,151,0.52)_28%,transparent_58%)] opacity-0" />
        <div className="racket-wipe pointer-events-none absolute -left-1/4 top-[-18%] h-[140%] w-1/3 rotate-[18deg] bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.86),rgba(111,207,151,0.42),transparent)] opacity-0 blur-[1px]" />

        <div className="relative z-10 mx-auto flex h-full max-w-7xl flex-col px-5 py-5 sm:px-8 lg:px-10">
          <nav className="flex shrink-0 items-center justify-between">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/10 px-3 py-2 text-sm font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-md">
              <span className="grid size-7 place-items-center rounded-full bg-[#6FCF97]/18 text-[#6FCF97]">
                <Sparkles className="size-3.5" />
              </span>
              SportsMom
            </div>
            <Link
              to="/dashboard"
              className="rounded-full border border-white/18 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/18"
            >
              Dashboard
            </Link>
          </nav>

          <div className="relative flex min-h-0 flex-1 items-center">
            <div className="hero-copy copy-1">Turn every session into athletic intelligence.</div>
            <div className="hero-copy copy-2">Log naturally with voice, photos, and text.</div>
            <div className="hero-copy copy-3">Messy training notes become structured data.</div>

            <div className="product-reveal-copy absolute left-0 top-[12%] max-w-[27rem] opacity-0">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#9de5ba]">SportsMom</p>
              <h1 className="mt-3 text-balance text-4xl font-semibold leading-[1.04] tracking-tight text-white sm:text-5xl">
                The athlete dashboard that builds itself from your logs.
              </h1>
            </div>

            <div className="real-dashboard-layer ml-auto w-full max-w-[860px] opacity-0">
              <div className="rounded-[2rem] border border-white/18 bg-white/94 p-3 shadow-[0_38px_120px_-70px_rgba(0,0,0,0.88)] backdrop-blur-xl sm:p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-[#dce5de] pb-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[#2FA084]">Maya Chen</div>
                    <div className="mt-1 text-xl font-semibold tracking-tight text-[#10251f]">Training Intelligence</div>
                  </div>
                  <div className="rounded-full bg-[#2FA084]/10 px-3 py-1.5 text-xs font-semibold text-[#1F6F5F]">
                    Live from logs
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {dashboardCards.map((card) => (
                    <article key={card.label} className="rounded-2xl border border-[#dce5de] bg-white p-3 shadow-[0_14px_34px_-28px_rgba(16,37,31,0.42)]">
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <span className="truncate text-[10px] font-semibold uppercase tracking-[0.16em] text-[#688078]">
                          {card.label}
                        </span>
                        <span className="grid size-7 shrink-0 place-items-center rounded-xl bg-[#6FCF97]/14 text-[#2FA084]">
                          <card.icon className="size-3.5" />
                        </span>
                      </div>
                      <div className="truncate text-2xl font-semibold tracking-tight text-[#10251f]">{card.value}</div>
                      <p className="mt-1 truncate text-xs text-[#60766f]">{card.detail}</p>
                    </article>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-5 py-20 sm:px-8 lg:grid-cols-[0.82fr_1.18fr] lg:px-10">
        <SectionIntro eyebrow="Log naturally" title="Capture the way athletes actually think after training." />
        <div className="grid gap-3 sm:grid-cols-3">
          <FeatureCard icon={Camera} title="Notebook photo" body="Snap paper notes and pull the important details forward." />
          <FeatureCard icon={Mic} title="Voice entry" body="Talk through practice while the session is still fresh." />
          <FeatureCard icon={FileText} title="Text input" body="Paste quick notes without forcing a rigid form." />
        </div>
      </section>

      <section className="border-y border-[#dfe7e1] bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-20 sm:px-8 lg:grid-cols-[0.9fr_1.1fr] lg:px-10">
          <SectionIntro eyebrow="Structured automatically" title="Raw notes become clean entries without extra admin work." />
          <div className="grid gap-3 sm:grid-cols-4">
            {flowSteps.map((step, index) => (
              <div key={step} className="rounded-3xl border border-[#dce5de] bg-[#f8faf8] p-4">
                <div className="mb-8 grid size-9 place-items-center rounded-2xl bg-[#2FA084]/10 text-sm font-semibold text-[#1F6F5F]">
                  {index + 1}
                </div>
                <div className="text-sm font-semibold text-[#10251f]">{step}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-10">
        <SectionIntro eyebrow="Agents find patterns" title="Specialists watch recovery, performance, logistics, sponsors, and coaching." />
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {agentCards.map((agent) => (
            <FeatureCard key={agent.title} icon={agent.icon} title={agent.title} body={agent.body} />
          ))}
        </div>
      </section>

      <section className="bg-[#10251f] px-5 py-20 text-white sm:px-8 lg:px-10">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.8fr_1.2fr]">
          <SectionIntro eyebrow="Ask AI" title="A coach-like chat grounded in athlete history, not generic advice." dark />
          <div className="rounded-[2rem] border border-white/12 bg-white/8 p-4 shadow-[0_30px_80px_-64px_rgba(0,0,0,0.85)]">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-[#6FCF97]/12 px-3 py-1.5 text-xs font-semibold text-[#9de5ba]">
              <Bot className="size-3.5" />
              Grounded in 42 logs
            </div>
            <div className="space-y-3">
              <div className="max-w-[78%] rounded-3xl bg-white/12 px-4 py-3 text-sm text-white/82">
                Why did my serve drop off late last week?
              </div>
              <div className="ml-auto max-w-[86%] rounded-3xl bg-white px-4 py-3 text-sm leading-relaxed text-[#10251f]">
                Your serve accuracy dipped on the same days your load climbed and recovery was lowest. Keep the technical serve work, but swap one conditioning block for mobility before match play.
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 text-center sm:px-8 lg:px-10">
        <div className="mx-auto max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#2FA084]">Start simple</p>
          <h2 className="mt-3 text-4xl font-semibold tracking-tight text-[#10251f]">See the dashboard in action.</h2>
          <p className="mt-3 text-base leading-relaxed text-[#5d726b]">
            Open the product dashboard and see how logs become useful athlete intelligence.
          </p>
          <Link
            to="/dashboard"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-[#2FA084] px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_44px_-22px_rgba(47,160,132,0.72)] transition-colors hover:bg-[#268a73]"
          >
            Go to dashboard
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      <style>{`
        .landing-page .hero-copy {
          position: absolute;
          left: 0;
          max-width: 760px;
          color: white;
          font-size: clamp(2.7rem, 7vw, 7rem);
          line-height: 0.96;
          letter-spacing: 0;
          font-weight: 650;
          opacity: 0;
          text-wrap: balance;
        }

        .landing-page .serve-video {
          filter: blur(0px) brightness(0.78);
          will-change: filter, opacity;
        }

        @media (max-width: 900px) {
          .landing-page .real-dashboard-layer {
            margin-left: 0;
            align-self: flex-end;
          }

          .landing-page .product-reveal-copy {
            top: 8%;
          }
        }
      `}</style>
    </main>
  );
}

function SectionIntro({
  eyebrow,
  title,
  dark = false,
}: {
  eyebrow: string;
  title: string;
  dark?: boolean;
}) {
  return (
    <div>
      <p className={dark ? "text-xs font-semibold uppercase tracking-[0.24em] text-[#9de5ba]" : "text-xs font-semibold uppercase tracking-[0.24em] text-[#2FA084]"}>
        {eyebrow}
      </p>
      <h2 className={dark ? "mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl" : "mt-3 text-3xl font-semibold tracking-tight text-[#10251f] sm:text-4xl"}>
        {title}
      </h2>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Mic;
  title: string;
  body: string;
}) {
  return (
    <article className="rounded-[1.5rem] border border-[#dce5de] bg-white p-5 shadow-[0_18px_44px_-34px_rgba(16,37,31,0.32)]">
      <span className="grid size-10 place-items-center rounded-2xl bg-[#6FCF97]/14 text-[#2FA084]">
        <Icon className="size-5" strokeWidth={1.8} />
      </span>
      <h3 className="mt-5 text-base font-semibold tracking-tight text-[#10251f]">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-[#60766f]">{body}</p>
    </article>
  );
}
