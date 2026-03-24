import { motion } from "framer-motion";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import type { DirectionalDecision, StrategyRanking } from "@/lib/api";

const BOT_META: Record<string, { label: string; color: string }> = {
  TrendBot: { label: "Trend", color: "hsl(142, 60%, 45%)" },
  ReversalBot: { label: "Reversal", color: "hsl(280, 60%, 55%)" },
  TABot: { label: "TA", color: "hsl(200, 70%, 50%)" },
  ArbitrageBot: { label: "Arb", color: "hsl(45, 90%, 55%)" },
  ModelVsMarketBot: { label: "Model", color: "hsl(280, 60%, 65%)" },
  PerpArbBot: { label: "Perp", color: "hsl(210, 75%, 60%)" },
  ScalperBot: { label: "Scalp", color: "hsl(18, 90%, 58%)" },
};

interface Props {
  decision: DirectionalDecision | null;
  rankings: StrategyRanking[];
}

export function BotOrchestra({ decision, rankings }: Props) {
  const botEntries = decision?.bots ?? [];

  // Calculate vote tally
  const votes = botEntries.reduce(
    (acc, bot) => {
      if (bot.direction > 0) acc.long++;
      else if (bot.direction < 0) acc.short++;
      else acc.flat++;
      return acc;
    },
    { long: 0, short: 0, flat: 0 }
  );

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
      <div className="mb-4 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
          Strategy Engine
        </span>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-bullish">{votes.long}L</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-bearish">{votes.short}S</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">{votes.flat}F</span>
        </div>
      </div>

      <div className="space-y-5">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Strategy Ranking</span>
            <span className="font-mono text-[10px] text-muted-foreground">{rankings.length} tracked</span>
          </div>
          <div className="space-y-2">
            {rankings.slice(0, 5).map((ranking) => (
              <div key={ranking.strategy} className="rounded-lg border border-border bg-secondary/25 px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs text-foreground">{ranking.strategy.replaceAll("_", " ")}</p>
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground">Winrate {Math.round((ranking.win_rate ?? 0) * 100)}%</p>
                  </div>
                  <span className="font-mono text-sm font-semibold text-foreground">{Math.round((ranking.overall_score ?? 0) * 100)}</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, (ranking.overall_score ?? 0) * 100))}%` }} />
                </div>
              </div>
            ))}
            {rankings.length === 0 ? (
              <p className="py-3 text-center font-mono text-xs text-muted-foreground">No strategy rankings yet</p>
            ) : null}
          </div>
        </div>

        <div className="grid grid-cols-[minmax(0,1.2fr)_0.8fr_0.7fr_0.8fr] gap-2 px-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          <span>Bot</span>
          <span>Direction</span>
          <span>Weight</span>
          <span className="text-right">Conf</span>
        </div>

        {botEntries.map((bot, i) => {
          const name = String(bot.bot || bot.strategy || "UnknownBot");
          const meta = BOT_META[name] ?? { label: name, color: "hsl(215, 12%, 50%)" };
          const isLong = bot.direction > 0;
          const isShort = bot.direction < 0;
          const DirIcon = isLong ? ArrowUp : isShort ? ArrowDown : Minus;
          const confPct = Math.round(bot.confidence * 100);
          const weight = Number(bot.weight ?? 0).toFixed(2);

          return (
            <motion.div
              key={name}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="grid grid-cols-[minmax(0,1.2fr)_0.8fr_0.7fr_0.8fr] items-center gap-2 rounded-lg border border-border bg-secondary/30 px-3 py-3"
            >
              <div className="flex min-w-0 items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: meta.color }} />
                <div className="min-w-0">
                  <span className="block truncate font-mono text-xs font-medium text-foreground">{meta.label}</span>
                  <span className="block truncate font-mono text-[10px] text-muted-foreground">{bot.time_horizon ?? "short"}</span>
                </div>
              </div>

              <div className="flex items-center gap-1 font-mono text-xs">
                <DirIcon
                  className={`h-3.5 w-3.5 ${
                    isLong ? "text-bullish" : isShort ? "text-bearish" : "text-muted-foreground"
                  }`}
                />
                <span className={isLong ? "text-bullish" : isShort ? "text-bearish" : "text-muted-foreground"}>
                  {bot.signal ?? "FLAT"}
                </span>
              </div>

              <div className="space-y-1">
                <span className="block font-mono text-xs text-muted-foreground">{weight}</span>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, Number(bot.weight ?? 0) * 100))}%`, backgroundColor: meta.color }} />
                </div>
              </div>

              <span className="text-right font-mono text-xs text-muted-foreground">
                {confPct}%
              </span>
            </motion.div>
          );
        })}
      </div>

      {botEntries.length === 0 && (
        <p className="py-4 text-center font-mono text-xs text-muted-foreground">
          Waiting for bot signals...
        </p>
      )}
    </div>
  );
}
