import { memo } from "react";
import { Dumbbell, Clock, Target } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { cn } from "@/lib/utils";
import type { AthleteData, TrainingSession } from "@/types/athlete";

const intensityStatus: Record<TrainingSession["intensity"], string> = {
  Low: "text-positive",
  Moderate: "text-accent",
  High: "text-warning",
  Peak: "text-negative",
};

export const TrainingPanel = memo(function TrainingPanel({
  training,
  onAction,
  onSummarize,
}: {
  training: AthleteData["training"];
  onAction: () => void;
  onSummarize: () => void;
}) {
  const hrs = Math.floor(training.weeklyTotalMin / 60);
  const mins = training.weeklyTotalMin % 60;

  return (
    <SectionCard
      id="training"
      title="Training"
      subtitle="Recent sessions & weekly load"
      icon={Dumbbell}
      action="Generate next week's plan"
      onAction={onAction}
      secondaryAction="Summarize 7 days"
      onSecondary={onSummarize}
      delay={0.1}
    >
      <div className="glass-inset mb-4 flex items-center justify-between rounded-[1.35rem] px-4 py-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Weekly Total
          </div>
          <div className="tnum mt-0.5 text-2xl font-semibold text-text">
            {hrs}h {mins}m
          </div>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-warning/12 px-2.5 py-1 text-xs font-semibold text-warning ring-1 ring-warning/25">
          <Clock className="size-3.5" />
          High load week
        </div>
      </div>

      <ul className="space-y-2.5">
        {training.sessions.map((s) => (
          <li
            key={s.id}
            className="glass-inset flex items-center gap-3 rounded-2xl p-3 transition-colors hover:bg-white/56"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-white/46 text-text-muted ring-1 ring-white/60">
              <Dumbbell className="size-4" strokeWidth={1.75} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-text">{s.focus}</div>
              <div className="mt-0.5 flex items-center gap-2 text-[11px] text-text-dim">
                <span>{s.date}</span>
                <span>·</span>
                <span className="tnum">{s.durationMin} min</span>
              </div>
            </div>
            <span className={cn("rounded-full bg-white/44 px-2 py-1 text-xs font-semibold ring-1 ring-white/55", intensityStatus[s.intensity])}>
              {s.intensity}
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex items-start gap-2 rounded-2xl bg-ai/[0.07] p-3 text-xs ring-1 ring-ai/15">
        <Target className="mt-0.5 size-3.5 shrink-0 text-ai" />
        <p className="leading-relaxed text-text-muted">
          <span className="font-semibold text-ai">Suggested next focus · </span>
          {training.suggestedFocus}
        </p>
      </div>
    </SectionCard>
  );
});
