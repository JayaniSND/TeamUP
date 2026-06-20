import { memo } from "react";
import { Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { AgentInsight } from "@/types/athlete";

/**
 * Compact alert panel for the autonomous agent layer: one recommended action
 * plus two tiny agent signals, so the default dashboard stays one-glance.
 */
export const AgentInsightsStrip = memo(function AgentInsightsStrip({
  insights,
  onAsk,
  delay = 0,
}: {
  insights: AgentInsight[];
  onAsk: (prompt: string, replyId?: string) => void;
  delay?: number;
}) {
  const [featured] = insights;
  const signals = insights.slice(1, 3);

  return (
    <section
      id="insights"
      style={delay ? { animationDelay: `${delay}s` } : undefined}
      className="glass-card fade-up min-h-[104px] overflow-hidden rounded-[1.45rem] p-3.5"
    >
      <div className="flex items-start gap-3">
        <span className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-ai">
          <Sparkles className="size-4" strokeWidth={2} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-text">Next Action</h2>
              <p className="mt-0.5 truncate text-[10px] font-medium text-text-dim">Highest-leverage agent signal</p>
            </div>
            {featured?.action && (
              <button
                onClick={() => onAsk(featured.action!.prompt, featured.action!.replyId)}
                className="glass-chip shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold text-text transition-colors hover:bg-accent/7"
              >
                Apply
              </button>
            )}
          </div>

          {featured && <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-text-muted">{featured.suggestion}</p>}

          <div className="mt-2 flex flex-wrap gap-1.5">
            {signals.map((insight) => (
              <button
                key={insight.id}
                onClick={() => insight.action && onAsk(insight.action.prompt, insight.action.replyId)}
                className="transition-colors hover:brightness-110"
              >
                <Badge status={insight.status} className="px-2 py-0.5 text-[10px]">
                  {insight.agent}
                </Badge>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
});
