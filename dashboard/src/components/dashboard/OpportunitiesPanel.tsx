import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, ChevronUp, Target } from "lucide-react";
import type { Opportunity } from "@/lib/api";

interface Props {
  opportunities: Opportunity[];
}

export function OpportunitiesPanel({ opportunities }: Props) {
  const [filter, setFilter] = useState<"ALL" | "HIGH EDGE" | "WEAK" | "SCALP">("ALL");

  const filtered = useMemo(() => {
    return opportunities.filter((opp) => {
      if (filter === "HIGH EDGE") return opp.edge >= 0.03;
      if (filter === "WEAK") return opp.confidence < 0.5;
      if (filter === "SCALP") return String(opp.strategy || "").toLowerCase() === "scalping";
      return true;
    });
  }, [filter, opportunities]);

  const directional = filtered.filter((opp) => !opp.arb_type && opp.strategy !== "arbitrage" && opp.strategy !== "perp_arb");
  const arbitrage = filtered.filter((opp) => Boolean(opp.arb_type) || opp.strategy === "arbitrage" || opp.strategy === "perp_arb");

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Target className="h-3.5 w-3.5 text-accent" />
          <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
            Opportunities
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["ALL", "HIGH EDGE", "WEAK", "SCALP"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setFilter(option)}
              className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${filter === option ? "border-primary/40 bg-primary/10 text-primary" : "border-border bg-secondary/40 text-muted-foreground"}`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border py-8 text-center">
          <p className="font-mono text-xs text-muted-foreground">No opportunities — system is selective</p>
          <p className="mt-1 font-mono text-[10px] text-muted-foreground/60">This is a valid state</p>
        </div>
      ) : (
        <div className="space-y-5">
          <OpportunityGroup title="Directional" opportunities={directional} />
          <OpportunityGroup title="Arbitrage" opportunities={arbitrage} />
        </div>
      )}
    </div>
  );
}

function OpportunityGroup({ title, opportunities }: { title: string; opportunities: Opportunity[] }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{title}</span>
        <span className="font-mono text-[10px] text-muted-foreground">{opportunities.length} rows</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-border">
        <div className="grid grid-cols-[1.1fr_0.9fr_0.7fr_0.7fr_0.8fr_1fr_0.7fr] gap-3 border-b border-border bg-secondary/25 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          <span>Market</span>
          <span>Type</span>
          <span>Side</span>
          <span>Edge</span>
          <span>Confidence</span>
          <span>Strategy</span>
          <span>Time</span>
        </div>

        {opportunities.length === 0 ? (
          <div className="px-4 py-6 text-center font-mono text-xs text-muted-foreground">No rows in this group</div>
        ) : (
          <div className="divide-y divide-border/70">
            {opportunities.map((opp, index) => (
              <OpportunityRow key={opp.id} opp={opp} index={index} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function OpportunityRow({ opp, index }: { opp: Opportunity; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="bg-card"
    >
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="grid w-full grid-cols-[1.1fr_0.9fr_0.7fr_0.7fr_0.8fr_1fr_0.7fr] gap-3 px-4 py-3 text-left transition-colors hover:bg-secondary/15"
      >
        <span className="truncate font-mono text-xs text-foreground">{opp.market_name}</span>
        <span className="font-mono text-xs text-muted-foreground">{opp.arb_type ?? opp.strategy}</span>
        <span className={`font-mono text-xs ${opp.side === "YES" ? "text-bullish" : "text-bearish"}`}>{opp.side}</span>
        <span className="font-mono text-xs text-accent">{(opp.edge * 100).toFixed(2)}%</span>
        <span className="font-mono text-xs text-foreground">{Math.round(opp.confidence * 100)}%</span>
        <span className="font-mono text-xs text-muted-foreground">{opp.strategy}</span>
        <span className="flex items-center justify-between font-mono text-xs text-muted-foreground">
          {opp.timeframe}
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </span>
      </button>

      {expanded ? (
        <div className="border-t border-border/70 bg-secondary/20 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Reasoning</p>
          <p className="mt-2 text-sm text-foreground">{opp.reasoning}</p>
        </div>
      ) : null}
    </motion.div>
  );
}
