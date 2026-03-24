import { motion } from "framer-motion";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import type { OrchestratedDecision } from "@/lib/api";

const BOT_META: Record<string, { label: string; color: string }> = {
  TrendBot: { label: "Trend", color: "hsl(142, 60%, 45%)" },
  ReversalBot: { label: "Reversal", color: "hsl(280, 60%, 55%)" },
  TABot: { label: "TA", color: "hsl(200, 70%, 50%)" },
  ArbitrageBot: { label: "Arb", color: "hsl(45, 90%, 55%)" },
  ModelVsMarketBot: { label: "Model", color: "hsl(280, 60%, 65%)" },
  PerpArbBot: { label: "Perp", color: "hsl(210, 75%, 60%)" },
};

interface Props {
  decision: OrchestratedDecision | null;
}

export function BotOrchestra({ decision }: Props) {
  const bots = decision?.bots ?? {};
  const botEntries = Object.entries(bots);

  // Calculate vote tally
  const votes = botEntries.reduce(
    (acc, [, bot]) => {
      if (bot.direction > 0) acc.long++;
      else if (bot.direction < 0) acc.short++;
      else acc.flat++;
      return acc;
    },
    { long: 0, short: 0, flat: 0 }
  );

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Bot Orchestra
        </span>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-bullish">{votes.long}L</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-bearish">{votes.short}S</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">{votes.flat}F</span>
        </div>
      </div>

      <div className="space-y-2">
        {botEntries.map(([name, bot], i) => {
          const meta = BOT_META[name] ?? { label: name, color: "hsl(215, 12%, 50%)" };
          const isLong = bot.direction > 0;
          const isShort = bot.direction < 0;
          const DirIcon = isLong ? ArrowUp : isShort ? ArrowDown : Minus;
          const confPct = Math.round(bot.confidence * 100);

          return (
            <motion.div
              key={name}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-3 rounded-md border border-border bg-secondary/30 px-3 py-2"
            >
              {/* Color dot */}
              <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: meta.color }} />

              {/* Name */}
              <span className="w-16 font-mono text-xs font-medium text-foreground">{meta.label}</span>

              {/* Direction */}
              <DirIcon
                className={`h-3.5 w-3.5 ${
                  isLong ? "text-bullish" : isShort ? "text-bearish" : "text-muted-foreground"
                }`}
              />

              {/* Confidence bar */}
              <div className="flex-1">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${confPct}%`,
                      backgroundColor: meta.color,
                      opacity: 0.7,
                    }}
                  />
                </div>
              </div>

              {/* Confidence % */}
              <span className="w-9 text-right font-mono text-xs text-muted-foreground">
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
