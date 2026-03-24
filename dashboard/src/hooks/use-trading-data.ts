import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useStatus(symbol?: string) {
  return useQuery({
    queryKey: ["status", symbol],
    queryFn: () => api.getStatus(symbol),
    refetchInterval: 5000,
    retry: 2,
  });
}

export function useSignals(limit = 20) {
  return useSignalsForSymbol(undefined, limit);
}

export function useSignalsForSymbol(symbol?: string, limit = 20) {
  return useQuery({
    queryKey: ["signals", symbol, limit],
    queryFn: () => api.getSignals(limit, symbol),
    refetchInterval: 15000,
    retry: 2,
  });
}

export function useOpportunities(symbol?: string, limit = 12) {
  return useQuery({
    queryKey: ["opportunities", symbol, limit],
    queryFn: () => api.getOpportunities(limit, symbol),
    refetchInterval: 15000,
    retry: 2,
  });
}

export function useArbitrageOpportunities(
  symbol?: string,
  arbType = "ALL",
  status = "open",
  limit = 12,
  offset = 0,
) {
  return useQuery({
    queryKey: ["arb-opportunities", symbol, arbType, status, limit, offset],
    queryFn: () => api.getArbitrageOpportunities(limit, symbol, arbType, status, offset),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function usePerpBasisLatest(symbol?: string) {
  return useQuery({
    queryKey: ["perp-basis-latest", symbol],
    queryFn: () => api.getPerpBasisLatest(symbol),
    refetchInterval: 15000,
    retry: 2,
  });
}

export function usePerpBasisHistory(symbol?: string, limit = 20) {
  return useQuery({
    queryKey: ["perp-basis-history", symbol, limit],
    queryFn: () => api.getPerpBasisHistory(symbol, limit),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useWallets() {
  return useQuery({
    queryKey: ["wallets"],
    queryFn: () => api.getWallets(),
    refetchInterval: 5000,
    retry: 2,
  });
}

export function usePerformance() {
  return useQuery({
    queryKey: ["performance"],
    queryFn: () => api.getPerformance(),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useStrategyRankings() {
  return useQuery({
    queryKey: ["rankings"],
    queryFn: () => api.getStrategyRankings(),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useActivePaperTrades(symbol?: string) {
  return useQuery({
    queryKey: ["active-paper-trades", symbol],
    queryFn: () => api.getActivePaperTrades(symbol),
    refetchInterval: 5000,
    retry: 2,
  });
}

export function useRecentTrades(symbol?: string, limit = 25) {
  return useQuery({
    queryKey: ["recent-trades", symbol, limit],
    queryFn: () => api.getRecentTrades(limit, symbol),
    refetchInterval: 10000,
    retry: 2,
  });
}

export function useScalpPerformance() {
  return useQuery({
    queryKey: ["scalp-performance"],
    queryFn: () => api.getScalpPerformance(),
    refetchInterval: 15000,
    retry: 2,
  });
}

export function useCalibrationDiagnostics(windowMinutes = 120) {
  return useQuery({
    queryKey: ["calibration-diagnostics", windowMinutes],
    queryFn: () => api.getCalibrationDiagnostics(windowMinutes),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useLogs(limit = 50) {
  return useQuery({
    queryKey: ["logs", limit],
    queryFn: () => api.getLogs(limit),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useHistorySignals(params: Record<string, string>) {
  return useQuery({
    queryKey: ["history-signals", params],
    queryFn: () => api.getHistorySignals(params),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useHistoryOpportunities(params: Record<string, string>) {
  return useQuery({
    queryKey: ["history-opportunities", params],
    queryFn: () => api.getHistoryOpportunities(params),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useHistoryTrades(params: Record<string, string>) {
  return useQuery({
    queryKey: ["history-trades", params],
    queryFn: () => api.getHistoryTrades(params),
    refetchInterval: 30000,
    retry: 2,
  });
}

export function useBacktestRuns(limit = 25, offset = 0) {
  return useQuery({
    queryKey: ["backtest-runs", limit, offset],
    queryFn: () => api.listBacktestRuns(limit, offset),
    refetchInterval: 10000,
    retry: 2,
  });
}

export function useBacktestStatus(runId?: string) {
  return useQuery({
    queryKey: ["backtest-status", runId],
    queryFn: () => api.getBacktestStatus(String(runId)),
    enabled: Boolean(runId),
    refetchInterval: 3000,
    retry: 2,
  });
}

export function useBacktestResult(runId?: string) {
  return useQuery({
    queryKey: ["backtest-result", runId],
    queryFn: () => api.getBacktestResult(String(runId)),
    enabled: Boolean(runId),
    refetchInterval: 10000,
    retry: 2,
  });
}

export function useRunBacktest() {
  return useMutation({
    mutationFn: api.runBacktest,
  });
}

export function useCancelBacktest() {
  return useMutation({
    mutationFn: api.cancelBacktest,
  });
}
