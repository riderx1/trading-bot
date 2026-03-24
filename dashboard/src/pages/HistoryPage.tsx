import { useSignals, useLogs } from "@/hooks/use-trading-data";
import { SignalsPanel } from "@/components/dashboard/SignalsPanel";
import { LogsPanel } from "@/components/dashboard/LogsPanel";
import { useSymbol } from "@/contexts/SymbolContext";

export default function HistoryPage() {
  const { symbol } = useSymbol();
  const signals = useSignals(50);
  const logs = useLogs();

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">History & Logs</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Signal history across all timeframes and system event logs.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <SignalsPanel signals={signals.data?.signals ?? []} />
        <LogsPanel logs={logs.data?.logs ?? []} />
      </div>
    </div>
  );
}
