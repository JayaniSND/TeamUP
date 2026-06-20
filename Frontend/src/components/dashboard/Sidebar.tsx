import { memo } from "react";
import { LayoutDashboard, TrendingUp, HeartPulse, Bot, Hexagon, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AthleteProfile } from "@/types/athlete";

const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "performance", label: "Trend", icon: TrendingUp },
  { id: "recovery", label: "Recovery", icon: HeartPulse },
  { id: "ai", label: "AI Chat", icon: Bot },
] as const;

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
    <aside className="sticky top-0 hidden h-[calc(100vh-2rem)] w-[76px] shrink-0 border-r border-line bg-white/72 p-3 lg:flex xl:w-[196px]">
      <div className="flex h-full w-full flex-col">
        <div className="flex items-center justify-center gap-3 px-1 pb-4 pt-1 xl:justify-start">
          <span className="grid size-8 place-items-center rounded-xl bg-white/95 text-accent ring-1 ring-accent/16 shadow-[0_0_20px_rgba(80,168,119,0.12)]">
            <Hexagon className="size-5" strokeWidth={2} />
          </span>
          <div className="hidden min-w-0 leading-tight xl:block">
            <div className="text-sm font-semibold tracking-tight text-text">Search</div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-dim">Athlete OS</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-2">
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
                    ? "bg-accent/10 text-accent shadow-[0_0_18px_rgba(65,158,105,0.12),inset_0_1px_0_rgba(255,255,255,0.9)] ring-1 ring-accent/16"
                    : "text-text-muted hover:bg-accent/7 hover:text-text"
                )}
              >
                {isActive && (
                  <span className="absolute right-3 top-1/2 hidden size-1.5 -translate-y-1/2 rounded-full bg-positive shadow-[0_0_16px_rgba(37,185,125,0.72)] xl:block" />
                )}
                <item.icon
                  className={cn("size-4.5 shrink-0", isActive ? "text-accent" : "text-text-dim group-hover:text-text")}
                  strokeWidth={1.8}
                />
                <span className="hidden truncate xl:inline">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="glass-inset mt-4 flex items-center justify-center gap-3 rounded-[1.15rem] p-2 xl:justify-start">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-emerald-100/90 to-teal-100/70 text-xs font-bold text-text ring-1 ring-accent/18">
            {profile.avatarInitials}
          </span>
          <div className="hidden min-w-0 leading-tight xl:block">
            <div className="truncate text-sm font-semibold text-text">{profile.name}</div>
            <div className="truncate text-[11px] text-text-dim">{profile.handle}</div>
          </div>
          <Settings
            className="hidden size-4 shrink-0 text-text-dim transition-colors hover:text-text xl:ml-auto xl:block"
            strokeWidth={1.75}
          />
        </div>
      </div>
    </aside>
  );
});
