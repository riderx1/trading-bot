import { motion } from "framer-motion";
import { Wallet, RotateCcw } from "lucide-react";
import type { WalletSnapshot } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

const STRATEGY_COLORS: Record<string, string> = {
  momentum: "hsl(142, 60%, 45%)",
  ta_confluence: "hsl(200, 70%, 50%)",
  reversal: "hsl(280, 60%, 55%)",
  yes_no: "hsl(45, 90%, 55%)",
  model_vs_market: "hsl(280, 60%, 65%)",
  cross_venue: "hsl(210, 75%, 60%)",
  scalping: "hsl(18, 90%, 58%)",
};

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
  wallets: WalletSnapshot | undefined;
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

  const total = wallets?.total_equity_usdc ?? 0;
  const initial = 40;
  const pnl = total - initial;
  const pnlPct = initial > 0 ? (pnl / initial) * 100 : 0;

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
        {wallets &&
          Object.entries(wallets.bots).map(([strategy, wallet]) => {
            const label = STRATEGY_LABELS[strategy] ?? strategy;
            const color = STRATEGY_COLORS[strategy] ?? "hsl(215, 12%, 50%)";
            const stratPnl = wallet.equity_usdc - 10;

            return (
              <motion.div
                key={strategy}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center gap-2"
              >
                <div className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="flex-1 font-mono text-xs text-muted-foreground">{label}</span>
                <span className="font-mono text-xs font-medium text-foreground">
                  ${wallet.equity_usdc.toFixed(2)}
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
