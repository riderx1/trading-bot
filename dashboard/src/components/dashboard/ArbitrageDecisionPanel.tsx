import { ArrowLeftRight, Activity, Shield } from "lucide-react";
import type { ArbitrageDecision } from "@/lib/api";

interface Props {
  decision: ArbitrageDecision | null;
}

export function ArbitrageDecisionPanel({ decision }: Props) {
  const active = Boolean(decision?.active);
  const edgePct = ((decision?.edge ?? 0) * 100).toFixed(2);
  const confidencePct = Math.round((decision?.confidence ?? 0) * 100);
  const tone = active ? "border-sky-500/30 bg-sky-500/8" : "border-border bg-secondary/20";

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[0_12px_32px_rgba(0,0,0,0.18)]">
      <div className="mb-4 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
          Arbitrage Decision
        </span>
        <span className={`rounded-full px-2.5 py-1 font-mono text-[10px] uppercase ${active ? "bg-sky-500/15 text-sky-300" : "bg-secondary/60 text-muted-foreground"}`}>
          {active ? "active" : "idle"}
        </span>
      </div>

      <div className={`rounded-xl border p-4 ${tone}`}>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Best Opportunity</p>
        <p className="mt-2 text-lg font-semibold text-foreground">{decision?.market || "No arbitrage opportunities right now"}</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Metric icon={ArrowLeftRight} label="Type" value={decision?.type || "none"} />
          <Metric icon={Activity} label="Edge" value={`${edgePct}%`} />
          <Metric icon={Shield} label="Confidence" value={`${confidencePct}%`} />
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-secondary/30 px-4 py-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Action</p>
        <p className="mt-2 text-sm text-foreground">{decision?.execution_note || "No arbitrage opportunities right now"}</p>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-background/30 px-3 py-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      </div>
      <span className="mt-2 block font-mono text-sm text-foreground">{value}</span>
    </div>
  );
}