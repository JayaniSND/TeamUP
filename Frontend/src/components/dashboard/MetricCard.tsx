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
  onClick,
  ariaLabel,
}: {
  metric: OverviewMetric;
  delay?: number;
  onClick?: () => void;
  ariaLabel?: string;
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
          : "bg-white";

  const content = (
    <>
      <div className="mesh-lines pointer-events-none absolute inset-0 opacity-25" />
      <div className={cn("pointer-events-none absolute -right-8 -top-8 size-24 rounded-full opacity-45", s.bg)} />
      <div className="relative flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">{metric.label}</span>
        <span className={cn("grid size-8 place-items-center rounded-xl ring-1 backdrop-blur-md", s.bg, s.text, s.ring)}>
          <Icon className="size-4" strokeWidth={2} />
        </span>
      </div>
      <div className="relative mt-3">
        <div className="tnum truncate text-[2rem] font-semibold leading-none tracking-tight text-text">{metric.value}</div>
        <div className="mt-1.5 flex items-center gap-1.5 text-[11px] font-medium">
          <span className={cn("size-1.5 shrink-0 rounded-full", s.dot)} />
          <span className="truncate text-text-dim">{metric.detail}</span>
        </div>
      </div>
    </>
  );

  const className = cn(
    "glass-card card-hover fade-up group relative min-h-[104px] overflow-hidden rounded-[1.45rem] p-3.5 text-left",
    onClick && "w-full cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35",
    gradient
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel ?? metric.label}
        style={delay ? { animationDelay: `${delay}s` } : undefined}
        className={className}
      >
        {content}
      </button>
    );
  }

  return (
    <div style={delay ? { animationDelay: `${delay}s` } : undefined} className={className}>
      {content}
    </div>
  );
});
