import { TrendingUp, Activity, BarChart3, AlertTriangle } from "lucide-react";
import type { PerformanceSummary, StrategyRanking } from "@/lib/api";

interface Props {
  performance: PerformanceSummary | undefined;
  rankings: StrategyRanking[];
}

export function PerformancePanel({ performance, rankings }: Props) {
  const p = performance;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
        Performance
      </span>

      {/* Key metrics */}
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricCard
          icon={BarChart3}
          label="Trades"
          value={String(p?.trade_count ?? 0)}
        />
        <MetricCard
          icon={TrendingUp}
          label="Win Rate"
          value={`${((p?.win_rate ?? 0) * 100).toFixed(0)}%`}
          color={p && p.win_rate >= 0.5 ? "text-bullish" : undefined}
        />
        <MetricCard
          icon={Activity}
          label="Total PnL"
          value={`$${(p?.total_pnl ?? 0).toFixed(2)}`}
          color={p && p.total_pnl >= 0 ? "text-bullish" : "text-bearish"}
        />
        <MetricCard
          icon={AlertTriangle}
          label="Drawdown"
          value={`$${(p?.max_drawdown ?? 0).toFixed(2)}`}
          color="text-warning"
        />
      </div>

      {/* Strategy rankings */}
      {rankings.length > 0 && (
        <div className="mt-4">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Strategy Scores
          </span>
          <div className="mt-2 space-y-1.5">
            {rankings.map((r) => (
              <div key={r.strategy} className="flex items-center gap-2">
                <span className="w-20 truncate font-mono text-xs text-muted-foreground">
                  {r.strategy.replace("_", " ")}
                </span>
                <div className="flex-1">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${r.overall_score * 100}%` }}
                    />
                  </div>
                </div>
                <span className="w-8 text-right font-mono text-[10px] text-muted-foreground">
                  {(r.overall_score * 100).toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
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
