import { useWallets } from "@/hooks/use-trading-data";
import { WalletPanel } from "@/components/dashboard/WalletPanel";

export default function WalletPage() {
  const wallets = useWallets();

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Paper Wallets</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Per-strategy wallet balances, PnL tracking, and portfolio management.
      </p>
      <div className="max-w-md">
        <WalletPanel wallets={wallets.data} />
      </div>
    </div>
  );
}
