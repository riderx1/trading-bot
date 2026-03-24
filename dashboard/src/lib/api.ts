// Trading Bot API Client

const getBaseUrl = () => {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured && configured.trim()) {
    return configured.trim().replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol || "http:";
    const host = window.location.hostname || "127.0.0.1";
    return `${protocol}//${host}:8000`;
  }

  return "http://127.0.0.1:8000";
};

const BASE_URL = getBaseUrl();

// ─── Types ───────────────────────────────────────────────────

export interface Signal {
  id: number;
  sequence_id: number | null;
  source: string;
  strategy: string | null;
  timeframe: string | null;
  trend: "bullish" | "bearish" | "neutral";
  confidence: number;
  signal_strength: "weak" | "medium" | "strong" | null;
  reasoning: string | null;
  regime: string | null;
  move_pct: number | null;
  value: number | null;
  symbol: string | null;
  timestamp: string;
}

export interface BotWallet {
  equity_usdc: number;
  locked_usdc: number;
  available_usdc: number;
}

export interface WalletSnapshot {
  total_equity_usdc: number;
  total_locked_usdc: number;
  total_available_usdc: number;
  bots: Record<string, BotWallet>;
}

export interface VenueWalletRow {
  balance: number;
  pnl: number;
}

export interface VenueWalletSnapshot {
  polymarket?: Record<string, VenueWalletRow>;
  hyperliquid: Record<string, VenueWalletRow>;
  total: number;
}

export interface BotDecision {
  bot?: string;
  strategy: string;
  type?: "directional" | "arbitrage";
  time_horizon?: "scalp" | "short" | "medium" | "long";
  direction: number;
  confidence: number;
  reasoning: string;
  signal?: string;
  weight?: number;
  edge?: number;
}

export interface OrchestratedDecision {
  symbol: string;
  direction: number;
  trend: "bullish" | "bearish" | "neutral";
  confidence: number;
  reasoning: string;
  timestamp?: string;
  bots: Record<string, BotDecision>;
}

export interface DirectionalDecision {
  bias: "LONG" | "SHORT" | "NO TRADE";
  confidence: number;
  conviction: "HIGH" | "MEDIUM" | "LOW";
  setup_quality: "READY" | "DEVELOPING" | "POOR";
  entry_timing: "EARLY" | "CONFIRMED" | "LATE";
  top_strategy: string;
  top_bot: string;
  time_horizon: "scalp" | "short" | "medium" | "long";
  weighted_bias: number;
  reasoning: string;
  bots: BotDecision[];
}

export interface ArbitrageDecision {
  active: boolean;
  type: string;
  edge: number;
  market: string;
  confidence: number;
  execution_note: string;
  bots: BotDecision[];
}

export interface MicroData {
  symbol: string;
  time_horizon: string;
  move_pct_short: number;
  volume_spike: boolean;
  volume_ratio: number;
  spread_bps: number;
  source_interval: string;
}

export interface StatusResponse {
  status: string;
  mode: string;
  execution_mode?: string;
  paper_trading_only?: boolean;
  paper_trading: boolean;
  paper_wallets: WalletSnapshot;
  paper_wallets_by_venue?: VenueWalletSnapshot;
  consensus_blocked_count?: number;
  symbol: string;
  supported_symbols: string[];
  signal_intervals: string[];
  latest_signal: Signal | null;
  latest_perp_context?: Record<string, unknown> | null;
  latest_micro_data?: MicroData | null;
  orchestrated_decision: OrchestratedDecision | null;
  directional_decision?: DirectionalDecision | null;
  arbitrage_decision?: ArbitrageDecision | null;
  decision_explainability?: {
    why_long: string[];
    why_not_stronger: string[];
  } | null;
  latest_scalping_signal?: BotDecision | null;
  last_signal_sequence_id: number | null;
  uptime_seconds: number;
  binance_thread_alive: boolean;
  polymarket_thread_alive: boolean;
  hyperliquid_thread_alive?: boolean;
  ta_scanner_thread_alive: boolean;
  ta_scanner_last_error: string | null;
}

