import { motion } from "framer-motion";
import { Target } from "lucide-react";
import type { Opportunity } from "@/lib/api";

interface Props {
  opportunities: Opportunity[];
}

export function OpportunitiesPanel({ opportunities }: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="h-3.5 w-3.5 text-accent" />
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Opportunities
          </span>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {opportunities.length} active
        </span>
      </div>

      {opportunities.length === 0 ? (
        <div className="rounded-md border border-dashed border-border py-6 text-center">
          <p className="font-mono text-xs text-muted-foreground">No opportunities — system is selective</p>
          <p className="mt-1 font-mono text-[10px] text-muted-foreground/60">This is a valid state</p>
        </div>
      ) : (
        <div className="space-y-2">
          {opportunities.map((opp, i) => (
            <motion.div
              key={opp.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-md border border-border bg-secondary/30 p-3"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="font-mono text-xs font-medium text-foreground">
                  {opp.symbol}
                  <span className="ml-1.5 text-muted-foreground">{opp.timeframe}</span>
                </span>
                <span
                  className={`rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                    opp.side === "YES"
                      ? "bg-bullish/10 text-bullish"
                      : "bg-bearish/10 text-bearish"
                  }`}
                >
                  {opp.side}
                </span>
              </div>
              <p className="mb-2 line-clamp-1 text-[11px] text-muted-foreground">
                {opp.market_name}
              </p>
              <div className="flex items-center gap-3 font-mono text-[10px]">
                <span className="text-muted-foreground">
                  Edge: <span className="text-accent font-medium">{(opp.edge * 100).toFixed(1)}%</span>
                </span>
                <span className="text-muted-foreground">
                  Conf: <span className="text-foreground">{(opp.confidence * 100).toFixed(0)}%</span>
                </span>
                <span className="text-muted-foreground">
                  Price: <span className="text-foreground">{opp.yes_price.toFixed(2)}</span>
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
