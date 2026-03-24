import { Activity } from "lucide-react";
import type { ActivePaperTrade, SimulatedTrade } from "@/lib/api";

interface Props {
  activeTrades: ActivePaperTrade[];
  recentTrades: SimulatedTrade[];
}

function formatDirection(direction: number, side: string): string {
  if (side && side.includes("BINANCE")) {
    return side.split("_").join(" ");
  }
  return direction > 0 ? "LONG" : direction < 0 ? "SHORT" : "FLAT";
}

function formatDuration(seconds: number): string {
  const sec = Math.max(0, Number(seconds) || 0);
  if (sec < 60) return `${sec}s`;
  const minutes = Math.floor(sec / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  return `${hours}h ${remMin}m`;
}

export function ActiveTradesPanel({ activeTrades, recentTrades }: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Active Trades
          </span>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{activeTrades.length} open</span>
      </div>

      <div className="space-y-1.5">
        {activeTrades.length === 0 && (
          <p className="rounded-md border border-border bg-secondary/30 px-3 py-4 text-center font-mono text-xs text-muted-foreground">
            No active paper trades
          </p>
        )}

        {activeTrades.map((trade) => {
          const pnl = trade.unrealized_pnl ?? 0;
          const pnlColor = pnl >= 0 ? "text-bullish" : "text-bearish";

          return (
            <div
              key={`${trade.trade_type}-${trade.symbol}-${trade.strategy}-${trade.opened_at}`}
              className="rounded-md border border-border bg-secondary/30 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-semibold text-foreground">
                  {trade.symbol}
                </span>
                <span className="font-mono text-[10px] text-muted-foreground">{trade.strategy}</span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 font-mono text-[11px]">
                <span className="text-muted-foreground">{formatDirection(trade.direction, trade.side)}</span>
                <span className={`${pnlColor}`}>
                  Unrealized {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 font-mono text-[10px] text-muted-foreground">
                <span>Stake ${trade.stake_usdc.toFixed(2)}</span>
                <span>{formatDuration(trade.duration_seconds)}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Recent Closed</span>
          <span className="font-mono text-[10px] text-muted-foreground">{recentTrades.length} rows</span>
        </div>

        <div className="max-h-56 overflow-auto rounded-md border border-border">
          <table className="w-full text-left font-mono text-[10px]">
            <thead className="sticky top-0 bg-card/95 text-muted-foreground">
              <tr>
                <th className="px-2 py-1">Pair</th>
                <th className="px-2 py-1">Side</th>
                <th className="px-2 py-1">PnL</th>
                <th className="px-2 py-1">Result</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.map((trade) => {
                const win = trade.pnl > 0;
                return (
                  <tr key={trade.id} className="border-t border-border/60">
                    <td className="px-2 py-1 text-foreground">{trade.symbol}</td>
                    <td className="px-2 py-1 text-muted-foreground">
                      {trade.direction > 0 ? "LONG" : trade.direction < 0 ? "SHORT" : "FLAT"}
                    </td>
                    <td className={`px-2 py-1 ${trade.pnl >= 0 ? "text-bullish" : "text-bearish"}`}>
                      {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                    </td>
                    <td className={`px-2 py-1 ${win ? "text-bullish" : "text-bearish"}`}>
                      {win ? "WIN" : "LOSS"}
                    </td>
                  </tr>
                );
              })}
              {recentTrades.length === 0 && (
                <tr>
                  <td className="px-2 py-4 text-center text-muted-foreground" colSpan={4}>
                    No closed trades yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
