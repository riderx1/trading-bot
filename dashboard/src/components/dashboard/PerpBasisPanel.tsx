import { BarChart3 } from "lucide-react";
import type { PerpBasisSnapshot } from "@/lib/api";

interface Props {
  latest: PerpBasisSnapshot | null;
  history: PerpBasisSnapshot[];
  symbol: string;
}

function toFundingPct(v?: number | null) {
  return `${((Number(v) || 0) * 100).toFixed(3)}%`;
}

function toBasisBp(row: PerpBasisSnapshot) {
  const ref = Math.max(Number(row.binance_perp_price || 0), Number(row.hl_perp_price || 0), 1);
  return ((Number(row.basis_diff || 0) / ref) * 10000).toFixed(1);
}

export function PerpBasisPanel({ latest, history, symbol }: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-3.5 w-3.5 text-accent" />
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Perp Basis / Funding
          </span>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{symbol}</span>
      </div>

      {!latest ? (
        <div className="rounded-md border border-dashed border-border py-6 text-center">
          <p className="font-mono text-xs text-muted-foreground">No perp basis snapshots yet</p>
        </div>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            <Metric label="Bin Spot" value={Number(latest.binance_spot_price || 0).toFixed(2)} />
            <Metric label="Bin Perp" value={Number(latest.binance_perp_price || 0).toFixed(2)} />
            <Metric label="HL Perp" value={Number(latest.hl_perp_price || 0).toFixed(2)} />
            <Metric label="Basis" value={`${toBasisBp(latest)}bp`} />
            <Metric label="Bin Funding" value={toFundingPct(latest.binance_funding_rate)} />
            <Metric label="HL Funding" value={toFundingPct(latest.hl_funding_rate)} />
            <Metric label="Spread" value={toFundingPct(latest.funding_spread)} />
            <Metric label="HL OI" value={Math.round(Number(latest.hl_open_interest || 0)).toLocaleString()} />
          </div>

          <div className="space-y-1.5">
            {history.slice(0, 8).map((row) => (
              <div key={row.id} className="flex items-center gap-2 rounded-md border border-border bg-secondary/30 px-3 py-2 font-mono text-[10px]">
                <span className="w-16 text-muted-foreground">
                  {new Date(row.timestamp).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
                <span className="w-16 text-foreground">{toBasisBp(row)}bp</span>
                <span className="w-16 text-muted-foreground">{toFundingPct(row.funding_spread)}</span>
                <span className="truncate text-muted-foreground">
                  {Number(row.binance_perp_price || 0).toFixed(2)} / {Number(row.hl_perp_price || 0).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-secondary/30 px-3 py-2">
      <div className="font-mono text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-foreground">{value}</div>
    </div>
  );
}