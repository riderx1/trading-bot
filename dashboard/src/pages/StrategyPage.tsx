import { useMemo, useState } from "react";
import { usePerformance, useRecentTrades, useStrategyRankings } from "@/hooks/use-trading-data";
import { PerformancePanel } from "@/components/dashboard/PerformancePanel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function StrategyPage() {
  const performance = usePerformance();
  const rankings = useStrategyRankings();
  const recentTrades = useRecentTrades(undefined, 5);
  const [venueFilter, setVenueFilter] = useState("ALL");
  const filteredRankings = useMemo(() => {
    const rows = rankings.data?.strategies ?? [];
    if (venueFilter === "ALL") return rows;
    return rows.filter((row) => String(row.venue || "").toLowerCase() === venueFilter.toLowerCase());
  }, [rankings.data?.strategies, venueFilter]);

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

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-mono text-sm text-foreground">Rankings</h2>
          <Select value={venueFilter} onValueChange={setVenueFilter}>
            <SelectTrigger className="h-8 w-[180px] font-mono text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All venues</SelectItem>
              <SelectItem value="hyperliquid">Hyperliquid</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[580px] text-left font-mono text-xs">
            <thead>
              <tr className="text-muted-foreground">
                <th className="px-2 py-2">Strategy</th>
                <th className="px-2 py-2">Venue</th>
                <th className="px-2 py-2">Trades</th>
                <th className="px-2 py-2">Winrate</th>
                <th className="px-2 py-2">Score</th>
              </tr>
            </thead>
            <tbody>
              {filteredRankings.map((row) => (
                <tr key={`${row.strategy}:${row.venue}`} className="border-t border-border/60 text-foreground">
                  <td className="px-2 py-2">{row.strategy.replace(/_/g, " ")}</td>
                  <td className="px-2 py-2">{row.venue || "n/a"}</td>
                  <td className="px-2 py-2">{row.trade_count}</td>
                  <td className="px-2 py-2">{Math.round(row.win_rate * 100)}%</td>
                  <td className="px-2 py-2">{Math.round(row.overall_score * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
