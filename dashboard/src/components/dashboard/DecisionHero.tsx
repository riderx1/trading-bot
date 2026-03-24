import { motion } from "framer-motion";
import { ArrowUpRight, ArrowDownRight, Minus, Zap, Shield, Target } from "lucide-react";
import type { OrchestratedDecision, Signal } from "@/lib/api";

interface Props {
  decision: OrchestratedDecision | null;
  latestSignal: Signal | null;
}

export function DecisionHero({ decision, latestSignal }: Props) {
  const direction = decision?.direction ?? 0;
  const confidence = decision?.confidence ?? 0;

  const isBullish = direction > 0;
  const isBearish = direction < 0;

  const biasLabel = isBullish ? "LONG" : isBearish ? "SHORT" : "NEUTRAL";
  const BiasIcon = isBullish ? ArrowUpRight : isBearish ? ArrowDownRight : Minus;

  const confidencePct = Math.round(confidence * 100);
  const signalStrength = latestSignal?.signal_strength ?? "—";
  const regime = latestSignal?.regime ?? "—";

  // Derive conviction from confidence
  const conviction = confidence >= 0.6 ? "HIGH" : confidence >= 0.4 ? "MEDIUM" : "LOW";
  const setupQuality = confidence >= 0.55 ? "READY" : confidence >= 0.35 ? "DEVELOPING" : "POOR";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="relative overflow-hidden rounded-lg border border-border bg-card p-6"
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
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-primary animate-pulse-live" />
            <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Decision Engine
            </span>
          </div>
          <span className="font-mono text-xs text-muted-foreground">
            {decision?.symbol ?? "—"}
          </span>
        </div>

        {/* Main bias display */}
        <div className="mb-6 flex items-center gap-4">
          <div
            className={`flex h-16 w-16 items-center justify-center rounded-lg ${
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
            <p className="mt-1 text-sm text-muted-foreground">
              {decision?.reasoning ?? "Waiting for data..."}
            </p>
          </div>
        </div>

        {/* Confidence bar */}
        <div className="mb-6">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-xs text-muted-foreground">Confidence</span>
            <span className="font-mono text-sm font-semibold text-foreground">{confidencePct}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidencePct}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className={`h-full rounded-full ${
                isBullish ? "bg-bullish" : isBearish ? "bg-bearish" : "bg-muted-foreground"
              }`}
            />
          </div>
        </div>

        {/* Stat chips */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatChip icon={Zap} label="Conviction" value={conviction} />
          <StatChip icon={Target} label="Setup" value={setupQuality} />
          <StatChip icon={Shield} label="Regime" value={regime} />
          <StatChip
            icon={Zap}
            label="Strength"
            value={signalStrength}
          />
        </div>
      </div>
    </motion.div>
  );
}

function StatChip({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-secondary/50 px-3 py-2">
      <div className="flex items-center gap-1.5">
        <Icon className="h-3 w-3 text-muted-foreground" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      </div>
      <p className="mt-1 font-mono text-sm font-medium capitalize text-foreground">{value}</p>
    </div>
  );
}
