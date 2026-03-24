import { useCallback, useEffect, useMemo, useState } from "react";

const DEFAULT_SYMBOL = "BTCUSDT";
const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];

const C = {
  bg: "#070b0c",
  panel: "#0f1517",
  panelAlt: "#111a1d",
  border: "#1f2a2e",
  text: "#d3e8e0",
  muted: "#7f9a93",
  bullish: "#34d399",
  bearish: "#f87171",
  neutral: "#fbbf24",
  accent: "#22d3ee",
  modelArb: "#a78bfa",
  sumArb: "#f59e0b",
  crossVenue: "#60a5fa",
};

const getApiBase = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) {
    const isLocalConfigured = configured.includes("localhost") || configured.includes("127.0.0.1");
    if (typeof window !== "undefined" && isLocalConfigured) {
      const host = window.location.hostname;
      if (host !== "localhost" && host !== "127.0.0.1") {
        return "/api/backend";
      }
    }
    return configured;
  }
  return "/api/backend";
};

const toPct = (v) => `${Math.round((Number(v) || 0) * 100)}%`;
const toBp = (v) => `${Math.round(Number(v) || 0)} bp`;
const toFundingPct = (v) => `${(Number(v) * 100).toFixed(3)}%`;
const shortTs = (iso) => {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  return d.toLocaleTimeString("en-US", { hour12: false });
};

async function fetchJson(path, opts = {}) {
  const base = getApiBase();
  const res = await fetch(`${base}${path}`, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 180)}`);
  }
  return res.json();
}

function usePolling(fetcher, intervalMs, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    try {
      const next = await fetcher();
      setData(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    let mounted = true;
    const safeRun = async () => {
      if (!mounted) return;
      await run();
    };

    safeRun();
    const id = setInterval(safeRun, intervalMs);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [run, intervalMs]);

  return { data, loading, error, refresh: run };
}

function Panel({ title, right, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panelHeader">
        <span className="panelTitle">{title}</span>
        {right ? <span className="panelRight">{right}</span> : null}
      </header>
      {children}
    </section>
  );
}

function ConfidenceBar({ value, tone = "neutral" }) {
  const pct = Math.max(0, Math.min(100, Math.round((Number(value) || 0) * 100)));
  return (
    <div className="meter">
      <div
        className={`meterFill ${tone}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function DecisionHero({ status }) {
  const decision = status?.orchestrated_decision || null;
  const latestSignal = status?.latest_signal || null;

  const dir = Number(decision?.direction || 0);
  const confidence = Number(decision?.confidence || 0);
  const bias = dir > 0 ? "LONG" : dir < 0 ? "SHORT" : "NEUTRAL";
  const tone = dir > 0 ? "bullish" : dir < 0 ? "bearish" : "neutral";
  const conviction = confidence >= 0.6 ? "HIGH" : confidence >= 0.4 ? "MEDIUM" : "LOW";
  const setup = confidence >= 0.55 ? "READY" : confidence >= 0.35 ? "DEVELOPING" : "POOR";

  return (
    <Panel title="Decision Hero" right={status?.symbol || DEFAULT_SYMBOL} className="heroPanel">
      <div className="biasRow">
        <div className={`biasChip ${tone}`}>{bias}</div>
        <div>
          <div className="heroSub">{decision?.reasoning || "Waiting for orchestrated decision..."}</div>
          <div className="heroSub muted">Updated {shortTs(decision?.timestamp || latestSignal?.timestamp)}</div>
        </div>
      </div>

      <div className="metricBlock">
        <div className="labelValue"><span>Confidence</span><span>{toPct(confidence)}</span></div>
        <ConfidenceBar value={confidence} tone={tone} />
      </div>

      <div className="chipGrid">
        <div className="miniChip"><span>Conviction</span><b>{conviction}</b></div>
        <div className="miniChip"><span>Setup</span><b>{setup}</b></div>
        <div className="miniChip"><span>Regime</span><b>{latestSignal?.regime || "--"}</b></div>
        <div className="miniChip"><span>Strength</span><b>{latestSignal?.signal_strength || "--"}</b></div>
      </div>
    </Panel>
  );
}

