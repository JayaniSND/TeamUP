import { memo, type ReactNode } from "react";
import { type LucideIcon, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

/**
 * The shared glass shell every section sits in. Guarantees a consistent
 * header + section-level AI action affordance across the whole dashboard.
 *
 * Entrance is a CSS keyframe (`.fade-up`) not framer-motion, and the component
 * is memoized — so unrelated dashboard state changes never re-render it.
 */
export const SectionCard = memo(function SectionCard({
  id,
  title,
  subtitle,
  icon: Icon,
  action,
  onAction,
  secondaryAction,
  onSecondary,
  className,
  children,
  delay = 0,
}: {
  /** anchor id for sidebar scroll-nav */
  id?: string;
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  /** label for the contextual AI action button, e.g. "Explain trend" */
  action?: string;
  onAction?: () => void;
  /** optional secondary (non-AI) action, e.g. "Summarize 7 days" */
  secondaryAction?: string;
  onSecondary?: () => void;
  className?: string;
  children: ReactNode;
  delay?: number;
}) {
  return (
    <section
      id={id}
      style={delay ? { animationDelay: `${delay}s` } : undefined}
      className={cn(
        "glass-card fade-up flex min-h-0 scroll-mt-24 flex-col overflow-hidden rounded-[1.45rem] p-3.5 sm:p-4 lg:scroll-mt-8",
        className
      )}
    >
      <header className="mb-3 flex flex-col gap-2 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <div className="flex min-w-0 items-center gap-2.5">
          {Icon && (
            <span className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-text-muted">
              <Icon className="size-4.5" strokeWidth={1.75} />
            </span>
          )}
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold tracking-tight text-white">{title}</h2>
            {subtitle && <p className="mt-0.5 truncate text-[11px] leading-relaxed text-text-dim">{subtitle}</p>}
          </div>
        </div>
        {(action || secondaryAction) && (
          <div className="flex shrink-0 flex-wrap items-center gap-1.5 2xl:justify-end">
            {secondaryAction && (
              <Button variant="ghost" size="sm" onClick={onSecondary}>
                {secondaryAction}
              </Button>
            )}
            {action && (
              <Button variant="ai" size="sm" onClick={onAction}>
                <Sparkles className="size-3.5" />
                {action}
              </Button>
            )}
          </div>
        )}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
});
