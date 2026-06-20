import { memo, useMemo } from "react";
import { Swords } from "lucide-react";
import type { FormMatch } from "@/types/athlete";

const WIN_BAR = "linear-gradient(180deg, #38bdf8 0%, #2563eb 100%)";
const LOSS_BAR = "linear-gradient(180deg, #a5b4fc 0%, #64748b 100%)";

/**
 * The win/loss form graph: one bar per recent match, blue/cyan for a win, slate-blue for a
 * loss, height = how well she played. A single, instantly-readable view of form.
 */
export const FormResultsCard = memo(function FormResultsCard({
  form,
  onAction,
}: {
  form: FormMatch[];
  onAction: () => void;
}) {
  const recent = useMemo(() => form.slice(-5), [form]);
  const { wins, losses, rate } = useMemo(() => {
    const w = recent.filter((f) => f.result === "W").length;
    return { wins: w, losses: recent.length - w, rate: Math.round((w / recent.length) * 100) };
  }, [recent]);

  return (
    <section id="form" className="glass-card fade-up flex min-h-0 flex-col overflow-hidden rounded-[1.45rem] p-2.5">
      <header className="mb-2 flex shrink-0 items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="glass-chip grid size-7 shrink-0 place-items-center rounded-xl text-text-muted">
            <Swords className="size-4" strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-text">Form</h2>
            <p className="truncate text-[10px] text-text-dim">Last {recent.length} matches</p>
          </div>
        </div>
        <button
          onClick={onAction}
          className="glass-chip shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold text-text transition-colors hover:bg-accent/7"
        >
          Explain
        </button>
      </header>

      <div className="glass-inset flex min-h-0 flex-1 flex-col rounded-[1.15rem] px-2.5 py-1.5">
        <div className="flex shrink-0 items-center justify-between">
          <div>
            <div className="tnum text-[1.5rem] font-semibold leading-none tracking-tight text-text">{rate}%</div>
            <div className="text-[10px] font-medium text-text-muted">Win rate</div>
          </div>
          <div className="flex items-center gap-3 text-right">
            <div>
              <div className="tnum text-base font-semibold text-positive">{wins}W</div>
              <div className="text-[9px] text-text-dim">Wins</div>
            </div>
            <div>
              <div className="tnum text-base font-semibold text-negative">{losses}L</div>
              <div className="text-[9px] text-text-dim">Losses</div>
            </div>
          </div>
        </div>

        <div className="mt-auto flex h-8 items-end gap-2 pt-2">
          {recent.map((match) => (
            <div key={match.id} className="flex min-w-0 flex-1 items-end">
              <span
                title={`${match.result} ${match.score} vs ${match.opponent}`}
                className="w-full rounded-t-md shadow-[0_0_12px_rgba(37,99,235,0.18)]"
                style={{
                  height: `${Math.max(28, match.value)}%`,
                  background: match.result === "W" ? WIN_BAR : LOSS_BAR,
                }}
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
});
