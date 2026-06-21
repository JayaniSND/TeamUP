import { memo } from "react";
import { Sparkles, ArrowRight, Target, Activity, HeartPulse, TimerReset } from "lucide-react";
import type { AthleteProfile, SeasonGoal } from "@/types/athlete";

/**
 * The single focal gradient card (per the design system's "one strong gradient"
 * budget). Left: this week's AI focus + CTA. Right: a frosted season-goal card.
 * Entrance is CSS (`.fade-up`); decoration is static (no per-frame work).
 */
export const Hero = memo(function Hero({
  profile,
  goal,
  onAskAI,
}: {
  profile: AthleteProfile;
  goal: SeasonGoal;
  onAskAI: () => void;
}) {
  return (
    <section className="glass-card fade-up relative min-h-[360px] overflow-hidden rounded-[2.15rem] p-5 sm:p-7">
      <div className="mesh-lines pointer-events-none absolute inset-0 opacity-60" />
      <div className="pointer-events-none absolute inset-x-8 bottom-0 h-20 bg-gradient-to-t from-accent/12 to-transparent" />
      <div className="pointer-events-none absolute bottom-8 left-8 right-8 hidden h-28 items-end gap-2 opacity-55 sm:flex">
        {[34, 48, 42, 70, 52, 86, 74, 96, 78, 66, 88, 58].map((h, i) => (
          <span
            key={i}
            className="flex-1 rounded-t-xl bg-gradient-to-t from-white/10 via-lime/24 to-accent/42 shadow-[0_0_20px_rgba(111,207,151,0.16)]"
            style={{ height: `${h}%` }}
          />
        ))}
        <svg className="absolute inset-x-0 bottom-6 h-20 w-full overflow-visible" viewBox="0 0 640 120" preserveAspectRatio="none">
          <path
            d="M0 86 C70 28 115 118 180 62 C248 4 302 105 375 46 C454 -18 505 86 640 36"
            fill="none"
            stroke="rgba(255,255,255,0.44)"
            strokeWidth="3"
          />
          <path
            d="M0 96 C84 60 118 106 190 76 C264 42 296 112 386 68 C472 26 520 80 640 58"
            fill="none"
            stroke="rgba(255,158,223,0.38)"
            strokeWidth="2"
          />
        </svg>
      </div>

      <div className="pointer-events-none absolute right-[15%] top-10 hidden h-[18rem] w-[12rem] sm:block">
        <div className="absolute left-12 top-0 size-24 rounded-full bg-[radial-gradient(circle_at_62%_35%,rgba(255,255,255,0.62),rgba(18,16,18,0.5)_58%,rgba(18,16,18,0.04)_78%)] blur-[0.2px]" />
        <div className="absolute left-9 top-20 h-56 w-32 rounded-[50%_50%_44%_44%] bg-[radial-gradient(circle_at_56%_16%,rgba(35,29,28,0.5),rgba(79,72,68,0.22)_46%,rgba(255,255,255,0.02)_78%)] blur-[1px]" />
        <div className="absolute left-0 top-[9.5rem] h-28 w-52 rounded-[50%] bg-[radial-gradient(circle_at_50%_35%,rgba(42,36,34,0.22),rgba(255,255,255,0)_72%)] blur-xl" />
      </div>

      <div className="relative z-[1] flex min-h-[306px] flex-col justify-between">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/12 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted">
              <span className="size-1.5 rounded-full bg-lime shadow-[0_0_14px_rgba(217,255,47,0.9)]" />
              {profile.currentWeek}
            </div>
            <h2 className="mt-5 max-w-[18rem] text-4xl font-semibold leading-[0.96] tracking-tight text-white sm:text-5xl">
              {profile.name}
            </h2>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-text-muted">
              Serve work is trending up while the right-knee recovery signal is asking for a smarter load before San Jose.
            </p>
          </div>

          <button
            onClick={onAskAI}
            className="card-hover glass-chip hidden h-11 shrink-0 items-center gap-2 rounded-2xl px-4 text-sm font-semibold text-text sm:inline-flex"
          >
            <Sparkles className="size-4 text-ai" />
            Ask AI
            <ArrowRight className="size-4 text-text-dim" />
          </button>
        </div>

        <div className="pointer-events-none absolute left-[53%] top-[42%] hidden -translate-x-1/2 -translate-y-1/2 sm:block">
          <div className="grid size-9 place-items-center rounded-full bg-lime/80 text-text shadow-[0_0_0_10px_rgba(217,255,47,0.16),0_0_28px_rgba(217,255,47,0.65)]">
            <HeartPulse className="size-4" strokeWidth={2} />
          </div>
          <div className="absolute left-8 top-4 h-px w-24 rotate-[-10deg] bg-text/12" />
          <div className="glass-chip absolute left-28 top-[-16px] w-36 rounded-2xl px-3 py-2">
            <div className="tnum text-2xl font-semibold leading-none text-white">55</div>
            <div className="mt-1 text-[11px] font-medium text-text-muted">recovery score</div>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_17rem]">
          <div className="glass-inset rounded-[1.45rem] p-3.5">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-white">Today's Data</div>
              <div className="hidden items-center gap-3 text-[11px] font-medium text-text-dim sm:flex">
                <span className="flex items-center gap-1.5">
                  <Activity className="size-3.5" /> Load
                </span>
                <span className="flex items-center gap-1.5">
                  <TimerReset className="size-3.5" /> Recovery
                </span>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
              <span className="tnum text-xs font-semibold text-text-muted">12:55</span>
              <div className="relative h-10 overflow-hidden rounded-2xl bg-white/12 ring-1 ring-white/22">
                <div className="absolute inset-y-1 left-[4%] w-[68%] rounded-xl bg-gradient-to-r from-[#6d9b69]/86 via-[#b2c776]/78 to-lime/80 shadow-[inset_0_1px_0_rgba(255,255,255,0.62)]" />
                {[16, 42, 66, 84].map((x) => (
                  <span
                    key={x}
                    className="absolute top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-white shadow-[0_0_0_4px_rgba(255,255,255,0.22)]"
                    style={{ left: `${x}%` }}
                  />
                ))}
                <span className="absolute left-[22%] top-1/2 size-2.5 -translate-y-1/2 rounded-full bg-lime shadow-[0_0_18px_rgba(217,255,47,0.85)]" />
              </div>
              <span className="tnum text-xs font-semibold text-text-muted">13:20</span>
            </div>
          </div>

          <div className="glass-inset rounded-[1.45rem] p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-text-dim">
              <Target className="size-3.5 text-accent" strokeWidth={2} />
              Season Goal
            </div>
            <div className="mt-2 text-base font-semibold text-white">{goal.title}</div>
            <div className="mt-4 flex items-center justify-between text-[11px] font-medium text-text-muted">
              <span>{goal.detail}</span>
              <span className="tnum font-semibold text-white">{goal.progressPct}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/16 ring-1 ring-white/22">
              <div
                className="h-full rounded-full bg-gradient-to-r from-accent via-ai to-lime"
                style={{ width: `${goal.progressPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
});
