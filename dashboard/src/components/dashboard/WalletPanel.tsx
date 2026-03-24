import { motion } from "framer-motion";
import { Wallet, RotateCcw } from "lucide-react";
import type { VenueWalletSnapshot } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

const STRATEGY_LABELS: Record<string, string> = {
  momentum: "Momentum",
  ta_confluence: "TA",
  reversal: "Reversal",
  yes_no: "Yes/No Arb",
  model_vs_market: "Model/FV",
  cross_venue: "Cross Venue",
  scalping: "Scalping",
};

interface Props {
  wallets: VenueWalletSnapshot | undefined;
}

export function WalletPanel({ wallets }: Props) {
  const qc = useQueryClient();
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    setResetting(true);
    try {
      await api.resetWallets(true);
      qc.invalidateQueries({ queryKey: ["wallets"] });
      qc.invalidateQueries({ queryKey: ["status"] });
      qc.invalidateQueries({ queryKey: ["performance"] });
      qc.invalidateQueries({ queryKey: ["rankings"] });
      qc.invalidateQueries({ queryKey: ["active-paper-trades"] });
      qc.invalidateQueries({ queryKey: ["recent-trades"] });
    } finally {
      setResetting(false);
    }
  };

  const total = wallets?.total ?? 0;
  const initial = 80;
  const pnl = total - initial;
  const pnlPct = initial > 0 ? (pnl / initial) * 100 : 0;

  const entries = [
    ...Object.entries(wallets?.polymarket ?? {}).map(([strategy, row]) => ({
      strategy,
      venue: "polymarket",
      balance: Number(row.balance ?? 0),
      pnl: Number(row.pnl ?? 0),
    })),
    ...Object.entries(wallets?.hyperliquid ?? {}).map(([strategy, row]) => ({
      strategy,
      venue: "hyperliquid",
      balance: Number(row.balance ?? 0),
      pnl: Number(row.pnl ?? 0),
    })),
  ];

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Portfolio
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={handleReset}
          disabled={resetting}
        >
          <RotateCcw className={`h-3 w-3 ${resetting ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Total equity */}
      <div className="mb-4">
        <p className="font-mono text-2xl font-bold text-foreground">
          ${total.toFixed(2)}
        </p>
        <p
          className={`font-mono text-xs ${
            pnl >= 0 ? "text-bullish" : "text-bearish"
          }`}
        >
          {pnl >= 0 ? "+" : ""}
          {pnl.toFixed(2)} ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%)
        </p>
      </div>

      {/* Per-strategy breakdown */}
      <div className="space-y-2">
        {entries.map(({ strategy, venue, balance, pnl: stratPnl }) => {
            const label = STRATEGY_LABELS[strategy] ?? strategy;

            return (
              <motion.div
                key={`${venue}:${strategy}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center gap-2"
              >
                <div className={`h-2 w-2 rounded-full ${venue === "polymarket" ? "bg-yellow-400" : "bg-cyan-400"}`} />
                <span className="flex-1 font-mono text-xs text-muted-foreground">{label}</span>
                <span className="font-mono text-xs font-medium text-foreground">
                  ${balance.toFixed(2)}
                </span>
                <span
                  className={`w-14 text-right font-mono text-[10px] ${
                    stratPnl >= 0 ? "text-bullish" : "text-bearish"
                  }`}
                >
                  {stratPnl >= 0 ? "+" : ""}{stratPnl.toFixed(2)}
                </span>
              </motion.div>
            );
          })}
      </div>
    </div>
  );
}
