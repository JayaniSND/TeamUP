import {
  Activity,
  HeartPulse,
  CalendarDays,
  Trophy,
  Sparkles,
  Target,
  TrendingUp,
  Plane,
  Handshake,
  BookOpen,
  Bot,
  Circle,
  type LucideIcon,
} from "lucide-react";

/**
 * Explicit icon registry. Data references icons by *name* (so it stays
 * API-shaped / DB-ready), but we resolve only the icons we actually use —
 * importing them by name keeps lucide tree-shakeable instead of bundling the
 * entire ~1500-icon set via `import * as Icons`.
 */
export const iconMap: Record<string, LucideIcon> = {
  Activity,
  HeartPulse,
  CalendarDays,
  Trophy,
  Sparkles,
  Target,
  TrendingUp,
  Plane,
  Handshake,
  BookOpen,
  Bot,
};

export function resolveIcon(name?: string): LucideIcon {
  return iconMap[name ?? ""] ?? Circle;
}
