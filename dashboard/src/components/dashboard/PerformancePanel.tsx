import { TrendingUp, Activity, BarChart3, AlertTriangle } from "lucide-react";
import type { PerformanceSummary, SimulatedTrade, StrategyRanking } from "@/lib/api";

interface Props {
  performance: PerformanceSummary | undefined;
  rankings: StrategyRanking[];
  recentTrades: SimulatedTrade[];
}

export function PerformancePanel({ performance, rankings, recentTrades }: Props) {
  const p = performance;
  const bestStrategy = [...rankings].sort((left, right) => (right.overall_score ?? 0) - (left.overall_score ?? 0))[0];

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
      <div className="mb-4 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
          Performance
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">paper trading</span>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-xl border border-border bg-secondary/20 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Summary</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <MetricCard icon={BarChart3} label="Trades" value={String(p?.trade_count ?? 0)} />
            <MetricCard icon={TrendingUp} label="Winrate" value={`${((p?.win_rate ?? 0) * 100).toFixed(0)}%`} color={p && p.win_rate >= 0.5 ? "text-bullish" : undefined} />
            <MetricCard icon={Activity} label="PnL" value={`$${(p?.total_pnl ?? 0).toFixed(2)}`} color={p && p.total_pnl >= 0 ? "text-bullish" : "text-bearish"} />
            <MetricCard icon={AlertTriangle} label="Drawdown" value={`$${(p?.max_drawdown ?? 0).toFixed(2)}`} color="text-warning" />
          </div>
        </div>

        <div className="rounded-xl border border-border bg-secondary/20 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Best Strategy</p>
          <p className="mt-3 font-mono text-lg font-semibold text-foreground">{bestStrategy ? bestStrategy.strategy.replace(/_/g, " ") : "No data"}</p>
          <div className="mt-4 grid gap-3">
            <MetricCard icon={TrendingUp} label="Score" value={bestStrategy ? `${Math.round((bestStrategy.overall_score ?? 0) * 100)}` : "0"} />
            <MetricCard icon={Activity} label="Avg Return" value={bestStrategy ? `$${(bestStrategy.avg_pnl ?? 0).toFixed(2)}` : "$0.00"} color={(bestStrategy?.avg_pnl ?? 0) >= 0 ? "text-bullish" : "text-bearish"} />
            <MetricCard icon={BarChart3} label="Winrate" value={bestStrategy ? `${Math.round((bestStrategy.win_rate ?? 0) * 100)}%` : "0%"} />
          </div>
        </div>

        <div className="rounded-xl border border-border bg-secondary/20 p-4">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Recent Trades</p>
            <span className="font-mono text-[10px] text-muted-foreground">Last 5 exits</span>
          </div>
          <div className="mt-3 space-y-2">
            {recentTrades.slice(0, 5).map((trade) => (
              <div key={trade.id} className="rounded-lg border border-border bg-background/30 px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xs text-foreground">{trade.symbol}</span>
                  <span className={`font-mono text-xs ${trade.pnl >= 0 ? "text-bullish" : "text-bearish"}`}>
                    {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between font-mono text-[10px] text-muted-foreground">
                  <span>{trade.direction > 0 ? "LONG" : trade.direction < 0 ? "SHORT" : "FLAT"}</span>
                  <span>{trade.strategy}</span>
                </div>
              </div>
            ))}
            {recentTrades.length === 0 ? <p className="py-8 text-center font-mono text-xs text-muted-foreground">No recent exits yet</p> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-secondary/30 px-3 py-2">
      <div className="flex items-center gap-1">
        <Icon className="h-3 w-3 text-muted-foreground" />
        <span className="font-mono text-[10px] uppercase text-muted-foreground">{label}</span>
      </div>
      <p className={`mt-1 font-mono text-sm font-semibold ${color ?? "text-foreground"}`}>
        {value}
      </p>
    </div>
  );
}
