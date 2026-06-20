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
    <aside className="sticky top-0 hidden h-[calc(100vh-2rem)] w-[76px] shrink-0 border-r border-white/18 bg-white/[0.035] p-3 lg:flex xl:w-[196px]">
      <div className="flex h-full w-full flex-col">
        <div className="flex items-center justify-center gap-3 px-1 pb-4 pt-1 xl:justify-start">
          <span className="grid size-8 place-items-center rounded-xl bg-white/12 text-white ring-1 ring-white/25 shadow-[0_0_26px_rgba(211,232,255,0.2)]">
            <Hexagon className="size-5" strokeWidth={2} />
          </span>
          <div className="hidden min-w-0 leading-tight xl:block">
            <div className="text-sm font-semibold tracking-tight text-white">Search</div>
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
                    ? "bg-white/88 text-[#4467e8] shadow-[0_0_24px_rgba(255,255,255,0.28),inset_0_1px_0_rgba(255,255,255,0.9)] ring-1 ring-white/65"
                    : "text-text-muted hover:bg-white/11 hover:text-white"
                )}
              >
                {isActive && (
                  <span className="absolute right-3 top-1/2 hidden size-1.5 -translate-y-1/2 rounded-full bg-[#9dfcff] shadow-[0_0_16px_rgba(157,252,255,0.9)] xl:block" />
                )}
                <item.icon
                  className={cn("size-4.5 shrink-0", isActive ? "text-[#4467e8]" : "text-text-dim group-hover:text-white")}
                  strokeWidth={1.8}
                />
                <span className="hidden truncate xl:inline">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="glass-inset mt-4 flex items-center justify-center gap-3 rounded-[1.15rem] p-2 xl:justify-start">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-pink-200/80 to-cyan-100/50 text-xs font-bold text-[#24316f] ring-1 ring-white/35">
            {profile.avatarInitials}
          </span>
          <div className="hidden min-w-0 leading-tight xl:block">
            <div className="truncate text-sm font-semibold text-white">{profile.name}</div>
            <div className="truncate text-[11px] text-text-dim">{profile.handle}</div>
          </div>
          <Settings
            className="hidden size-4 shrink-0 text-text-dim transition-colors hover:text-white xl:ml-auto xl:block"
            strokeWidth={1.75}
          />
        </div>
      </div>
    </aside>
  );
});
