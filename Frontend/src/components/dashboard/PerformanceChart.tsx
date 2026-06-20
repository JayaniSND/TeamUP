import { memo, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { SectionCard } from "./SectionCard";
import type { PerformancePoint } from "@/types/athlete";

type SeriesKey = "trainingLoad" | "recoveryScore" | "matchPerformance";

const CHART_LOAD = "#2563EB";
const CHART_RECOVERY = "#06B6D4";
const CHART_MATCH = "#4F46E5";
const CHART_GRID = "rgba(100,116,139,0.14)";
const CHART_TICK = "rgba(51,65,85,0.62)";
const CHART_CURSOR = "rgba(37,99,235,0.24)";

const SERIES: { key: SeriesKey; label: string; color: string }[] = [
  { key: "trainingLoad", label: "Training Load", color: CHART_LOAD },
  { key: "recoveryScore", label: "Recovery", color: CHART_RECOVERY },
  { key: "matchPerformance", label: "Match", color: CHART_MATCH },
];

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-card rounded-2xl px-3 py-2 text-xs">
      <div className="mb-1.5 font-semibold text-text">{label}</div>
      <div className="space-y-1">
        {payload.map((p: any) => (
          <div key={p.dataKey} className="flex items-center gap-2">
            <span className="size-2 rounded-full" style={{ background: p.color }} />
            <span className="text-text-muted">{p.name}</span>
            <span className="tnum ml-auto font-semibold text-text">{p.value ?? "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-text-dim">{label}</div>
      <div className="tnum mt-0.5 text-lg font-bold drop-shadow-[0_0_12px_rgba(59,130,246,0.22)]" style={{ color: accent }}>
        {value}
      </div>
    </div>
  );
}

export const PerformanceChart = memo(function PerformanceChart({
  data,
  onAction,
}: {
  data: PerformancePoint[];
  onAction: () => void;
}) {
  // summary stats — computed once per data change, never per render
  const stats = useMemo(() => {
    const avg = (xs: number[]) => Math.round(xs.reduce((a, b) => a + b, 0) / xs.length);
    const matches = data.map((d) => d.matchPerformance).filter((v): v is number => v != null);
    return {
      load: avg(data.map((d) => d.trainingLoad)),
      recovery: avg(data.map((d) => d.recoveryScore)),
      match: matches.length ? Math.max(...matches) : 0,
    };
  }, [data]);

  return (
    <SectionCard
      id="performance"
      title="Performance Trend"
      subtitle="Load, recovery, match form · last 7 days"
      icon={TrendingUp}
      action="Explain trend"
      onAction={onAction}
      delay={0.05}
      className="h-full"
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="mb-3 flex shrink-0 flex-wrap items-center gap-2">
          <div className="glass-inset flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-2 rounded-[1.15rem] px-3 py-2">
            <Stat label="Avg Load" value={String(stats.load)} accent={CHART_LOAD} />
            <Stat label="Avg Recovery" value={String(stats.recovery)} accent={CHART_RECOVERY} />
            <Stat label="Peak Match" value={String(stats.match)} accent={CHART_MATCH} />
          </div>
          <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px] font-semibold text-text-muted">
            {SERIES.map((s) => (
              <span key={s.key} className="glass-chip inline-flex items-center gap-1.5 rounded-full px-2 py-1">
                <span className="size-1.5 rounded-full" style={{ background: s.color }} />
                {s.label}
              </span>
            ))}
          </div>
        </div>

        <div className="glass-inset min-h-[190px] flex-1 overflow-hidden rounded-[1.2rem] p-2.5">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 10, left: -18, bottom: 4 }}>
              <defs>
                <linearGradient id="gLoad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_LOAD} stopOpacity={0.16} />
                  <stop offset="100%" stopColor={CHART_LOAD} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gRecovery" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_RECOVERY} stopOpacity={0.14} />
                  <stop offset="100%" stopColor={CHART_RECOVERY} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={false} />
              <XAxis
                dataKey="date"
                height={18}
                tickMargin={2}
                tick={{ fill: CHART_TICK, fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: CHART_TICK, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={40}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: CHART_CURSOR }} />
              <Area
                type="monotone"
                dataKey="trainingLoad"
                name="Training Load"
                stroke={CHART_LOAD}
                strokeWidth={2}
                fill="url(#gLoad)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="recoveryScore"
                name="Recovery"
                stroke={CHART_RECOVERY}
                strokeWidth={2}
                fill="url(#gRecovery)"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="matchPerformance"
                name="Match"
                stroke={CHART_MATCH}
                strokeWidth={2.5}
                strokeDasharray="5 4"
                dot={{ r: 3, fill: CHART_MATCH, strokeWidth: 0 }}
                connectNulls
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </SectionCard>
  );
});
