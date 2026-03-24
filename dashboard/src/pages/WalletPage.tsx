import { useWallets } from "@/hooks/use-trading-data";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function WalletPage() {
  const wallets = useWallets();
  const data = wallets.data;

  const renderVenueRows = (rows: Record<string, { balance: number; pnl: number }>) => {
    const entries = Object.entries(rows || {});
    if (entries.length === 0) {
      return <p className="font-mono text-xs text-muted-foreground">No wallets found.</p>;
    }
    return (
      <div className="space-y-2">
        {entries.map(([name, row]) => (
          <div key={name} className="flex items-center justify-between rounded-md border border-border bg-secondary/20 px-3 py-2">
            <span className="font-mono text-xs text-muted-foreground">{name}</span>
            <div className="text-right">
              <div className="font-mono text-xs text-foreground">${Number(row.balance ?? 0).toFixed(2)}</div>
              <div className={`font-mono text-[10px] ${Number(row.pnl ?? 0) >= 0 ? "text-bullish" : "text-bearish"}`}>
                {Number(row.pnl ?? 0) >= 0 ? "+" : ""}{Number(row.pnl ?? 0).toFixed(2)}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Paper Wallets</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Per-strategy wallet balances, PnL tracking, and portfolio management.
      </p>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="font-mono text-sm text-foreground">Total Portfolio: ${Number(data?.total ?? 0).toFixed(2)}</p>
      </div>
      <div className="max-w-2xl rounded-lg border border-border bg-card p-4">
        <Tabs defaultValue="polymarket">
          <TabsList className="mb-4">
            <TabsTrigger value="polymarket">Polymarket</TabsTrigger>
            <TabsTrigger value="hyperliquid">Hyperliquid</TabsTrigger>
          </TabsList>
          <TabsContent value="polymarket">
            {renderVenueRows(data?.polymarket ?? {})}
          </TabsContent>
          <TabsContent value="hyperliquid">
            {renderVenueRows(data?.hyperliquid ?? {})}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
