import type { BotDecision, MicroData, ScalpPerformanceResponse } from "@/lib/api";

interface Props {
  performance: ScalpPerformanceResponse | undefined;
  latestSignal?: BotDecision | null;
  microData?: MicroData | null;
}

export function ScalpPanel({ performance, latestSignal, microData }: Props) {
  const overall = performance?.overall;
  const venues = performance?.by_venue ?? {};
  const scalpDirection = latestSignal?.signal ?? "FLAT";
  const microConfidence = Math.round((latestSignal?.confidence ?? 0) * 100);

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Scalping
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">paper only</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Metric label="Trades" value={String(overall?.trade_count ?? 0)} />
        <Metric label="Win Rate" value={`${(((overall?.win_rate ?? 0) * 100)).toFixed(0)}%`} />
        <Metric
          label="PnL"
          value={`$${(overall?.total_pnl ?? 0).toFixed(2)}`}
          valueClass={(overall?.total_pnl ?? 0) >= 0 ? "text-bullish" : "text-bearish"}
        />
      </div>

      <div className="mt-3 rounded-md border border-border bg-secondary/20 px-3 py-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Latest Scalping Signal</span>
          <span className={`font-mono text-xs ${scalpDirection === "LONG" ? "text-bullish" : scalpDirection === "SHORT" ? "text-bearish" : "text-muted-foreground"}`}>
            {scalpDirection}
          </span>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <Metric label="Confidence" value={`${microConfidence}%`} />
          <Metric label="Move" value={`${((microData?.move_pct_short ?? 0) * 100).toFixed(2)}%`} />
          <Metric label="Spread" value={`${(microData?.spread_bps ?? 0).toFixed(1)}bp`} />
        </div>
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          Volume spike: {microData?.volume_spike ? "yes" : "no"} · Source: {microData?.source_interval ?? "—"}
        </p>
      </div>

      <div className="mt-3 space-y-1.5">
        {Object.entries(venues).map(([venue, row]) => (
          <div key={venue} className="flex items-center justify-between rounded-md border border-border bg-secondary/30 px-3 py-2">
            <span className="font-mono text-xs text-muted-foreground">{venue}</span>
            <span className="font-mono text-xs text-foreground">{row.trade_count} trades</span>
            <span className={`font-mono text-xs ${(row.total_pnl ?? 0) >= 0 ? "text-bullish" : "text-bearish"}`}>
              ${(row.total_pnl ?? 0).toFixed(2)}
            </span>
          </div>
        ))}
        {Object.keys(venues).length === 0 && (
          <p className="py-3 text-center font-mono text-xs text-muted-foreground">No scalp data yet</p>
        )}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-secondary/30 px-3 py-2">
      <p className="font-mono text-[10px] uppercase text-muted-foreground">{label}</p>
      <p className={`mt-1 font-mono text-sm font-semibold ${valueClass ?? "text-foreground"}`}>{value}</p>
    </div>
  );
}
