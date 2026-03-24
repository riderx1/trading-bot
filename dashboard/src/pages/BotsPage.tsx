import { useStatus } from "@/hooks/use-trading-data";
import { BotOrchestra } from "@/components/dashboard/BotOrchestra";
import { useSymbol } from "@/contexts/SymbolContext";

export default function BotsPage() {
  const { symbol } = useSymbol();
  const status = useStatus(symbol);
  const s = status.data;

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Bot Orchestra</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Each strategy bot votes independently. The orchestrator aggregates their signals into a final consensus decision.
      </p>
      <div className="max-w-xl">
        <BotOrchestra decision={s?.orchestrated_decision ?? null} />
      </div>
    </div>
  );
}
