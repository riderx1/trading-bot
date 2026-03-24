import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ArbitrageDecision, DirectionalDecision } from "@/lib/api";

interface Props {
  symbol: string;
  decision: DirectionalDecision | null;
  arbitrageDecision: ArbitrageDecision | null;
}

export function DecisionStickyBar({ symbol, decision, arbitrageDecision }: Props) {
  const bias = decision?.bias ?? "NO TRADE";
  const confidence = Math.round((decision?.confidence ?? 0) * 100);
  const positionSize = getPositionSize(decision?.conviction, bias);
  const BiasIcon = bias === "LONG" ? ArrowUpRight : bias === "SHORT" ? ArrowDownRight : Minus;
  const arbActive = Boolean(arbitrageDecision?.active);

  return (
    <div className="sticky top-[3.75rem] z-40 overflow-hidden rounded-xl border border-border bg-card/90 shadow-[0_18px_50px_rgba(0,0,0,0.22)] backdrop-blur-md">
      <div className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-11 w-11 items-center justify-center rounded-lg ${
              bias === "LONG"
                ? "bg-bullish/12 text-bullish"
                : bias === "SHORT"
                ? "bg-bearish/12 text-bearish"
                : "bg-muted text-muted-foreground"
            }`}
          >
            <BiasIcon className="h-5 w-5" />
          </div>
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">Primary Decision</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span
                className={`font-mono text-xl font-semibold ${
                  bias === "LONG"
                    ? "text-bullish"
                    : bias === "SHORT"
                    ? "text-bearish"
                    : "text-muted-foreground"
                }`}
              >
                {symbol.replace("USDT", "")} {bias}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{confidence}% confidence</span>
              <span className="font-mono text-xs text-muted-foreground">{positionSize} size</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge label="Conviction" value={decision?.conviction ?? "LOW"} />
          <Badge label="Setup" value={decision?.setup_quality ?? "POOR"} />
          <Badge label="Arb" value={arbActive ? `${Math.round((arbitrageDecision?.edge ?? 0) * 10000) / 100}% active` : "idle"} tone="blue" />
        </div>
      </div>
    </div>
  );
}

function Badge({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "blue";
}) {
  return (
    <div className={`rounded-full border px-3 py-1 ${tone === "blue" ? "border-sky-500/30 bg-sky-500/10" : "border-border bg-secondary/40"}`}>
      <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className={`ml-2 font-mono text-xs ${tone === "blue" ? "text-sky-300" : "text-foreground"}`}>{value}</span>
    </div>
  );
}

function getPositionSize(conviction: DirectionalDecision["conviction"] | undefined, bias: DirectionalDecision["bias"] | "NO TRADE") {
  if (bias === "NO TRADE") return "No";
  if (conviction === "HIGH") return "Full";
  if (conviction === "MEDIUM") return "Medium";
  return "Small";
}