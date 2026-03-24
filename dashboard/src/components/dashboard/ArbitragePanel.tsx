import { useState } from "react";
import { Shuffle, ChevronLeft, ChevronRight } from "lucide-react";
import type { ArbitrageOpportunity } from "@/lib/api";

interface Props {
  opportunities: ArbitrageOpportunity[];
  arbType: string;
  status: string;
  page: number;
  loading?: boolean;
  hasMore?: boolean;
  onArbTypeChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onPageChange: (value: number) => void;
}

const typeTone = (arbType: string) => {
  if (arbType === "funding_arb") return "text-[hsl(280,60%,65%)] bg-[hsl(280,60%,55%,0.10)]";
  if (arbType === "basis_arb") return "text-warning bg-warning/10";
  if (arbType === "volatility") return "text-[hsl(210,75%,65%)] bg-[hsl(210,75%,55%,0.10)]";
  return "text-muted-foreground bg-muted";
};

export function ArbitragePanel({
  opportunities,
  arbType,
  status,
  page,
  loading,
  hasMore,
  onArbTypeChange,
  onStatusChange,
  onPageChange,
}: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Shuffle className="h-3.5 w-3.5 text-accent" />
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Arbitrage Opportunities
          </span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={arbType}
            onChange={(e) => onArbTypeChange(e.target.value)}
            className="rounded-md border border-border bg-secondary/40 px-2 py-1 font-mono text-[10px] text-foreground"
          >
            <option value="ALL">All types</option>
            <option value="funding_arb">funding_arb</option>
            <option value="basis_arb">basis_arb</option>
            <option value="volatility">volatility</option>
          </select>
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value)}
            className="rounded-md border border-border bg-secondary/40 px-2 py-1 font-mono text-[10px] text-foreground"
          >
            <option value="ALL">All status</option>
            <option value="open">open</option>
            <option value="executed">executed</option>
          </select>
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] text-muted-foreground">
          Page {page + 1}{loading ? " · loading" : ""}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPageChange(Math.max(0, page - 1))}
            disabled={page === 0}
            className="rounded border border-border bg-secondary/40 p-1 text-muted-foreground disabled:opacity-40"
          >
            <ChevronLeft className="h-3 w-3" />
          </button>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={!hasMore}
            className="rounded border border-border bg-secondary/40 p-1 text-muted-foreground disabled:opacity-40"
          >
            <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {opportunities.length === 0 ? (
        <div className="rounded-md border border-dashed border-border py-6 text-center">
          <p className="font-mono text-xs text-muted-foreground">No arbitrage opportunities logged</p>
        </div>
      ) : (
        <div className="space-y-2">
          {opportunities.map((opp) => (
            <div key={opp.id} className="rounded-md border border-border bg-secondary/30 p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-medium text-foreground">
                  {opp.symbol ?? "--"}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${typeTone(opp.arb_type)}`}>
                    {opp.arb_type}
                  </span>
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {opp.status}
                  </span>
                </div>
              </div>
              <p className="mb-2 line-clamp-1 text-[11px] text-muted-foreground">{opp.market_name}</p>
              <div className="flex flex-wrap items-center gap-3 font-mono text-[10px]">
                <span className="text-muted-foreground">Edge <span className="text-foreground">{Math.round(Number(opp.edge_bp || 0))}bp</span></span>
                {opp.p_fair != null ? <span className="text-muted-foreground">Fair <span className="text-foreground">{Math.round(Number(opp.p_fair) * 100)}%</span></span> : null}
                {opp.p_mkt != null ? <span className="text-muted-foreground">Mkt <span className="text-foreground">{Math.round(Number(opp.p_mkt) * 100)}%</span></span> : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}