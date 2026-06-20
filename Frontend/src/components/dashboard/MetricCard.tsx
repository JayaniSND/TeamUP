import { memo } from "react";
import { cn } from "@/lib/utils";
import { resolveIcon } from "@/lib/icons";
import { statusStyles } from "@/components/ui/Badge";
import type { OverviewMetric } from "@/types/athlete";

/**
 * Hover lift is pure CSS (`.card-hover`) and entrance is a CSS keyframe — no
 * framer-motion `whileHover` driving transforms per frame (that was the lag).
 * memo keeps it from re-rendering when the dashboard's nav/chat state changes.
 */
export const MetricCard = memo(function MetricCard({
  metric,
  delay = 0,
}: {
  metric: OverviewMetric;
  delay?: number;
}) {
  const Icon = resolveIcon(metric.icon);
  const s = statusStyles[metric.status];
  const gradient =
    metric.status === "positive"
      ? "grad-lime"
      : metric.status === "warning"
        ? "grad-peach"
        : metric.status === "ai"
          ? "grad-sky"
          : "bg-white/44";
  const onGradient = metric.status === "warning";

  return (
    <div
      style={delay ? { animationDelay: `${delay}s` } : undefined}
      className={cn("glass-card card-hover fade-up group relative min-h-[104px] overflow-hidden rounded-[1.45rem] p-3.5", gradient)}
    >
      <div className="mesh-lines pointer-events-none absolute inset-0 opacity-25" />
      <div className={cn("pointer-events-none absolute -right-8 -top-8 size-24 rounded-full opacity-45", s.bg)} />
      <div className="relative flex items-center justify-between">
        <span className={cn("text-xs font-semibold uppercase tracking-[0.18em]", onGradient ? "text-white/78" : "text-text-muted")}>
          {metric.label}
        </span>
        <span
          className={cn(
            "grid size-8 place-items-center rounded-xl ring-1 backdrop-blur-md",
            onGradient ? "bg-white/20 text-white ring-white/35" : [s.bg, s.text, s.ring]
          )}
        >
          <Icon className="size-4" strokeWidth={2} />
        </span>
      </div>
      <div className="relative mt-3">
        <div className={cn("tnum truncate text-[2rem] font-semibold leading-none tracking-tight", onGradient ? "text-white" : "text-text")}>
          {metric.value}
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 text-[11px] font-medium">
          <span className={cn("size-1.5 shrink-0 rounded-full", onGradient ? "bg-lime shadow-[0_0_12px_rgba(217,255,47,0.9)]" : s.dot)} />
          <span className={cn("truncate", onGradient ? "text-white/78" : "text-text-dim")}>{metric.detail}</span>
        </div>
      </div>
    </div>
  );
});