export interface Opportunity {
  id: number;
  opportunity_key: string;
  market_id: string;
  market_name: string;
  symbol: string;
  strategy: string;
  timeframe: string;
  trend: "bullish" | "bearish" | "neutral";
  confidence: number;
  signal_strength: string;
  side: "YES" | "NO";
  yes_price: number;
  no_price: number;
  edge: number;
  arb_type?: string | null;
  p_fair?: number | null;
  p_mkt?: number | null;
  edge_bp?: number | null;
  reasoning: string;
  timestamp: string;
}

export interface ArbitrageOpportunity {
  id: number;
  market_id: string;
  market_name: string;
  symbol: string | null;
  arb_type: string;
  p_fair: number | null;
  p_mkt: number | null;
  edge_bp: number | null;
  strategy: string | null;
  status: string;
  why: string | null;
  timestamp: string;
}

export interface PerpBasisSnapshot {
  id: number;
  symbol: string;
  binance_spot_price: number | null;
  binance_perp_price: number | null;
  binance_funding_rate: number | null;
  binance_basis_pct: number | null;
  hl_perp_price: number | null;
  hl_funding_rate: number | null;
  hl_open_interest: number | null;
  basis_diff: number | null;
  funding_spread: number | null;
  timestamp: string;
}

export interface PerformanceSummary {
  trade_count: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
  max_drawdown: number;
  sharpe_ratio: number;
  edge_per_setup: Record<string, number>;
  as_of: string;
  venue?: string;
}

export interface StrategyRanking {
  strategy: string;
  venue?: string;
  trade_count: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  overall_score: number;
  sample_count?: number;
}

export interface ScalpAggregate {
  trade_count: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
  max_drawdown: number;
  sharpe_ratio: number;
  edge_per_setup: Record<string, number>;
}

export interface ScalpPerformanceResponse {
  overall: ScalpAggregate;
  by_venue: Record<string, ScalpAggregate>;
  by_asset: Record<string, ScalpAggregate>;
  as_of: string;
}

export interface CalibrationDiagnosticsResponse {
  confidence_distribution: Record<string, number>;
  edge_distribution: Record<string, number>;
  signal_density: {
    window_minutes: number;
    total_signals: number;
    by_strategy: Record<string, number>;
  };
}

export interface SimulatedTrade {
  id: number;
  symbol: string;
  strategy: string;
  entry_price: number;
  exit_price: number;
  direction: number;
  pnl: number;
  duration_seconds: number;
  timeframe?: string | null;
  signal_strength?: string | null;
  regime?: string | null;
  entry_timestamp?: string | null;
  exit_timestamp?: string | null;
  venue?: string | null;
  status?: string | null;
  timestamp: string;
}

export interface ActivePaperTrade {
  trade_type: "single" | "pair";
  venue?: string;
  symbol: string;
  strategy: string;
  direction: number;
  side: "BUY" | "SELL" | "LONG" | "SHORT" | "YES" | "NO";
  entry_price: number;
  current_price: number | null;
  quantity: number | null;
  stake_usdc: number;
  unrealized_pnl: number | null;
  opened_at: string;
  duration_seconds: number;
  signal_strength?: string | null;
  regime?: string | null;
  timeframe?: string | null;
  entry_spread?: number | null;
  current_spread?: number | null;
  entry_binance_price?: number | null;
  entry_hl_price?: number | null;
  current_binance_price?: number | null;
  current_hl_price?: number | null;
}

export interface LogEntry {
  id: number;
  timestamp: string;
  level: "INFO" | "WARNING" | "ERROR" | "DEBUG";
  module: string;
  message: string;
  context: unknown;
}

export interface BacktestRunRequest {
  symbol: string;
  venue?: "hyperliquid";
  market_type?: "updown" | "all";
  timeframe: "5m" | "15m" | "1h" | "4h" | "1d";
  start_ts: string;
  end_ts: string;
  initial_capital?: number;
  lookback_bars?: number;
  enable_signal_strategy?: boolean;
  enable_funding_arb?: boolean;
  enable_basis_arb?: boolean;
  slippage_bps?: number;
  fee_bps?: number;
}

