import { memo } from "react";
import { MetricCard } from "./MetricCard";
import type { OverviewMetric } from "@/types/athlete";

export const OverviewCards = memo(function OverviewCards({
  metrics,
}: {
  metrics: OverviewMetric[];
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {metrics.map((m, i) => (
        <MetricCard key={m.id} metric={m} delay={i * 0.03} />
      ))}
    </div>
  );
});
