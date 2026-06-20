import { memo } from "react";
import { Swords, Sparkles } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { cn } from "@/lib/utils";
import type { MatchResult } from "@/types/athlete";

export const MatchResultsPanel = memo(function MatchResultsPanel({
  matches,
  onAction,
  onAskMatch,
}: {
  matches: MatchResult[];
  onAction: () => void;
  onAskMatch: (m: MatchResult) => void;
}) {
  return (
    <SectionCard
      id="matches"
      title="Match Results"
      subtitle="Recent singles results"
      icon={Swords}
      action="Ask AI"
      onAction={onAction}
      delay={0.15}
    >
      <ul className="space-y-2.5">
        {matches.map((m) => {
          const win = m.result === "W";
          return (
            <li
              key={m.id}
              className="glass-inset group rounded-2xl p-3 transition-colors hover:bg-white/56"
            >
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "grid size-9 shrink-0 place-items-center rounded-xl text-sm font-bold ring-1",
                    win
                      ? "bg-positive/12 text-positive ring-positive/25"
                      : "bg-negative/12 text-negative ring-negative/25"
                  )}
                >
                  {m.result}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="truncate text-sm font-medium text-text">vs. {m.opponent}</span>
                    <span className="tnum text-xs text-text-muted">{m.score}</span>
                  </div>
                  <div className="mt-0.5 text-[11px] text-text-dim">{m.date}</div>
                </div>
                <button
                  onClick={() => onAskMatch(m)}
                  className="flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-ai opacity-0 transition-opacity hover:bg-ai/10 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Sparkles className="size-3" />
                  Ask AI
                </button>
              </div>
              <p className="mt-2 pl-12 text-[11px] leading-relaxed text-text-muted">{m.note}</p>
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
});
