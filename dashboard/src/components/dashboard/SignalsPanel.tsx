import { motion } from "framer-motion";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import type { Signal } from "@/lib/api";

interface Props {
  signals: Signal[];
}

const TF_ORDER = ["1d", "4h", "1h", "15m", "5m"];

export function SignalsPanel({ signals }: Props) {
  // Group by timeframe, pick latest per timeframe
  const byTf = new Map<string, Signal>();
  for (const s of signals) {
    const tf = s.timeframe ?? "?";
    if (!byTf.has(tf)) byTf.set(tf, s);
  }

  const sorted = TF_ORDER.map((tf) => byTf.get(tf)).filter(Boolean) as Signal[];

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Multi-Timeframe Signals
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {signals.length} total
        </span>
      </div>

      <div className="space-y-1.5">
        {sorted.map((s, i) => {
          const isBull = s.trend === "bullish";
          const isBear = s.trend === "bearish";
          const Icon = isBull ? ArrowUpRight : isBear ? ArrowDownRight : Minus;
          const confPct = Math.round(s.confidence * 100);

          return (
            <motion.div
              key={s.timeframe}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
              className="flex items-center gap-2 rounded-md border border-border bg-secondary/30 px-3 py-2"
            >
              {/* Timeframe */}
              <span className="w-8 font-mono text-xs font-semibold text-foreground">
                {s.timeframe}
              </span>

              {/* Direction icon */}
              <Icon
                className={`h-3.5 w-3.5 ${
                  isBull ? "text-bullish" : isBear ? "text-bearish" : "text-muted-foreground"
                }`}
              />

              {/* Trend label */}
              <span
                className={`w-14 font-mono text-xs capitalize ${
                  isBull ? "text-bullish" : isBear ? "text-bearish" : "text-muted-foreground"
                }`}
              >
                {s.trend}
              </span>

              {/* Confidence bar */}
              <div className="flex-1">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${
                      isBull ? "bg-bullish" : isBear ? "bg-bearish" : "bg-muted-foreground"
                    }`}
                    style={{ width: `${confPct}%` }}
                  />
                </div>
              </div>

              <span className="w-8 text-right font-mono text-xs text-muted-foreground">
                {confPct}%
              </span>

              {/* Regime */}
              <span className="hidden w-16 text-right font-mono text-[10px] text-muted-foreground sm:block">
                {s.regime ?? "—"}
              </span>
            </motion.div>
          );
        })}

        {sorted.length === 0 && (
          <p className="py-4 text-center font-mono text-xs text-muted-foreground">
            No signals yet
          </p>
        )}
      </div>
    </div>
  );
}
