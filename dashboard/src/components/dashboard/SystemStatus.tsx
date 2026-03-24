import { Circle, Clock } from "lucide-react";
import type { StatusResponse } from "@/lib/api";

interface Props {
  status: StatusResponse | undefined;
  isLoading: boolean;
  isError: boolean;
}

export function SystemStatus({ status, isLoading, isError }: Props) {
  const uptime = status?.uptime_seconds ?? 0;
  const hours = Math.floor(uptime / 3600);
  const mins = Math.floor((uptime % 3600) / 60);
  const isPaperOnly = (status?.paper_trading_only ?? false) || (status?.execution_mode === "paper");

  const threads = [
    { label: "Binance", alive: status?.binance_thread_alive },
    { label: "Polymarket", alive: status?.polymarket_thread_alive },
    { label: "Hyperliquid", alive: status?.hyperliquid_thread_alive },
    { label: "TA Scanner", alive: status?.ta_scanner_thread_alive },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-4 py-2">
      {/* Connection status */}
      <div className="flex items-center gap-1.5">
        <Circle
          className={`h-2 w-2 fill-current ${
            isError ? "text-bearish" : isLoading ? "text-warning" : "text-bullish"
          }`}
        />
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {isError ? "Disconnected" : isLoading ? "Connecting" : "Live"}
        </span>
      </div>

      {/* Uptime */}
      <div className="flex items-center gap-1">
        <Clock className="h-3 w-3 text-muted-foreground" />
        <span className="font-mono text-[10px] text-muted-foreground">
          {hours}h {mins}m
        </span>
      </div>

      {/* Thread health */}
      {threads.map((t) => (
        <div key={t.label} className="flex items-center gap-1">
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              t.alive ? "bg-bullish" : "bg-bearish"
            }`}
          />
          <span className="font-mono text-[10px] text-muted-foreground">{t.label}</span>
        </div>
      ))}

      {/* Symbol */}
      {status && (
        <div className="ml-auto flex items-center gap-2">
          <span
            className={`rounded border px-2 py-0.5 font-mono text-[9px] font-semibold tracking-wider ${
              isPaperOnly
                ? "border-amber-300/40 bg-amber-500/15 text-amber-300"
                : "border-bearish/40 bg-bearish/10 text-bearish"
            }`}
          >
            {isPaperOnly ? "PAPER TRADING ONLY" : "MODE CHECK"}
          </span>
          <span className="font-mono text-[10px] font-medium text-foreground">
            {status.symbol}
          </span>
        </div>
      )}
    </div>
  );
}
