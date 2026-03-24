import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowUpRight, ArrowDownRight, Minus, ChevronDown, ChevronUp } from "lucide-react";
import type { DirectionalDecision, Signal } from "@/lib/api";

interface Props {
  decision: DirectionalDecision | null;
  latestSignal: Signal | null;
  explainability?: {
    why_long: string[];
    why_not_stronger: string[];
  } | null;
}

export function DecisionHero({ decision, latestSignal, explainability }: Props) {
  const [showDetails, setShowDetails] = useState(false);
  const direction = decision?.bias === "LONG" ? 1 : decision?.bias === "SHORT" ? -1 : 0;
  const confidence = decision?.confidence ?? 0;

  const isBullish = direction > 0;
  const isBearish = direction < 0;

  const biasLabel = isBullish ? "LONG" : isBearish ? "SHORT" : "NO TRADE";
  const BiasIcon = isBullish ? ArrowUpRight : isBearish ? ArrowDownRight : Minus;

  const confidencePct = Math.round(confidence * 100);
  const signalStrength = decision?.top_strategy ?? latestSignal?.signal_strength ?? "—";
  const regime = latestSignal?.regime ?? "—";
  const conviction = decision?.conviction ?? "LOW";
  const setupQuality = decision?.setup_quality ?? "POOR";
  const entryTiming = decision?.entry_timing ?? "EARLY";
  const topBot = decision?.top_bot ?? "—";
  const horizon = decision?.time_horizon ?? "short";
  const positionSize = getPositionSize(conviction, biasLabel);
  const detailRows = [
    { label: "Reasoning", value: decision?.reasoning ?? "Waiting for data..." },
    { label: "Regime", value: regime },
    { label: "Entry Timing", value: entryTiming },
    { label: "TA Alignment", value: signalStrength },
    { label: "Score Breakdown", value: `${topBot} · ${horizon} horizon · ${(decision?.weighted_bias ?? 0).toFixed(2)} weighted bias` },
  ];
  const regimeTone = getRegimeTone(regime);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="relative overflow-hidden rounded-xl border border-border bg-card p-6 shadow-[0_18px_45px_rgba(0,0,0,0.22)]"
      style={{
        boxShadow: isBullish
          ? "0 0 40px hsl(142 60% 45% / 0.08)"
          : isBearish
          ? "0 0 40px hsl(0 72% 55% / 0.08)"
          : "none",
      }}
    >
      {/* Subtle gradient overlay */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          background: isBullish
            ? "linear-gradient(135deg, hsl(142 60% 45%), transparent 60%)"
            : isBearish
            ? "linear-gradient(135deg, hsl(0 72% 55%), transparent 60%)"
            : "none",
        }}
      />

      <div className="relative z-10">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-primary animate-pulse-live" />
            <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
              Directional Decision
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowDetails((current) => !current)}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary/40 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-foreground"
          >
            Show Details
            {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>

        <div className="mb-6 flex items-start gap-4">
          <div
            className={`flex h-16 w-16 items-center justify-center rounded-xl ${
              isBullish ? "bg-bullish/10 text-bullish" : isBearish ? "bg-bearish/10 text-bearish" : "bg-muted text-muted-foreground"
            }`}
          >
            <BiasIcon className="h-8 w-8" />
          </div>
          <div>
            <h1
              className={`font-mono text-4xl font-bold tracking-tight ${
                isBullish ? "text-bullish" : isBearish ? "text-bearish" : "text-muted-foreground"
              }`}
            >
              {biasLabel}
            </h1>
            <p className="mt-2 font-mono text-sm text-muted-foreground">{topBot} driving current bias</p>
            <span className={`mt-2 inline-flex rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ${regimeTone}`}>
              Regime {regime}
            </span>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <PrimaryMetric label="Confidence" value={`${confidencePct}%`} emphasis />
          <PrimaryMetric label="Conviction" value={conviction} />
          <PrimaryMetric label="Setup Quality" value={setupQuality} />
          <PrimaryMetric label="Position Size" value={positionSize} />
          <PrimaryMetric label="Horizon" value={horizon} />
        </div>

        {showDetails ? (
          <div className="mt-5 grid gap-3 rounded-xl border border-border bg-secondary/25 p-4 md:grid-cols-2">
            {detailRows.map((row) => (
              <div key={row.label} className="rounded-lg border border-border/70 bg-background/30 px-3 py-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{row.label}</p>
                <p className="mt-2 text-sm text-foreground">{row.value}</p>
              </div>
            ))}
          </div>
        ) : null}

        {explainability ? (
          <div className="mt-5 grid gap-3 rounded-xl border border-border bg-secondary/25 p-4 md:grid-cols-2">
            <div className="rounded-lg border border-border/70 bg-background/30 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bullish">Why {biasLabel === "NO TRADE" ? "Bias" : biasLabel}</p>
              <ul className="mt-2 space-y-1 text-sm text-foreground">
                {(explainability.why_long || []).slice(0, 3).map((line) => (
                  <li key={line}>+ {line}</li>
                ))}
                {(explainability.why_long || []).length === 0 ? <li>+ No strong directional drivers</li> : null}
              </ul>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/30 px-3 py-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-warning">Weakness</p>
              <ul className="mt-2 space-y-1 text-sm text-foreground">
                {(explainability.why_not_stronger || []).slice(0, 3).map((line) => (
                  <li key={line}>- {line}</li>
                ))}
                {(explainability.why_not_stronger || []).length === 0 ? <li>- No major conflicts detected</li> : null}
              </ul>
            </div>
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}

function PrimaryMetric({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-secondary/40 px-4 py-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className={`mt-2 font-mono capitalize ${emphasis ? "text-2xl font-bold text-foreground" : "text-sm font-semibold text-foreground"}`}>{value}</p>
    </div>
  );
}

function getPositionSize(conviction: string, biasLabel: string) {
  if (biasLabel === "NO TRADE") return "No position";
  if (conviction === "HIGH") return "Full size";
  if (conviction === "MEDIUM") return "Medium size";
  return "Small size";
}

function getRegimeTone(regime: string) {
  const normalized = String(regime || "").toUpperCase();
  if (normalized.includes("TREND")) return "border-bullish/30 bg-bullish/10 text-bullish";
  if (normalized.includes("REVERS")) return "border-warning/30 bg-warning/10 text-warning";
  if (normalized.includes("CHOP")) return "border-muted-foreground/30 bg-muted text-muted-foreground";
  return "border-border bg-secondary/40 text-muted-foreground";
}
