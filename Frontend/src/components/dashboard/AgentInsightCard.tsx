import { memo } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { resolveIcon } from "@/lib/icons";
import { Badge, statusStyles } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { AgentInsight, AgentName } from "@/types/athlete";

const agentIcon: Record<AgentName, string> = {
  Recovery: "HeartPulse",
  Logistics: "Plane",
  Scout: "TrendingUp",
  Orchestrator: "Sparkles",
  Librarian: "BookOpen",
};

/**
 * A card that names the agent that produced an insight — this is what makes the
 * underlying agent network legible. Used in-context (Recovery panel) and in the
 * Agent Insights strip. Pass `onAction` to wire its one-tap question into chat.
 */
export const AgentInsightCard = memo(function AgentInsightCard({
  insight,
  onAction,
  featured = false,
  className,
}: {
  insight: AgentInsight;
  onAction?: (prompt: string, replyId?: string) => void;
  featured?: boolean;
  className?: string;
}) {
  const s = statusStyles[insight.status];
  const Icon = resolveIcon(insight.icon ?? agentIcon[insight.agent]);

  return (
    <div
      className={cn(
        "card-hover flex flex-col rounded-[1.35rem] p-4 ring-1",
        featured ? "grad-sage-soft ring-ai/18" : "glass-inset ring-line",
        className
      )}
    >
      <div className="flex items-center gap-2">
        <span className={cn("grid size-7 shrink-0 place-items-center rounded-xl ring-1", s.bg, s.text, s.ring)}>
          <Icon className="size-3.5" strokeWidth={2} />
        </span>
        <span className="truncate text-xs font-semibold text-text-muted">{insight.agent} agent</span>
        <Badge status={insight.status} className="ml-auto shrink-0" dot={false}>
          {featured ? "Recommended" : insight.status === "warning" ? "Risk pattern" : "Insight"}
        </Badge>
      </div>

      <h4 className={cn("mt-2.5 text-sm font-semibold", featured ? "text-text" : s.text)}>
        {insight.title}
      </h4>
      <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-text-muted">{insight.body}</p>

      {onAction ? (
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3">
          <p className="line-clamp-1 text-[11px] text-text-dim">{insight.suggestion}</p>
          {insight.action && (
            <Button
              variant="ai"
              size="sm"
              className="shrink-0"
              onClick={() => onAction(insight.action!.prompt, insight.action!.replyId)}
            >
              {insight.action.label}
              <ArrowRight className="size-3.5" />
            </Button>
          )}
        </div>
      ) : (
        <div className="mt-3 flex items-start gap-2 rounded-2xl bg-accent/[0.06] p-3 text-xs text-text ring-1 ring-ai/15">
          <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-ai" />
          <span className="leading-relaxed">{insight.suggestion}</span>
        </div>
      )}
    </div>
  );
});
