import { useState } from "react";
import { useStatus, useSignalsForSymbol, useOpportunities, useArbitrageOpportunities, usePerpBasisLatest, usePerpBasisHistory, useWallets, usePerformance, useStrategyRankings, useLogs, useActivePaperTrades, useRecentTrades, useScalpPerformance } from "@/hooks/use-trading-data";
import { DecisionHero } from "@/components/dashboard/DecisionHero";
import { BotOrchestra } from "@/components/dashboard/BotOrchestra";
import { WalletPanel } from "@/components/dashboard/WalletPanel";
import { ActiveTradesPanel } from "@/components/dashboard/ActiveTradesPanel";
import { SignalsPanel } from "@/components/dashboard/SignalsPanel";
import { OpportunitiesPanel } from "@/components/dashboard/OpportunitiesPanel";
import { ArbitragePanel } from "@/components/dashboard/ArbitragePanel";
import { PerpBasisPanel } from "@/components/dashboard/PerpBasisPanel";
import { PerformancePanel } from "@/components/dashboard/PerformancePanel";
import { ScalpPanel } from "@/components/dashboard/ScalpPanel";
import { SystemStatus } from "@/components/dashboard/SystemStatus";
import { LogsPanel } from "@/components/dashboard/LogsPanel";
import { PriceChart } from "@/components/dashboard/PriceChart";
import { useSymbol } from "@/contexts/SymbolContext";

const Index = () => {
  const { symbol } = useSymbol();
  const [arbType, setArbType] = useState("ALL");
  const [arbStatus, setArbStatus] = useState("open");
  const [arbPage, setArbPage] = useState(0);
  const status = useStatus(symbol);
  const signals = useSignalsForSymbol(symbol, 20);
  const opportunities = useOpportunities(symbol, 12);
  const arbOpportunities = useArbitrageOpportunities(symbol, arbType, arbStatus, 12, arbPage * 12);
  const perpBasisLatest = usePerpBasisLatest(symbol);
  const perpBasisHistory = usePerpBasisHistory(symbol, 20);
  const wallets = useWallets();
  const performance = usePerformance();
  const rankings = useStrategyRankings();
  const activeTrades = useActivePaperTrades(symbol);
  const recentTrades = useRecentTrades(symbol, 25);
  const scalpPerformance = useScalpPerformance();
  const logs = useLogs();

  const s = status.data;

  return (
    <div className="space-y-4">
      {/* System status bar */}
      <SystemStatus
        status={s}
        isLoading={status.isLoading}
        isError={status.isError}
      />

      {/* Price chart */}
      <PriceChart />

      {/* Hero row: Decision + Orchestra + Wallet */}
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <DecisionHero
            decision={s?.orchestrated_decision ?? null}
            latestSignal={s?.latest_signal ?? null}
          />
        </div>
        <div className="lg:col-span-3">
          <BotOrchestra decision={s?.orchestrated_decision ?? null} />
        </div>
        <div className="lg:col-span-3">
          <WalletPanel wallets={wallets.data} />
        </div>
      </div>

      {/* Middle row: Signals + Opportunities + Active Trades */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SignalsPanel signals={signals.data?.signals ?? []} />
        <OpportunitiesPanel opportunities={opportunities.data?.opportunities ?? []} />
        <ActiveTradesPanel
          activeTrades={activeTrades.data?.trades ?? []}
          recentTrades={recentTrades.data?.trades ?? []}
        />
      </div>

      {/* Arbitrage + Performance */}
      <div className="grid gap-4 md:grid-cols-2">
        <ArbitragePanel
          opportunities={arbOpportunities.data?.opportunities ?? []}
          arbType={arbType}
          status={arbStatus}
          page={arbPage}
          loading={arbOpportunities.isLoading}
          hasMore={(arbOpportunities.data?.pagination?.returned ?? 0) >= 12}
          onArbTypeChange={(value) => {
            setArbType(value);
            setArbPage(0);
          }}
          onStatusChange={(value) => {
            setArbStatus(value);
            setArbPage(0);
          }}
          onPageChange={setArbPage}
        />
        <PerformancePanel
          performance={performance.data}
          rankings={rankings.data?.strategies ?? []}
        />
      </div>

      {/* Perp basis + Logs */}
      <div className="grid gap-4 md:grid-cols-2">
        <PerpBasisPanel
          latest={perpBasisLatest.data?.snapshot ?? null}
          history={perpBasisHistory.data?.snapshots ?? []}
          symbol={symbol}
        />
        <ScalpPanel performance={scalpPerformance.data} />
      </div>

      {/* Logs */}
      <div className="grid gap-4">
        <LogsPanel logs={logs.data?.logs ?? []} />
      </div>
    </div>
  );
};

export default Index;
