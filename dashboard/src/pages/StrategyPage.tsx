import { usePerformance, useRecentTrades, useStrategyRankings } from "@/hooks/use-trading-data";
import { PerformancePanel } from "@/components/dashboard/PerformancePanel";

export default function StrategyPage() {
  const performance = usePerformance();
  const rankings = useStrategyRankings();
  const recentTrades = useRecentTrades(undefined, 5);

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Strategy Performance</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Strategy rankings, win rates, and edge analysis across all paper trading bots.
      </p>
      <PerformancePanel
        performance={performance.data}
        rankings={rankings.data?.strategies ?? []}
        recentTrades={recentTrades.data?.trades ?? []}
      />
    </div>
  );
}
