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

export interface BotDecision {
  bot?: string;
  strategy: string;
  direction: number;
  confidence: number;
  reasoning: string;
  signal?: string;
  weight?: number;
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

export interface StatusResponse {
  status: string;
  mode: string;
  execution_mode?: string;
  paper_trading_only?: boolean;
  paper_trading: boolean;
  paper_wallets: WalletSnapshot;
  symbol: string;
  supported_symbols: string[];
  signal_intervals: string[];
  latest_signal: Signal | null;
  latest_perp_context?: Record<string, unknown> | null;
  orchestrated_decision: OrchestratedDecision | null;
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
}

export interface StrategyRanking {
  strategy: string;
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
  timestamp: string;
}

export interface ActivePaperTrade {
  trade_type: "single" | "pair";
  symbol: string;
  strategy: string;
  direction: number;
  side: string;
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

function normalizeRankings(raw: any): { strategies: StrategyRanking[] } {
  const rows = Array.isArray(raw?.strategies)
    ? raw.strategies
    : Array.isArray(raw)
    ? raw
    : [];
  return {
    strategies: rows.map((row: any) => ({
      strategy: String(row.strategy || "unknown"),
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
    return {
      ...raw,
      latest_signal: raw.latest_signal ?? null,
      orchestrated_decision: normalizeDecision(raw.orchestrated_decision),
    } as StatusResponse;
  },

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
    fetchJson<WalletSnapshot>("/paper-wallets"),

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

  getLogs: (limit = 50) =>
    fetchJson<{ logs: LogEntry[] }>("/logs", { limit: String(limit) }),

  resetWallets: (clearHistory = false) =>
    fetch(`${BASE_URL}/paper-wallets/reset?confirm=true&clear_history=${clearHistory ? "true" : "false"}`, {
      method: "POST",
    }).then(r => r.json()),
};
