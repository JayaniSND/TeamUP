import { memo } from "react";
import { HeartPulse, Moon, Gauge } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { AgentInsight, RecoverySignal } from "@/types/athlete";

/**
 * Recovery = wellness / self-management. Strictly non-medical language:
 * "recovery signal", "risk pattern", "suggested adjustment".
 */
export const RecoveryPanel = memo(function RecoveryPanel({
  recovery,
  insight,
  onAction,
}: {
  recovery: RecoverySignal;
  insight?: AgentInsight;
  onAction: () => void;
}) {
  return (
    <section
      id="recovery"
      className="glass-card fade-up min-h-0 overflow-hidden rounded-[1.45rem] p-3"
      style={{ animationDelay: "0.1s" }}
    >
      <header className="mb-2 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="glass-chip grid size-7 shrink-0 place-items-center rounded-xl text-text-muted">
            <HeartPulse className="size-4" strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-text">Recovery</h2>
            <p className="truncate text-[10px] text-text-dim">Wellness signal</p>
          </div>
        </div>
        <button
          onClick={onAction}
          className="glass-chip shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold text-text transition-colors hover:bg-accent/7"
        >
          Check
        </button>
      </header>

      <div className="glass-inset mb-2 flex items-center justify-between gap-2 rounded-[1.05rem] px-2.5 py-1.5">
        <div>
          <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-text-muted">Risk</div>
          <div className="mt-1">
            <Badge status={recovery.risk} className="px-2 py-0.5 text-[10px]">
              {recovery.riskLabel}
            </Badge>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[9px] uppercase tracking-wider text-text-dim">Signal</div>
          <div className="mt-0.5 text-sm font-semibold text-warning">{recovery.focusArea}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="glass-inset rounded-xl p-2">
          <div className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-text-dim">
            <Gauge className="size-3" /> Fatigue
          </div>
          <div className="tnum mt-0.5 text-base font-semibold text-text">{recovery.fatigueLevel}%</div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/95 ring-1 ring-accent/14">
            <div className="h-full rounded-full bg-warning" style={{ width: `${recovery.fatigueLevel}%` }} />
          </div>
        </div>
        <div className="glass-inset rounded-xl p-2">
          <div className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-text-dim">
            <Moon className="size-3" /> Sleep
          </div>
          <div className="tnum mt-0.5 text-base font-semibold text-text">
            {recovery.sleepHours}
            <span className="ml-0.5 text-xs font-medium text-text-muted">h</span>
          </div>
          <div className="truncate text-[9px] text-text-dim">Below target</div>
        </div>

        <div className="glass-inset rounded-xl p-2">
          <div className="mb-1 flex items-center justify-between text-[9px] uppercase tracking-wider">
            <span className="truncate text-text-dim">Soreness</span>
            <span className="font-semibold text-warning">Up</span>
          </div>
          <div className="flex h-7 items-end gap-1">
            {recovery.sorenessTrend.map((d) => (
              <span
                key={d.day}
                title={`${d.day}: ${d.value}`}
                className="flex-1 rounded-t bg-gradient-to-t from-[#2563eb]/70 to-[#38bdf8]/70 shadow-[0_0_10px_rgba(37,99,235,0.16)]"
                style={{ height: `${Math.max(18, d.value)}%` }}
              />
            ))}
          </div>
        </div>
      </div>

      {insight && (
        <div className="mt-2 truncate rounded-xl bg-accent/[0.06] px-2.5 py-1.5 text-[10px] leading-relaxed text-text-muted ring-1 ring-ai/16">
          <span className="font-semibold text-ai">Suggested adjustment · </span>
          {insight.suggestion}
        </div>
      )}
    </section>
  );
});
