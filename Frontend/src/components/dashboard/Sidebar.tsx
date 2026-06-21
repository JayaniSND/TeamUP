import { memo } from "react";
import { LayoutDashboard, CalendarDays, TrendingUp, HeartPulse, Bot, Hexagon, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AthleteProfile } from "@/types/athlete";

const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "calendar", label: "Calendar", icon: CalendarDays },
  { id: "performance", label: "Trend", icon: TrendingUp },
  { id: "recovery", label: "Recovery", icon: HeartPulse },
  { id: "ai", label: "AI Chat", icon: Bot },
] as const;

/**
 * Premium dark-green rail (#1F6F5F). Text/icons are light (#EEEEEE family);
 * the active item is a solid #2FA084 pill so navigation reads at a glance
 * without the rail feeling heavy.
 */
export const Sidebar = memo(function Sidebar({
  active,
  onSelect,
  profile,
}: {
  active: string;
  onSelect: (id: string) => void;
  profile: AthleteProfile;
}) {
  return (
    <aside className="sticky top-0 hidden h-[calc(100vh-2rem)] w-[76px] shrink-0 bg-sidebar p-3 text-[#EEEEEE] lg:flex xl:w-[200px]">
      <div className="flex h-full w-full flex-col">
        <div className="flex items-center justify-center gap-3 px-1 pb-4 pt-1 xl:justify-start">
          <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-white/10 text-lime ring-1 ring-white/15">
            <Hexagon className="size-5" strokeWidth={2} />
          </span>
          <div className="hidden min-w-0 leading-tight xl:block">
            <div className="truncate text-sm font-semibold tracking-tight text-white">AthleteOS</div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/50">Analytics</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1.5">
          {NAV.map((item) => {
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelect(item.id)}
                aria-current={isActive ? "page" : undefined}
                title={item.label}
                className={cn(
                  "group relative flex h-10 items-center justify-center gap-3 rounded-xl px-3 text-sm font-semibold transition-[background-color,color,box-shadow,transform] duration-200 ease-out active:translate-y-px xl:justify-start",
                  isActive
                    ? "bg-accent text-white shadow-[0_8px_20px_-10px_rgba(47,160,132,0.8),inset_0_1px_0_rgba(255,255,255,0.25)]"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                )}
              >
                <item.icon
                  className={cn("size-4.5 shrink-0", isActive ? "text-white" : "text-white/65 group-hover:text-white")}
                  strokeWidth={1.8}
                />
                <span className="hidden truncate xl:inline">{item.label}</span>
                {isActive && (
                  <span className="absolute right-3 top-1/2 hidden size-1.5 -translate-y-1/2 rounded-full bg-lime shadow-[0_0_12px_rgba(111,207,151,0.9)] xl:block" />
                )}
              </button>
            );
          })}
        </nav>

        <div className="mt-4 flex items-center justify-center gap-3 rounded-[1.15rem] bg-white/10 p-2 ring-1 ring-white/10 xl:justify-start">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent/35 text-xs font-bold text-white ring-1 ring-white/20">
            {profile.avatarInitials}
          </span>
          <div className="hidden min-w-0 leading-tight xl:block">
            <div className="truncate text-sm font-semibold text-white">{profile.name}</div>
            <div className="truncate text-[11px] text-white/55">{profile.handle}</div>
          </div>
          <Settings
            className="hidden size-4 shrink-0 text-white/55 transition-colors hover:text-white xl:ml-auto xl:block"
            strokeWidth={1.75}
          />
        </div>
      </div>
    </aside>
  );
});