function BotOrchestra({ status }) {
  const bots = status?.orchestrated_decision?.bots || {};
  const entries = Object.entries(bots);
  const tally = entries.reduce(
    (acc, [, b]) => {
      const d = Number(b?.direction || 0);
      if (d > 0) acc.long += 1;
      else if (d < 0) acc.short += 1;
      else acc.flat += 1;
      return acc;
    },
    { long: 0, short: 0, flat: 0 }
  );

  return (
    <Panel
      title="Bot Orchestra"
      right={`${tally.long}L / ${tally.short}S / ${tally.flat}F`}
    >
      <div className="listGap">
        {entries.length === 0 ? <div className="empty">Waiting for bot votes...</div> : null}
        {entries.map(([name, bot]) => {
          const dir = Number(bot?.direction || 0);
          const tone = dir > 0 ? "bullish" : dir < 0 ? "bearish" : "neutral";
          return (
            <div key={name} className="rowCard compact">
              <span className="rowName">{name}</span>
              <span className={`badge ${tone}`}>{dir > 0 ? "LONG" : dir < 0 ? "SHORT" : "FLAT"}</span>
              <div className="rowMeter"><ConfidenceBar value={Number(bot?.confidence || 0)} tone={tone} /></div>
              <span className="rowPct">{toPct(bot?.confidence)}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function WalletPanel({ wallets, onReset, resetting, clearHistoryOnReset, setClearHistoryOnReset }) {
  const total = Number(wallets?.total_equity_usdc || 0);
  const pnl = total - 40;
  const strategies = wallets?.bots ? Object.entries(wallets.bots) : [];

  return (
    <Panel
      title="Wallet Panel"
      right={
        <button className="resetBtn" onClick={onReset} disabled={resetting}>
          {resetting ? "Resetting..." : "Reset"}
        </button>
      }
    >
      <div className="walletTotal">${total.toFixed(2)}</div>
      <div className={pnl >= 0 ? "pnlPlus" : "pnlMinus"}>{pnl >= 0 ? "+" : ""}{pnl.toFixed(2)} USDC</div>
      <div className="walletResetRow">
        <label className="checkLabel">
          <input
            type="checkbox"
            checked={clearHistoryOnReset}
            onChange={(e) => setClearHistoryOnReset(e.target.checked)}
          />
          <span>Clear history on reset</span>
        </label>
      </div>
      <div className="listGap">
        {strategies.map(([strategy, row]) => {
          const eq = Number(row?.equity_usdc || 0);
          const stratPnl = eq - 10;
          return (
            <div className="rowCard compact" key={strategy}>
              <span className="rowName">{strategy}</span>
              <span>${eq.toFixed(2)}</span>
              <span className={stratPnl >= 0 ? "pnlPlus" : "pnlMinus"}>{stratPnl >= 0 ? "+" : ""}{stratPnl.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function SignalsPanel({ signals }) {
  const order = ["1d", "4h", "1h", "15m", "5m"];
  const map = new Map();
  for (const s of signals || []) {
    const tf = s?.timeframe || "?";
    if (!map.has(tf)) map.set(tf, s);
  }
  const stack = order.map((tf) => map.get(tf)).filter(Boolean);

  return (
    <Panel title="Signals Panel" right={`${(signals || []).length} total`}>
      <div className="listGap">
        {stack.length === 0 ? <div className="empty">No signals yet</div> : null}
        {stack.map((s) => {
          const trend = String(s?.trend || "neutral");
          const tone = trend === "bullish" ? "bullish" : trend === "bearish" ? "bearish" : "neutral";
          return (
            <div key={s.timeframe} className="rowCard">
              <span className="rowName">{s.timeframe}</span>
              <span className={`badge ${tone}`}>{trend.toUpperCase()}</span>
              <div className="rowMeter"><ConfidenceBar value={Number(s?.confidence || 0)} tone={tone} /></div>
              <span className="rowPct">{toPct(s?.confidence)}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function OpportunitiesPanel({ opportunities }) {
  return (
    <Panel title="Opportunities Panel" right={`${(opportunities || []).length} active`}>
      <div className="listGap">
        {(opportunities || []).length === 0 ? (
          <div className="empty">No opportunities. System is currently selective.</div>
        ) : null}
        {(opportunities || []).slice(0, 12).map((opp) => (
          <div className="oppCard" key={opp.id || opp.opportunity_key}>
            <div className="oppTop">
              <span>{opp.symbol} {opp.timeframe ? `(${opp.timeframe})` : ""}</span>
              <div className="badgeRow">
                {opp.arb_type ? (
                  <span className={`badge ${opp.arb_type === "model_vs_market" ? "modelArb" : "sumArb"}`}>
                    {opp.arb_type}
                  </span>
                ) : null}
                <span className={`badge ${opp.side === "YES" ? "bullish" : "bearish"}`}>{opp.side}</span>
              </div>
            </div>
            <div className="oppName">{opp.market_name}</div>
            <div className="oppStats">
              <span>Edge <b>{(Number(opp.edge || 0) * 100).toFixed(2)}%</b></span>
              <span>Conf <b>{toPct(opp.confidence)}</b></span>
              <span>YES <b>{Number(opp.yes_price || 0).toFixed(2)}</b></span>
              {opp.p_fair != null ? <span>Fair <b>{toPct(opp.p_fair)}</b></span> : null}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function PerpBasisPanel({ latest, history, symbol }) {
  const snap = latest || null;
  const rows = history || [];

  return (
    <Panel title="Perp Basis / Funding" right={symbol || DEFAULT_SYMBOL}>
      {!snap ? <div className="empty">No cross-venue basis snapshots yet.</div> : null}
      {snap ? (
        <>
          <div className="perfGrid basisGrid">
            <div className="miniChip"><span>Bin Spot</span><b>{Number(snap.binance_spot_price || 0).toFixed(2)}</b></div>
            <div className="miniChip"><span>Bin Perp</span><b>{Number(snap.binance_perp_price || 0).toFixed(2)}</b></div>
            <div className="miniChip"><span>HL Perp</span><b>{Number(snap.hl_perp_price || 0).toFixed(2)}</b></div>
            <div className="miniChip"><span>Basis Diff</span><b>{toBp((Number(snap.basis_diff || 0) / Math.max(Number(snap.binance_perp_price || 1), Number(snap.hl_perp_price || 1), 1)) * 10000)}</b></div>
            <div className="miniChip"><span>Bin Funding</span><b>{toFundingPct(snap.binance_funding_rate || 0)}</b></div>
            <div className="miniChip"><span>HL Funding</span><b>{toFundingPct(snap.hl_funding_rate || 0)}</b></div>
            <div className="miniChip"><span>Funding Spread</span><b>{toFundingPct(snap.funding_spread || 0)}</b></div>
            <div className="miniChip"><span>HL OI</span><b>{Math.round(Number(snap.hl_open_interest || 0)).toLocaleString()}</b></div>
          </div>

          <div className="sectionLabel">Recent Basis Tape</div>
          <div className="listGap">
            {rows.slice(0, 8).map((row) => {
              const ref = Math.max(Number(row.binance_perp_price || 0), Number(row.hl_perp_price || 0), 1);
              const basisBp = (Number(row.basis_diff || 0) / ref) * 10000;
              return (
                <div key={row.id || row.timestamp} className="rowCard basisRow">
                  <span className="rowName">{shortTs(row.timestamp)}</span>
                  <span className={`badge ${Math.abs(basisBp) >= 5 ? "crossVenue" : "neutral"}`}>{toBp(basisBp)}</span>
                  <span>{toFundingPct(row.funding_spread || 0)}</span>
                  <span>{Number(row.binance_perp_price || 0).toFixed(2)} / {Number(row.hl_perp_price || 0).toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        </>
      ) : null}
    </Panel>
  );
}

function ArbOpportunitiesPanel({
  opportunities,
  arbType,
  status,
  onArbTypeChange,
  onStatusChange,
  page,
  onPrevPage,
  onNextPage,
  hasMore,
  loading,
}) {
  return (
    <Panel
      title="Arbitrage Opportunities"
      right={
        <div className="toolbarRow">
          <select className="miniSelect" value={arbType} onChange={(e) => onArbTypeChange(e.target.value)}>
            <option value="ALL">All types</option>
            <option value="model_vs_market">model_vs_market</option>
            <option value="yes_no_sum">yes_no_sum</option>
            <option value="cross_venue">cross_venue</option>
          </select>
          <select className="miniSelect" value={status} onChange={(e) => onStatusChange(e.target.value)}>
            <option value="ALL">All status</option>
            <option value="open">open</option>
            <option value="executed">executed</option>
          </select>
        </div>
      }
    >
      <div className="toolbarRow pagerRow">
        <span className="panelRight">Page {page + 1}{loading ? " · Loading" : ""}</span>
        <div className="pagerBtns">
          <button className="pagerBtn" onClick={onPrevPage} disabled={page === 0}>Prev</button>
          <button className="pagerBtn" onClick={onNextPage} disabled={!hasMore}>Next</button>
        </div>
      </div>
      <div className="listGap">
        {(opportunities || []).length === 0 ? <div className="empty">No arbitrage opportunities logged yet.</div> : null}
        {(opportunities || []).map((opp) => (
          <div className="oppCard" key={opp.id || `${opp.market_id}-${opp.timestamp}`}>
            <div className="oppTop">
              <span>{opp.symbol || "--"}</span>
              <div className="badgeRow">
                <span className={`badge ${opp.arb_type === "model_vs_market" ? "modelArb" : opp.arb_type === "cross_venue" ? "crossVenue" : "sumArb"}`}>
                  {opp.arb_type || "unknown"}
                </span>
                <span className="badge neutral">{opp.status || "open"}</span>
              </div>
            </div>
            <div className="oppName">{opp.market_name}</div>
            <div className="oppStats">
              <span>Fair <b>{toPct(opp.p_fair)}</b></span>
              <span>Mkt <b>{toPct(opp.p_mkt)}</b></span>
              <span>Edge <b>{toBp(opp.edge_bp)}</b></span>
              <span>At <b>{shortTs(opp.timestamp)}</b></span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function PerformancePanel({ perf, rankings }) {
  const cards = [
    { k: "Trades", v: String(perf?.trade_count ?? 0) },
    { k: "Win Rate", v: `${((Number(perf?.win_rate || 0)) * 100).toFixed(1)}%` },
    { k: "Total PnL", v: `$${Number(perf?.total_pnl || 0).toFixed(2)}` },
    { k: "Drawdown", v: `$${Number(perf?.max_drawdown || 0).toFixed(2)}` },
  ];

  return (
    <Panel title="Performance Panel" right={perf?.as_of ? shortTs(perf.as_of) : "--:--:--"}>
      <div className="perfGrid">
        {cards.map((c) => (
          <div key={c.k} className="miniChip"><span>{c.k}</span><b>{c.v}</b></div>
        ))}
      </div>

      <div className="sectionLabel">Strategy Score Rankings</div>
      <div className="listGap">
        {(rankings || []).slice(0, 8).map((r) => (
          <div key={r.strategy} className="rowCard">
            <span className="rowName">{r.strategy}</span>
            <div className="rowMeter"><ConfidenceBar value={Number(r.overall_score || 0)} tone="bullish" /></div>
            <span className="rowPct">{Math.round((Number(r.overall_score || 0)) * 100)}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function SystemStatus({ statusState }) {
  const { data, loading, error } = statusState;
  const live = !loading && !error;

  const uptime = Number(data?.uptime_seconds || 0);
  const hrs = Math.floor(uptime / 3600);
  const mins = Math.floor((uptime % 3600) / 60);

  return (
    <Panel
      title="System Status"
      right={data?.symbol || DEFAULT_SYMBOL}
      className="statusPanel"
    >
      <div className="statusRowWrap">
        <div className="statusInline">
          <span className={`dot ${live ? "bullish" : "bearish"}`} />
          <span>{live ? "Live" : loading ? "Connecting" : "Disconnected"}</span>
        </div>
        <div className="statusInline">Uptime {hrs}h {mins}m</div>
        <div className="statusInline">
          <span className={`dot ${data?.binance_thread_alive ? "bullish" : "bearish"}`} />Binance
        </div>
        <div className="statusInline">
          <span className={`dot ${data?.polymarket_thread_alive ? "bullish" : "bearish"}`} />Polymarket
        </div>
        <div className="statusInline">
          <span className={`dot ${data?.hyperliquid_thread_alive ? "bullish" : "bearish"}`} />Hyperliquid
        </div>
        <div className="statusInline">
          <span className={`dot ${data?.ta_scanner_thread_alive ? "bullish" : "bearish"}`} />TA Scanner
        </div>
      </div>
      {error ? <div className="errorText">{error}</div> : null}
    </Panel>
  );
}

function LogsPanel({ logs }) {
  return (
    <Panel title="Logs Panel" right={`${(logs || []).length} rows`}>
      <div className="logsWrap">
        {(logs || []).length === 0 ? <div className="empty">No logs available</div> : null}
        {(logs || []).slice(0, 120).map((log) => (
          <div key={log.id || `${log.timestamp}-${log.message}`} className="logRow">
            <span className="logTime">{shortTs(log.timestamp)}</span>
            <span className={`logLevel ${String(log.level || "").toUpperCase()}`}>{String(log.level || "INFO").toUpperCase()}</span>
            <span className="logMsg">{log.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Toast({ toast }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type || "info"}`}>
      <div className="toastTitle">{toast.type === "error" ? "Action Failed" : "Success"}</div>
      <div className="toastMsg">{toast.message}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [selectedSymbol, setSelectedSymbol] = useState(DEFAULT_SYMBOL);
  const [clearHistoryOnReset, setClearHistoryOnReset] = useState(false);
  const [toast, setToast] = useState(null);
  const [arbTypeFilter, setArbTypeFilter] = useState("ALL");
  const [arbStatusFilter, setArbStatusFilter] = useState("open");
  const [arbPage, setArbPage] = useState(0);

  useEffect(() => {
    setArbPage(0);
  }, [selectedSymbol, arbTypeFilter, arbStatusFilter]);

  const statusState = usePolling(
    () => fetchJson(`/status?symbol=${selectedSymbol}`),
    5000,
    [selectedSymbol]
  );

  const signalsState = usePolling(
    () => fetchJson(`/signals?symbol=${selectedSymbol}&limit=30`),
    15000,
    [selectedSymbol]
  );

  const oppState = usePolling(
    () => fetchJson(`/opportunities?symbol=${selectedSymbol}&limit=40&include_fair_value=true`),
    15000,
    [selectedSymbol]
  );

  const arbOppState = usePolling(
    () => {
      const params = new URLSearchParams({
        symbol: selectedSymbol,
        limit: "12",
        offset: String(arbPage * 12),
      });
      if (arbStatusFilter !== "ALL") params.set("status", arbStatusFilter);
      if (arbTypeFilter !== "ALL") params.set("arb_type", arbTypeFilter);
      return fetchJson(`/arbitrage/opportunities?${params.toString()}`);
    },
    30000,
    [selectedSymbol, arbTypeFilter, arbStatusFilter, arbPage]
  );

  const perpBasisLatestState = usePolling(
    () => fetchJson(`/perp-basis/latest?symbol=${selectedSymbol}`),
    15000,
    [selectedSymbol]
  );

  const perpBasisHistoryState = usePolling(
    () => fetchJson(`/perp-basis/history?symbol=${selectedSymbol}&limit=30`),
    30000,
    [selectedSymbol]
  );

  const walletsState = usePolling(
    () => fetchJson(`/paper-wallets`),
    5000,
    []
  );

  const perfState = usePolling(
    () => fetchJson(`/performance/summary`),
    30000,
    []
  );

  const rankingsState = usePolling(
    () => fetchJson(`/strategy/rankings`),
    30000,
    []
  );

  const logsState = usePolling(
    () => fetchJson(`/logs?limit=80`),
    30000,
    []
  );

  const [resetting, setResetting] = useState(false);

  const pushToast = useCallback((message, type = "success") => {
    setToast({ message, type });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(id);
  }, [toast]);

  const handleReset = useCallback(async () => {
    const ok = window.confirm(
      `Reset all paper wallets to default balances?\n\n${clearHistoryOnReset ? "Trade history will be cleared." : "Trade history will be kept."}`
    );
    if (!ok) return;

    setResetting(true);
    try {
      await fetchJson(
        `/paper-wallets/reset?confirm=true&clear_history=${clearHistoryOnReset ? "true" : "false"}`,
        { method: "POST" }
      );
      await Promise.all([
        walletsState.refresh(),
        statusState.refresh(),
        perfState.refresh(),
        rankingsState.refresh(),
      ]);
      pushToast(
        clearHistoryOnReset
          ? "Wallets reset and history cleared"
          : "Wallets reset successfully",
        "success"
      );
    } catch (err) {
      pushToast(`Reset failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setResetting(false);
    }
  }, [walletsState, statusState, perfState, rankingsState, clearHistoryOnReset, pushToast]);

  const signals = useMemo(() => signalsState.data?.signals || [], [signalsState.data]);
  const opportunities = useMemo(() => oppState.data?.opportunities || [], [oppState.data]);
  const arbOpportunities = useMemo(() => arbOppState.data?.opportunities || [], [arbOppState.data]);
  const arbPagination = useMemo(() => arbOppState.data?.pagination || {}, [arbOppState.data]);
  const perpBasisLatest = useMemo(() => perpBasisLatestState.data?.snapshot || null, [perpBasisLatestState.data]);
  const perpBasisHistory = useMemo(() => perpBasisHistoryState.data?.snapshots || [], [perpBasisHistoryState.data]);
  const logs = useMemo(() => logsState.data?.logs || [], [logsState.data]);

  return (
    <main className="page">
      <div className="bgMesh" />
      <div className="container">
        <div className="topBar">
          <div className="symbolSwitcher" role="tablist" aria-label="Symbol switcher">
            {SYMBOLS.map((symbol) => (
              <button
                key={symbol}
                type="button"
                className={`symbolBtn ${selectedSymbol === symbol ? "active" : ""}`}
                onClick={() => setSelectedSymbol(symbol)}
              >
                {symbol.replace("USDT", "")}
              </button>
            ))}
          </div>
          <div className="topMeta">Polling: 5s / 15s / 30s</div>
        </div>

        <SystemStatus statusState={statusState} />

        <section className="heroGrid">
          <DecisionHero status={statusState.data} />
          <BotOrchestra status={statusState.data} />
          <WalletPanel
            wallets={walletsState.data}
            onReset={handleReset}
            resetting={resetting}
            clearHistoryOnReset={clearHistoryOnReset}
            setClearHistoryOnReset={setClearHistoryOnReset}
          />
        </section>

        <section className="twoGrid">
          <SignalsPanel signals={signals} />
          <OpportunitiesPanel opportunities={opportunities} />
        </section>

        <section className="twoGrid">
          <ArbOpportunitiesPanel
            opportunities={arbOpportunities}
            arbType={arbTypeFilter}
            status={arbStatusFilter}
            onArbTypeChange={setArbTypeFilter}
            onStatusChange={setArbStatusFilter}
            page={arbPage}
            onPrevPage={() => setArbPage((p) => Math.max(0, p - 1))}
            onNextPage={() => setArbPage((p) => p + 1)}
            hasMore={Number(arbPagination.returned || 0) >= 12}
            loading={arbOppState.loading}
          />
          <PerformancePanel perf={perfState.data} rankings={rankingsState.data?.strategies || []} />
        </section>

        <section className="twoGrid">
          <PerpBasisPanel latest={perpBasisLatest} history={perpBasisHistory} symbol={selectedSymbol} />
          <LogsPanel logs={logs} />
        </section>
      </div>

      <Toast toast={toast} />

      <style jsx>{`
        .page {
          min-height: 100vh;
          background: radial-gradient(circle at 20% -20%, #16332d 0%, #070b0c 55%), ${C.bg};
          color: ${C.text};
          padding: 12px;
          position: relative;
          overflow-x: hidden;
        }
        .bgMesh {
          position: fixed;
          inset: 0;
          pointer-events: none;
          background-image:
            linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
          background-size: 28px 28px;
          opacity: 0.4;
        }
        .container {
          max-width: 1360px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 12px;
          position: relative;
          z-index: 1;
        }
        .topBar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          border: 1px solid ${C.border};
          border-radius: 10px;
          padding: 8px 10px;
          background: rgba(0,0,0,0.16);
        }
        .topMeta {
          font-size: 11px;
          color: ${C.muted};
          letter-spacing: 0.04em;
        }
        .symbolSwitcher {
          display: inline-flex;
          gap: 6px;
          background: rgba(0,0,0,0.24);
          border: 1px solid ${C.border};
          border-radius: 8px;
          padding: 4px;
        }
        .symbolBtn {
          border: 1px solid transparent;
          border-radius: 6px;
          color: ${C.muted};
          background: transparent;
          padding: 5px 10px;
          font-size: 11px;
          letter-spacing: 0.04em;
          cursor: pointer;
        }
        .symbolBtn:hover {
          color: ${C.text};
        }
        .symbolBtn.active {
          color: ${C.text};
          border-color: rgba(34,211,238,0.45);
          background: rgba(34,211,238,0.1);
          box-shadow: 0 0 14px rgba(34,211,238,0.12);
        }
        .panel {
          border: 1px solid ${C.border};
          border-radius: 10px;
          background: linear-gradient(180deg, ${C.panelAlt}, ${C.panel});
          padding: 12px;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 8px 30px rgba(0,0,0,0.25);
        }
        .panelHeader {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }
        .panelTitle {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.14em;
          color: ${C.muted};
          font-weight: 700;
        }
        .panelRight {
          font-size: 11px;
          color: ${C.muted};
        }
        .statusPanel {
          padding-bottom: 10px;
        }
        .statusRowWrap {
          display: flex;
          flex-wrap: wrap;
          gap: 14px;
          font-size: 12px;
          color: ${C.muted};
        }
        .statusInline {
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .dot {
          width: 8px;
          height: 8px;
          border-radius: 999px;
          display: inline-block;
          box-shadow: 0 0 12px currentColor;
        }
        .dot.bullish { color: ${C.bullish}; background: ${C.bullish}; }
        .dot.bearish { color: ${C.bearish}; background: ${C.bearish}; }

        .heroGrid {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr;
          gap: 12px;
        }
        .twoGrid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .biasRow {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 12px;
        }
        .biasChip {
          min-width: 84px;
          text-align: center;
          font-weight: 800;
          font-size: 18px;
          letter-spacing: 0.06em;
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid ${C.border};
        }
        .biasChip.bullish { color: ${C.bullish}; background: rgba(52,211,153,0.08); }
        .biasChip.bearish { color: ${C.bearish}; background: rgba(248,113,113,0.08); }
        .biasChip.neutral { color: ${C.neutral}; background: rgba(251,191,36,0.08); }

        .heroSub { font-size: 12px; }
        .heroSub.muted { color: ${C.muted}; margin-top: 4px; }

        .metricBlock { margin-bottom: 12px; }
        .labelValue {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: ${C.muted};
          margin-bottom: 6px;
        }
        .meter {
          height: 8px;
          border-radius: 999px;
          background: #1a2327;
          overflow: hidden;
          border: 1px solid #233138;
        }
        .meterFill {
          height: 100%;
          transition: width 0.45s ease;
        }
        .meterFill.bullish { background: linear-gradient(90deg, #1b9d73, ${C.bullish}); }
        .meterFill.bearish { background: linear-gradient(90deg, #c34e4e, ${C.bearish}); }
        .meterFill.neutral { background: linear-gradient(90deg, #8f7430, ${C.neutral}); }

        .chipGrid {
          display: grid;
          gap: 8px;
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .miniChip {
          border: 1px solid ${C.border};
          border-radius: 8px;
          padding: 8px;
          background: rgba(0,0,0,0.16);
        }
        .miniChip span {
          font-size: 10px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: ${C.muted};
          display: block;
          margin-bottom: 4px;
        }
        .miniChip b {
          font-size: 13px;
          color: ${C.text};
        }

        .listGap {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .rowCard {
          border: 1px solid ${C.border};
          background: rgba(0,0,0,0.2);
          border-radius: 8px;
          padding: 8px;
          display: grid;
          grid-template-columns: 72px 72px 1fr 48px;
          align-items: center;
          gap: 8px;
          font-size: 12px;
        }
        .rowCard.compact {
          grid-template-columns: 1fr auto auto;
        }
        .rowName {
          color: ${C.muted};
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .rowMeter { min-width: 80px; }
        .rowPct {
          text-align: right;
          color: ${C.muted};
          font-size: 11px;
        }

        .badge {
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 5px;
          border: 1px solid transparent;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          width: max-content;
          font-weight: 700;
        }
        .badge.bullish { color: ${C.bullish}; background: rgba(52,211,153,0.1); border-color: rgba(52,211,153,0.28); }
        .badge.bearish { color: ${C.bearish}; background: rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.28); }
        .badge.neutral { color: ${C.neutral}; background: rgba(251,191,36,0.1); border-color: rgba(251,191,36,0.28); }
        .badge.modelArb { color: ${C.modelArb}; background: rgba(167,139,250,0.12); border-color: rgba(167,139,250,0.36); }
        .badge.sumArb { color: ${C.sumArb}; background: rgba(245,158,11,0.12); border-color: rgba(245,158,11,0.36); }
        .badge.crossVenue { color: ${C.crossVenue}; background: rgba(96,165,250,0.12); border-color: rgba(96,165,250,0.36); }

        .toolbarRow {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin-bottom: 8px;
          flex-wrap: wrap;
        }
        .miniSelect {
          background: rgba(0,0,0,0.24);
          color: ${C.text};
          border: 1px solid ${C.border};
          border-radius: 6px;
          padding: 4px 8px;
          font-size: 11px;
        }
        .pagerRow {
          margin-top: -2px;
        }
        .pagerBtns {
          display: inline-flex;
          gap: 6px;
        }
        .pagerBtn {
          background: transparent;
          color: ${C.accent};
          border: 1px solid ${C.border};
          border-radius: 6px;
          padding: 4px 8px;
          cursor: pointer;
          font-size: 11px;
        }
        .pagerBtn:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }

        .walletTotal {
          font-size: 30px;
          font-weight: 800;
          margin: 2px 0;
        }
        .pnlPlus { color: ${C.bullish}; font-size: 12px; }
        .pnlMinus { color: ${C.bearish}; font-size: 12px; }

        .resetBtn {
          background: transparent;
          color: ${C.accent};
          border: 1px solid ${C.border};
          border-radius: 6px;
          padding: 4px 8px;
          cursor: pointer;
          font-size: 11px;
        }
        .resetBtn:disabled { opacity: 0.6; cursor: not-allowed; }
        .walletResetRow {
          margin: 8px 0 10px;
        }
        .checkLabel {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          font-size: 11px;
          color: ${C.muted};
          user-select: none;
        }
        .checkLabel input {
          accent-color: ${C.accent};
          width: 13px;
          height: 13px;
        }

        .oppCard {
          border: 1px solid ${C.border};
          border-radius: 8px;
          background: rgba(0,0,0,0.2);
          padding: 8px;
        }
        .oppTop {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
          font-size: 12px;
        }
        .badgeRow {
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .oppName {
          font-size: 11px;
          color: ${C.muted};
          margin-bottom: 6px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .oppStats {
          display: flex;
          gap: 12px;
          font-size: 11px;
          color: ${C.muted};
        }
        .oppStats b { color: ${C.text}; }

        .perfGrid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
          margin-bottom: 12px;
        }
        .basisGrid {
          margin-bottom: 12px;
        }
        .basisRow {
          grid-template-columns: 70px 74px 70px 1fr;
        }
        .sectionLabel {
          font-size: 10px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: ${C.muted};
          margin-bottom: 8px;
        }

        .logsWrap {
          max-height: 340px;
          overflow-y: auto;
          border: 1px solid ${C.border};
          border-radius: 8px;
          background: rgba(0,0,0,0.22);
          padding: 8px;
        }
        .logRow {
          display: grid;
          grid-template-columns: 72px 54px 1fr;
          gap: 8px;
          font-size: 11px;
          padding: 3px 0;
        }
        .logTime { color: ${C.muted}; }
        .logLevel { font-weight: 700; }
        .logLevel.INFO { color: ${C.bullish}; }
        .logLevel.WARNING { color: ${C.neutral}; }
        .logLevel.ERROR { color: ${C.bearish}; }
        .logMsg { color: ${C.text}; opacity: 0.92; }

        .empty {
          border: 1px dashed ${C.border};
          border-radius: 8px;
          padding: 14px;
          text-align: center;
          color: ${C.muted};
          font-size: 12px;
        }

        .errorText {
          color: ${C.bearish};
          margin-top: 8px;
          font-size: 12px;
        }
        .toast {
          position: fixed;
          right: 14px;
          bottom: 14px;
          min-width: 260px;
          max-width: 420px;
          border-radius: 10px;
          border: 1px solid ${C.border};
          background: linear-gradient(180deg, ${C.panelAlt}, ${C.panel});
          padding: 10px 12px;
          z-index: 20;
          box-shadow: 0 10px 30px rgba(0,0,0,0.35);
        }
        .toast.success {
          border-color: rgba(52,211,153,0.35);
        }
        .toast.error {
          border-color: rgba(248,113,113,0.42);
        }
        .toastTitle {
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: ${C.muted};
          margin-bottom: 4px;
          font-weight: 700;
        }
        .toastMsg {
          font-size: 12px;
          color: ${C.text};
          line-height: 1.4;
        }

        @media (max-width: 1180px) {
          .heroGrid {
            grid-template-columns: 1fr;
          }
          .twoGrid {
            grid-template-columns: 1fr;
          }
        }
        @media (max-width: 720px) {
          .topBar {
            flex-direction: column;
            align-items: flex-start;
          }
          .panel {
            padding: 10px;
          }
          .rowCard {
            grid-template-columns: 56px 66px 1fr 40px;
            gap: 6px;
            font-size: 11px;
          }
          .perfGrid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .basisRow {
            grid-template-columns: 64px 72px 64px 1fr;
          }
          .logRow {
            grid-template-columns: 58px 46px 1fr;
            font-size: 10px;
          }
        }
      `}</style>
    </main>
  );
}
