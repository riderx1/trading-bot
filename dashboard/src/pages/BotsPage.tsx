import { useStatus, useStrategyRankings } from "@/hooks/use-trading-data";
import { BotOrchestra } from "@/components/dashboard/BotOrchestra";
import { useSymbol } from "@/contexts/SymbolContext";

export default function BotsPage() {
  const { symbol } = useSymbol();
  const status = useStatus(symbol);
  const rankings = useStrategyRankings();
  const s = status.data;

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Bot Orchestra</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Each directional bot votes independently. The orchestrator now separates directional conviction from arbitrage opportunity detection.
      </p>
      <div className="max-w-xl">
        <BotOrchestra decision={s?.directional_decision ?? null} rankings={rankings.data?.strategies ?? []} />
      </div>
    </div>
  );
}
