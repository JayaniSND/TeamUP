import { memo } from "react";
import { Mic, Camera, FileText, ArrowRight, BookOpen } from "lucide-react";
import { type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { Intake } from "@/types/athlete";

const sourceMeta: Record<Intake["sources"][number], { icon: LucideIcon; label: string }> = {
  voice: { icon: Mic, label: "Voice note" },
  notebook: { icon: Camera, label: "Notebook photo" },
  text: { icon: FileText, label: "Text log" },
};

/**
 * The product story in one slim band: a raw brain-dump (voice / notebook photo)
 * on the left → what the Librarian agent filed into structured sections on the
 * right. Makes "messy logs become structured athletic intelligence" visible.
 */
export const IntakeStrip = memo(function IntakeStrip({
  intake,
  delay = 0,
}: {
  intake: Intake;
  delay?: number;
}) {
  return (
    <section
      style={delay ? { animationDelay: `${delay}s` } : undefined}
      className="glass-card fade-up flex flex-col gap-4 rounded-[1.65rem] p-4 sm:p-5 lg:flex-row lg:items-center"
    >
      {/* raw capture */}
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <div className="flex shrink-0 gap-1.5">
          {intake.sources.map((src) => {
            const { icon: Icon, label } = sourceMeta[src];
            return (
              <span
                key={src}
                title={label}
                className="grid size-9 place-items-center rounded-2xl bg-ai/10 text-ai ring-1 ring-ai/20"
              >
                <Icon className="size-4" strokeWidth={1.75} />
              </span>
            );
          })}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Latest intake
            <span className="font-medium normal-case tracking-normal text-text-dim">· {intake.capturedAt}</span>
          </div>
          <p className="mt-0.5 line-clamp-1 text-sm text-text-muted">{intake.summary}</p>
        </div>
      </div>

      {/* transform arrow */}
      <ArrowRight className="hidden size-5 shrink-0 rotate-90 text-text-dim lg:block lg:rotate-0" strokeWidth={1.75} />

      {/* structured output */}
      <div className="flex flex-wrap items-center gap-2 lg:shrink-0">
        {intake.filed.map((f) => (
          <Badge key={f.label} status={f.status}>
            {f.label}
          </Badge>
        ))}
        <span className="glass-chip inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium text-text-dim">
          <BookOpen className="size-3" strokeWidth={2} />
          Filed by {intake.agent}
        </span>
      </div>
    </section>
  );
});
