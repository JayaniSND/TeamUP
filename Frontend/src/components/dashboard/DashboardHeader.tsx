import { memo } from "react";
import { Home, Mic, Sparkles, Bell } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { AthleteProfile } from "@/types/athlete";

export const DashboardHeader = memo(function DashboardHeader({
  profile,
  onAskAI,
  onVoiceUpload,
  onLanding,
}: {
  profile: AthleteProfile;
  onAskAI: () => void;
  onVoiceUpload: () => void;
  onLanding: () => void;
}) {
  return (
    <header className="fade-up flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-white/95 text-sm font-bold text-accent ring-1 ring-accent/16">
          {profile.avatarInitials}
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim">
            <span>{profile.currentWeek}</span>
          </div>
          <h1 className="mt-0.5 truncate text-base font-semibold tracking-tight text-text">{profile.name}</h1>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] font-medium text-text-muted">
            <span>{profile.sport}</span>
            <span className="text-text-dim">·</span>
            <span>{profile.level}</span>
            {profile.worldRank && (
              <>
                <span className="text-text-dim">·</span>
                <span className="tnum">World #{profile.worldRank}</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        <Button variant="outline" size="sm" onClick={onLanding} className="hidden sm:inline-flex">
          <Home className="size-4" strokeWidth={1.75} />
          Landing
        </Button>
        <Button variant="outline" size="icon" aria-label="Notifications">
          <Bell className="size-4" strokeWidth={1.75} />
        </Button>
        <Button variant="outline" size="sm" onClick={onVoiceUpload} className="hidden sm:inline-flex">
          <Mic className="size-4" strokeWidth={1.75} />
          Voice
        </Button>
        <Button variant="primary" size="sm" onClick={onAskAI}>
          <Sparkles className="size-4" strokeWidth={2} />
          Ask AI
        </Button>
      </div>
    </header>
  );
});
