import { useMemo, useState } from "react";
import { useHistorySignals, useHistoryOpportunities, useHistoryTrades, useLogs } from "@/hooks/use-trading-data";
import { useSymbol } from "@/contexts/SymbolContext";

const STRATEGY_TYPE: Record<string, "directional" | "arbitrage"> = {
  trend: "directional",
  momentum: "directional",
  ta_confluence: "directional",
  reversal: "directional",
  breakout: "directional",
  mean_reversion: "directional",
  volatility: "directional",
  scalping: "directional",
  funding_arb: "arbitrage",
  basis_arb: "arbitrage",
};

const BOT_TO_STRATEGY: Record<string, string> = {
  TrendBot: "trend",
  MomentumBot: "momentum",
  TABot: "ta_confluence",
  ReversalBot: "reversal",
  BreakoutBot: "breakout",
  MeanRevBot: "mean_reversion",
  VolatilityBot: "volatility",
  ScalperBot: "scalping",
  FundingArbBot: "funding_arb",
  BasisArbBot: "basis_arb",
};

export default function HistoryPage() {
  const { symbol, setSymbol, symbols } = useSymbol();
  const [strategy, setStrategy] = useState("ALL");
  const [bot, setBot] = useState("ALL");
  const [tradeType, setTradeType] = useState("ALL");
  const [timeframe, setTimeframe] = useState("ALL");
  const [outcome, setOutcome] = useState("ALL");

  const strategyParam = strategy !== "ALL" ? strategy : bot !== "ALL" ? BOT_TO_STRATEGY[bot] : "ALL";
  const sharedParams = useMemo(
    () => ({
      limit: "100",
      symbol,
      ...(timeframe !== "ALL" ? { timeframe } : {}),
      ...(strategyParam !== "ALL" ? { strategy: strategyParam } : {}),
    }),
    [symbol, timeframe, strategyParam],
  );

  const signals = useHistorySignals(sharedParams);
  const opportunities = useHistoryOpportunities(sharedParams);
  const trades = useHistoryTrades(
    useMemo(
      () => ({
        limit: "100",
        symbol,
        ...(strategyParam !== "ALL" ? { strategy: strategyParam } : {}),
      }),
      [symbol, strategyParam],
    ),
  );
  const logs = useLogs();

  const filteredSignals = (signals.data?.signals ?? []).filter((row) => {
    const rowStrategy = String(row.strategy || "unknown");
    const rowBot = Object.entries(BOT_TO_STRATEGY).find(([, value]) => value === rowStrategy)?.[0] || "UnknownBot";
    return (tradeType === "ALL" || STRATEGY_TYPE[rowStrategy] === tradeType) && (bot === "ALL" || rowBot === bot);
  });

  const filteredOpportunities = (opportunities.data?.opportunities ?? []).filter((row) => {
    const rowStrategy = String(row.strategy || "unknown");
    const rowBot = Object.entries(BOT_TO_STRATEGY).find(([, value]) => value === rowStrategy)?.[0] || "UnknownBot";
    return (tradeType === "ALL" || STRATEGY_TYPE[rowStrategy] === tradeType) && (bot === "ALL" || rowBot === bot);
  });

  const filteredTrades = (trades.data?.trades ?? []).filter((row) => {
    const rowStrategy = String(row.strategy || "unknown");
    const rowBot = Object.entries(BOT_TO_STRATEGY).find(([, value]) => value === rowStrategy)?.[0] || "UnknownBot";
    const rowOutcome = Number(row.pnl || 0) > 0 ? "win" : Number(row.pnl || 0) < 0 ? "loss" : "flat";
    return (
      (tradeType === "ALL" || STRATEGY_TYPE[rowStrategy] === tradeType) &&
      (bot === "ALL" || rowBot === bot) &&
      (timeframe === "ALL" || String(row.timeframe || "") === timeframe) &&
      (outcome === "ALL" || rowOutcome === outcome)
    );
  });

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">History & Logs</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Filtered history across directional and arbitrage systems.
      </p>

      <div className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-5 xl:grid-cols-6">
        <FilterSelect label="Symbol" value={symbol} onChange={setSymbol} options={symbols} />
        <FilterSelect label="Strategy" value={strategy} onChange={setStrategy} options={["ALL", "trend", "momentum", "ta_confluence", "reversal", "breakout", "mean_reversion", "volatility", "scalping", "funding_arb", "basis_arb"]} />
        <FilterSelect label="Bot" value={bot} onChange={setBot} options={["ALL", "TrendBot", "MomentumBot", "TABot", "ReversalBot", "BreakoutBot", "MeanRevBot", "VolatilityBot", "ScalperBot", "FundingArbBot", "BasisArbBot"]} />
        <FilterSelect label="Type" value={tradeType} onChange={setTradeType} options={["ALL", "directional", "arbitrage"]} />
        <FilterSelect label="Timeframe" value={timeframe} onChange={setTimeframe} options={["ALL", "scalp", "5m", "15m", "1h", "4h", "1d", "consensus"]} />
        <FilterSelect label="Outcome" value={outcome} onChange={setOutcome} options={["ALL", "win", "loss", "flat"]} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <HistoryTable
          title="Signals"
          columns={["Strategy", "Trend", "Timeframe", "Confidence"]}
          rows={filteredSignals.map((row) => [
            String(row.strategy || "unknown"),
            row.trend,
            String(row.timeframe || "—"),
            `${Math.round((row.confidence || 0) * 100)}%`,
          ])}
        />
        <HistoryTable
          title="Opportunities"
          columns={["Strategy", "Side", "Timeframe", "Edge"]}
          rows={filteredOpportunities.map((row) => [
            String(row.strategy || "unknown"),
            row.side,
            String(row.timeframe || "—"),
            `${((row.edge || 0) * 100).toFixed(2)}%`,
          ])}
        />
        <HistoryTable
          title="Trades"
          columns={["Strategy", "Direction", "Timeframe", "PnL"]}
          rows={filteredTrades.map((row) => [
            String(row.strategy || "unknown"),
            Number(row.direction || 0) > 0 ? "LONG" : Number(row.direction || 0) < 0 ? "SHORT" : "FLAT",
            String(row.timeframe || "—"),
            `$${Number(row.pnl || 0).toFixed(2)}`,
          ])}
        />
      </div>

      <HistoryTable
        title="Logs"
        columns={["Time", "Level", "Module", "Message"]}
        rows={(logs.data?.logs ?? []).slice(0, 30).map((row) => [
          new Date(row.timestamp).toLocaleTimeString(),
          row.level,
          row.module,
          row.message,
        ])}
        wide
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="grid gap-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-border bg-background px-3 py-2 text-xs text-foreground"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function HistoryTable({
  title,
  columns,
  rows,
  wide = false,
}: {
  title: string;
  columns: string[];
  rows: string[][];
  wide?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">{title}</h2>
        <span className="font-mono text-[10px] text-muted-foreground">{rows.length} rows</span>
      </div>
      <div className={`overflow-x-auto ${wide ? "" : "max-h-[360px]"}`}>
        <table className="w-full min-w-[420px] table-auto border-collapse">
          <thead>
            <tr className="border-b border-border">
              {columns.map((column) => (
                <th key={column} className="px-2 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${title}-${index}`} className="border-b border-border/60">
                {row.map((cell, cellIndex) => (
                  <td key={`${title}-${index}-${cellIndex}`} className="px-2 py-2 font-mono text-xs text-foreground">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-2 py-6 text-center font-mono text-xs text-muted-foreground">
                  No rows for current filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