export interface BacktestRun {
  run_id: string;
  status: "queued" | "running" | "cancelling" | "cancelled" | "completed" | "failed";
  symbol: string;
  venue: string;
  market_type: string;
  start_ts: string;
  end_ts: string;
  timeframe: string;
  strategy_scope: string;
  params: Record<string, unknown>;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface BacktestMetrics {
  total_return: number;
  annualized_return: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  trades_count: number;
  avg_holding_period_seconds: number;
  exposure_ratio: number;
  gross_profit: number;
  gross_loss: number;
  fees_paid: number;
  slippage_paid: number;
}

export interface BacktestReport {
  run: BacktestRun;
  metrics: BacktestMetrics | null;
  equity_curve: Array<{ timestamp: string; value: number }>;
  drawdown_curve: Array<{ timestamp: string; drawdown_pct: number }>;
  trades: Array<Record<string, unknown>>;
  events: Array<{ ts: string; level: string; message: string; payload: Record<string, unknown> }>;
}

// ─── API Functions ───────────────────────────────────────────

async function fetchJson<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, BASE_URL);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const url = new URL(path, BASE_URL);
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function postNoBodyJson<T>(path: string): Promise<T> {
  const url = new URL(path, BASE_URL);
  const res = await fetch(url.toString(), {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function fetchBlob(path: string, params?: Record<string, string>): Promise<Blob> {
  const url = new URL(path, BASE_URL);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.blob();
}

function normalizeDecision(raw: any): OrchestratedDecision | null {
  if (!raw || typeof raw !== "object") return null;
  const finalBias = Number(raw.final_bias ?? 0);
  const confidence = Number(raw.confidence ?? raw.final_confidence ?? 0);
  const direction = finalBias > 0.2 ? 1 : finalBias < -0.2 ? -1 : 0;
  const trend = direction > 0 ? "bullish" : direction < 0 ? "bearish" : "neutral";

  const contributions = Array.isArray(raw.contributions)
    ? raw.contributions
    : Array.isArray(raw.contributing_bots)
    ? raw.contributing_bots
    : [];

  const bots = Object.fromEntries(
    contributions.map((item: any) => [
      String(item.bot || item.strategy || "UnknownBot"),
      {
        bot: String(item.bot || item.strategy || "UnknownBot"),
        strategy: String(item.strategy || "unknown"),
        direction: Number(item.direction || 0),
        confidence: Number(item.confidence || 0),
        reasoning: String(item.reasoning || ""),
        signal: String(item.signal || "FLAT"),
        weight: Number(item.weight || 0),
      },
    ])
  );

  return {
    symbol: String(raw.symbol || ""),
    direction,
    trend,
    confidence,
    reasoning: String(raw.reasoning || ""),
    timestamp: raw.timestamp ? String(raw.timestamp) : undefined,
    bots,
  };
}

function normalizeBotDecision(raw: any): BotDecision {
  return {
    bot: String(raw?.bot || raw?.strategy || "UnknownBot"),
    strategy: String(raw?.strategy || "unknown"),
    type: raw?.type === "arbitrage" ? "arbitrage" : "directional",
    time_horizon: String(raw?.time_horizon || "short") as BotDecision["time_horizon"],
    direction: Number(raw?.direction || 0),
    confidence: Number(raw?.confidence || 0),
    reasoning: String(raw?.reasoning || ""),
    signal: String(raw?.signal || "FLAT"),
    weight: Number(raw?.weight || 0),
    edge: Number(raw?.edge || 0),
  };
}

function normalizeDirectionalDecision(raw: any, fallback: OrchestratedDecision | null): DirectionalDecision | null {
  if (raw && typeof raw === "object") {
    return {
      bias: raw.bias === "LONG" || raw.bias === "SHORT" ? raw.bias : "NO TRADE",
      confidence: Number(raw.confidence || 0),
      conviction: raw.conviction === "HIGH" || raw.conviction === "MEDIUM" ? raw.conviction : "LOW",
      setup_quality: raw.setup_quality === "READY" || raw.setup_quality === "DEVELOPING" ? raw.setup_quality : "POOR",
      entry_timing: raw.entry_timing === "EARLY" || raw.entry_timing === "LATE" ? raw.entry_timing : "CONFIRMED",
      top_strategy: String(raw.top_strategy || "ta_confluence"),
      top_bot: String(raw.top_bot || ""),
      time_horizon: String(raw.time_horizon || "short") as DirectionalDecision["time_horizon"],
      weighted_bias: Number(raw.weighted_bias || 0),
      reasoning: String(raw.reasoning || ""),
      bots: Array.isArray(raw.bots) ? raw.bots.map(normalizeBotDecision) : [],
    };
  }

  if (!fallback) return null;
  const botRows = Object.values(fallback.bots);
  const bias = fallback.direction > 0 ? "LONG" : fallback.direction < 0 ? "SHORT" : "NO TRADE";
  const confidence = Number(fallback.confidence || 0);
  return {
    bias,
    confidence,
    conviction: confidence >= 0.65 ? "HIGH" : confidence >= 0.45 ? "MEDIUM" : "LOW",
    setup_quality: confidence >= 0.6 ? "READY" : confidence >= 0.35 ? "DEVELOPING" : "POOR",
    entry_timing: confidence < 0.35 ? "EARLY" : Math.abs(fallback.direction) > 0 ? "CONFIRMED" : "LATE",
    top_strategy: botRows[0]?.strategy || "ta_confluence",
    top_bot: botRows[0]?.bot || "",
    time_horizon: (botRows[0]?.time_horizon as DirectionalDecision["time_horizon"]) || "short",
    weighted_bias: Number(fallback.direction || 0),
    reasoning: fallback.reasoning,
    bots: botRows,
  };
}

function normalizeArbitrageDecision(raw: any): ArbitrageDecision | null {
  if (!raw || typeof raw !== "object") return null;
  return {
    active: Boolean(raw.active),
    type: String(raw.type || "none"),
    edge: Number(raw.edge || 0),
    market: String(raw.market || ""),
    confidence: Number(raw.confidence || 0),
    execution_note: String(raw.execution_note || "No active arbitrage edge"),
    bots: Array.isArray(raw.bots) ? raw.bots.map(normalizeBotDecision) : [],
  };
}

function normalizeRankings(raw: any): { strategies: StrategyRanking[] } {
  const rows = Array.isArray(raw?.strategies)
    ? raw.strategies
    : Array.isArray(raw)
    ? raw
    : [];
  return {
    strategies: rows.map((row: any) => ({
      strategy: String(row.strategy || "unknown"),
      venue: String(row.venue || ""),
      trade_count: Number(row.trade_count ?? row.trades ?? 0),
      win_rate: Number(row.win_rate ?? 0),
      avg_pnl: Number(row.avg_pnl ?? 0),
      total_pnl: Number(row.total_pnl ?? row.last_24h_pnl ?? 0),
      sharpe_ratio: Number(row.sharpe_ratio ?? 0),
      max_drawdown: Number(row.max_drawdown ?? 0),
      overall_score: Number(row.overall_score ?? row.score ?? 0),
      sample_count: Number(row.sample_count ?? row.trades ?? 0),
    })),
  };
}

export const api = {
  getStatus: async (symbol?: string) => {
    const raw = await fetchJson<any>("/status", symbol ? { symbol } : undefined);
    const normalizedLegacy = normalizeDecision(raw.orchestrated_decision);
    return {
      ...raw,
      latest_signal: raw.latest_signal ?? null,
      latest_micro_data: raw.latest_micro_data ?? null,
      orchestrated_decision: normalizedLegacy,
      directional_decision: normalizeDirectionalDecision(raw.directional_decision, normalizedLegacy),
      arbitrage_decision: normalizeArbitrageDecision(raw.arbitrage_decision),
      decision_explainability: raw.decision_explainability ?? null,
      latest_scalping_signal: raw.latest_scalping_signal ? normalizeBotDecision(raw.latest_scalping_signal) : null,
    } as StatusResponse;
  },

  getHistorySignals: (params?: Record<string, string>) =>
    fetchJson<{ signals: Signal[] }>("/history/signals", params),

  getHistoryOpportunities: (params?: Record<string, string>) =>
    fetchJson<{ opportunities: Opportunity[] }>("/history/opportunities", params),

  getHistoryTrades: (params?: Record<string, string>) =>
    fetchJson<{ trades: SimulatedTrade[] }>("/history/trades", params),

  getSignals: (limit = 20, symbol?: string) =>
    fetchJson<{ signals: Signal[] }>("/signals", { limit: String(limit), ...(symbol ? { symbol } : {}) }),

  getOpportunities: (limit = 10, symbol?: string) =>
    fetchJson<{ opportunities: Opportunity[] }>("/opportunities", {
      limit: String(limit),
      include_fair_value: "true",
      ...(symbol ? { symbol } : {}),
    }),

  getArbitrageOpportunities: (
    limit = 12,
    symbol?: string,
    arbType?: string,
    status?: string,
    offset = 0,
  ) =>
    fetchJson<{ opportunities: ArbitrageOpportunity[]; pagination: { limit: number; offset: number; returned: number } }>(
      "/arbitrage/opportunities",
      {
        limit: String(limit),
        offset: String(offset),
        ...(symbol ? { symbol } : {}),
        ...(arbType && arbType !== "ALL" ? { arb_type: arbType } : {}),
        ...(status && status !== "ALL" ? { status } : {}),
      }
    ),

  getPerpBasisLatest: (symbol?: string) =>
    fetchJson<{ symbol: string; snapshot: PerpBasisSnapshot | null }>(
      "/perp-basis/latest",
      symbol ? { symbol } : undefined,
    ),

  getPerpBasisHistory: (symbol?: string, limit = 20) =>
    fetchJson<{ symbol: string; snapshots: PerpBasisSnapshot[] }>(
      "/perp-basis/history",
      { limit: String(limit), ...(symbol ? { symbol } : {}) },
    ),

  getWallets: () =>
    fetchJson<VenueWalletSnapshot>("/paper-wallets"),

  getPerformance: () =>
    fetchJson<PerformanceSummary>("/performance/summary"),

  getStrategyRankings: async () => normalizeRankings(await fetchJson<any>("/strategy/rankings")),

  getActivePaperTrades: (symbol?: string) =>
    fetchJson<{ count: number; trades: ActivePaperTrade[] }>(
      "/paper-trades/active",
      symbol ? { symbol } : undefined,
    ),

  getRecentTrades: (limit = 25, symbol?: string) =>
    fetchJson<{ trades: SimulatedTrade[] }>("/performance/recent-trades", {
      limit: String(limit),
      ...(symbol ? { symbol } : {}),
    }),

  getScalpPerformance: () =>
    fetchJson<ScalpPerformanceResponse>("/scalp/performance"),

  getCalibrationDiagnostics: (windowMinutes = 120) =>
    fetchJson<CalibrationDiagnosticsResponse>("/diagnostics/calibration", {
      window_minutes: String(windowMinutes),
    }),

  getLogs: (limit = 50) =>
    fetchJson<{ logs: LogEntry[] }>("/logs", { limit: String(limit) }),

  runBacktest: (payload: BacktestRunRequest) =>
    postJson<{ run_id: string; status: string }>("/backtest/run", payload),

  getBacktestStatus: (runId: string) =>
    fetchJson<{
      run: BacktestRun;
      is_active_thread: boolean;
      latest_events: Array<{ ts: string; level: string; message: string; payload: Record<string, unknown> }>;
    }>(`/backtest/status/${runId}`),

  getBacktestResult: (runId: string) =>
    fetchJson<BacktestReport>(`/backtest/result/${runId}`),

  listBacktestRuns: (limit = 25, offset = 0) =>
    fetchJson<{ runs: BacktestRun[]; pagination: { limit: number; offset: number; returned: number } }>(
      "/backtest/runs",
      { limit: String(limit), offset: String(offset) },
    ),

  cancelBacktest: (runId: string) =>
    postNoBodyJson<{ status: string; run_id: string }>(`/backtest/cancel/${runId}`),

  exportBacktestTradesCsv: (runId: string) =>
    fetchBlob(`/backtest/export/${runId}`, { format: "csv" }),

  exportBacktestEquityCsv: (runId: string) =>
    fetchBlob(`/backtest/export/${runId}`, { format: "equity_csv" }),

  resetWallets: (clearHistory = false) =>
    fetch(`${BASE_URL}/paper-wallets/reset?confirm=true&clear_history=${clearHistory ? "true" : "false"}`, {
      method: "POST",
    }).then(r => r.json()),
};
