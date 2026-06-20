import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Status } from "@/types/athlete";

/** Maps a semantic status to its accent classes. Single place color = meaning. */
export const statusStyles: Record<Status, { text: string; bg: string; dot: string; ring: string }> = {
  positive: { text: "text-positive", bg: "bg-positive/12", dot: "bg-positive", ring: "ring-positive/25" },
  warning: { text: "text-warning", bg: "bg-warning/13", dot: "bg-warning", ring: "ring-warning/25" },
  negative: { text: "text-negative", bg: "bg-negative/12", dot: "bg-negative", ring: "ring-negative/25" },
  neutral: { text: "text-accent", bg: "bg-accent/12", dot: "bg-accent", ring: "ring-accent/25" },
  ai: { text: "text-ai", bg: "bg-ai/12", dot: "bg-ai", ring: "ring-ai/25" },
};

export function Badge({
  status = "neutral",
  children,
  className,
  dot = true,
}: {
  status?: Status;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}) {
  const s = statusStyles[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-white/18 px-2.5 py-1 text-[11px] font-semibold tracking-wide shadow-[inset_0_1px_0_rgba(255,255,255,0.16)]",
        s.bg,
        s.text,
        className
      )}
    >
      {dot && <span className={cn("size-1.5 rounded-full", s.dot)} />}
      {children}
    </span>
  );
}
