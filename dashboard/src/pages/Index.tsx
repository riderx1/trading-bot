import { useState } from "react";
import { useStatus, useSignalsForSymbol, useOpportunities, useArbitrageOpportunities, usePerpBasisLatest, usePerpBasisHistory, useWallets, usePerformance, useStrategyRankings, useLogs, useActivePaperTrades, useRecentTrades, useScalpPerformance } from "@/hooks/use-trading-data";
import { DecisionStickyBar } from "@/components/dashboard/DecisionStickyBar";
import { DecisionHero } from "@/components/dashboard/DecisionHero";
import { MarketStatePanel } from "@/components/dashboard/MarketStatePanel";
import { BotOrchestra } from "@/components/dashboard/BotOrchestra";
import { WalletPanel } from "@/components/dashboard/WalletPanel";
import { ActiveTradesPanel } from "@/components/dashboard/ActiveTradesPanel";
import { SignalsPanel } from "@/components/dashboard/SignalsPanel";
import { OpportunitiesPanel } from "@/components/dashboard/OpportunitiesPanel";
import { ArbitragePanel } from "@/components/dashboard/ArbitragePanel";
import { ArbitrageDecisionPanel } from "@/components/dashboard/ArbitrageDecisionPanel";
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
    <div className="space-y-5">
      <SystemStatus
        status={s}
        isLoading={status.isLoading}
        isError={status.isError}
      />

      <DecisionStickyBar
        symbol={symbol}
        decision={s?.directional_decision ?? null}
        arbitrageDecision={s?.arbitrage_decision ?? null}
      />

      <PriceChart />

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <DecisionHero
            decision={s?.directional_decision ?? null}
            latestSignal={s?.latest_signal ?? null}
            explainability={s?.decision_explainability ?? null}
          />
        </div>
        <div className="lg:col-span-5">
          <ArbitrageDecisionPanel decision={s?.arbitrage_decision ?? null} />
        </div>
      </div>

      <MarketStatePanel
        symbol={symbol}
        latestSignal={s?.latest_signal ?? null}
        decision={s?.directional_decision ?? null}
        microData={s?.latest_micro_data ?? null}
        perpBasis={perpBasisLatest.data?.snapshot ?? null}
      />

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <OpportunitiesPanel opportunities={opportunities.data?.opportunities ?? []} />
        <div className="space-y-4">
          <BotOrchestra decision={s?.directional_decision ?? null} rankings={rankings.data?.strategies ?? []} />
          <WalletPanel wallets={wallets.data} />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <PerformancePanel
          performance={performance.data}
          rankings={rankings.data?.strategies ?? []}
          recentTrades={recentTrades.data?.trades ?? []}
        />
        <ActiveTradesPanel
          activeTrades={activeTrades.data?.trades ?? []}
          recentTrades={recentTrades.data?.trades ?? []}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <SignalsPanel signals={signals.data?.signals ?? []} />
        <div className="space-y-4">
          <ScalpPanel
            performance={scalpPerformance.data}
            latestSignal={s?.latest_scalping_signal ?? null}
            microData={s?.latest_micro_data ?? null}
          />
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
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <PerpBasisPanel
          latest={perpBasisLatest.data?.snapshot ?? null}
          history={perpBasisHistory.data?.snapshots ?? []}
          symbol={symbol}
        />
        <LogsPanel logs={logs.data?.logs ?? []} />
      </div>
    </div>
  );
};

export default Index;
