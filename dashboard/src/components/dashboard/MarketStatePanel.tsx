import type { DirectionalDecision, MicroData, PerpBasisSnapshot, Signal } from "@/lib/api";

interface Props {
  symbol: string;
  latestSignal: Signal | null;
  decision: DirectionalDecision | null;
  microData: MicroData | null | undefined;
  perpBasis: PerpBasisSnapshot | null;
}

export function MarketStatePanel({ symbol, latestSignal, decision, microData, perpBasis }: Props) {
  const state = getStateLabel(decision?.bias ?? "NO TRADE", decision?.confidence ?? 0, latestSignal?.regime ?? null);
  const trend = latestSignal?.trend ? latestSignal.trend.toUpperCase() : "NEUTRAL";
  const ta = latestSignal?.signal_strength ? latestSignal.signal_strength.toUpperCase() : "MIXED";
  const regime = latestSignal?.regime?.toUpperCase() ?? "UNDEFINED";
  const move = `${((microData?.move_pct_short ?? 0) * 100).toFixed(2)}%`;
  const spread = `${(microData?.spread_bps ?? 0).toFixed(1)} bp`;
  const basis = perpBasis?.basis_diff != null ? `${Number(perpBasis.basis_diff).toFixed(2)}%` : "n/a";

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-[0_10px_35px_rgba(0,0,0,0.18)]">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">Section 2</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">Market State</h2>
        </div>
        <p className="font-mono text-[11px] text-muted-foreground">Context condensed into one view</p>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-secondary/20">
        <div className="grid grid-cols-[1fr_repeat(4,minmax(0,0.8fr))] gap-3 border-b border-border/80 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
          <span>Symbol</span>
          <span>State</span>
          <span>Trend</span>
          <span>TA</span>
          <span>Regime</span>
        </div>
        <div className="grid grid-cols-[1fr_repeat(4,minmax(0,0.8fr))] gap-3 px-4 py-4 text-sm">
          <span className="font-mono font-semibold text-foreground">{symbol.replace("USDT", "")}</span>
          <span className="font-mono text-foreground">{state}</span>
          <span className="font-mono text-foreground">{trend}</span>
          <span className="font-mono text-foreground">{ta}</span>
          <span className="font-mono text-foreground">{regime}</span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <ContextMetric label="Micro Move" value={move} />
        <ContextMetric label="Spread" value={spread} />
        <ContextMetric label="Perp Basis" value={basis} />
      </div>
    </section>
  );
}

function ContextMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-secondary/35 px-4 py-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function getStateLabel(bias: DirectionalDecision["bias"], confidence: number, regime: string | null) {
  if (bias === "NO TRADE") return regime ? `WAIT / ${regime.toUpperCase()}` : "WAIT";
  const intensity = confidence >= 0.7 ? "STRONG" : confidence >= 0.5 ? "ACTIVE" : "LIGHT";
  return `${intensity} ${bias}`;
}