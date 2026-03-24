import { useEffect, useMemo, useState } from "react";
import { useSymbol } from "@/contexts/SymbolContext";
import { useBacktestResult, useBacktestRuns, useBacktestStatus, useCancelBacktest, useRunBacktest } from "@/hooks/use-trading-data";
import { api, type BacktestReport, type BacktestRunRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const defaultWindow = () => {
  const end = new Date();
  const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000);
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
};

export default function BacktestPage() {
  const { symbol } = useSymbol();
  const windowDefaults = useMemo(() => defaultWindow(), []);
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(undefined);
  const [cancelPendingRunIds, setCancelPendingRunIds] = useState<Record<string, boolean>>({});
  const [compareRunIds, setCompareRunIds] = useState<string[]>([]);
  const [compareReports, setCompareReports] = useState<Record<string, BacktestReport>>({});
  const [payload, setPayload] = useState<BacktestRunRequest>({
    symbol,
    timeframe: "5m",
    start_ts: windowDefaults.start,
    end_ts: windowDefaults.end,
    initial_capital: 10000,
    lookback_bars: 300,
    venue: "hyperliquid",
    market_type: "updown",
    enable_signal_strategy: true,
    enable_funding_arb: true,
    enable_basis_arb: true,
    slippage_bps: 8,
    fee_bps: 0,
  });

  const runs = useBacktestRuns(30, 0);
  const runStatus = useBacktestStatus(selectedRunId);
  const runResult = useBacktestResult(selectedRunId);
  const runMutation = useRunBacktest();
  const cancelMutation = useCancelBacktest();

  const activeRunStatus = runStatus.data?.run?.status;
  const selectedStatus = selectedRunId && cancelPendingRunIds[selectedRunId]
    ? "cancelling"
    : (activeRunStatus ?? "loading");

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    const status = runStatus.data?.run?.status;
    if (!status || (status !== "cancelled" && status !== "failed" && status !== "completed")) {
      return;
    }
    setCancelPendingRunIds((prev) => {
      if (!prev[selectedRunId]) {
        return prev;
      }
      const next = { ...prev };
      delete next[selectedRunId];
      return next;
    });
  }, [selectedRunId, runStatus.data?.run?.status]);

  useEffect(() => {
    let cancelled = false;
    const loadCompareReports = async () => {
      if (compareRunIds.length < 2) {
        setCompareReports({});
        return;
      }
      const ids = compareRunIds.slice(0, 4);
      const rows = await Promise.all(
        ids.map(async (runId) => {
          const report = await api.getBacktestResult(runId);
          return [runId, report] as const;
        }),
      );
      if (cancelled) {
        return;
      }
      setCompareReports(Object.fromEntries(rows));
    };
    loadCompareReports().catch(() => {
      if (!cancelled) {
        setCompareReports({});
      }
    });
    return () => {
      cancelled = true;
    };
  }, [compareRunIds]);

  const onSubmit = async () => {
    const merged = {
      ...payload,
      symbol,
    };
    const result = await runMutation.mutateAsync(merged);
    setSelectedRunId(result.run_id);
  };

  const onCancel = async (runId: string) => {
    setCancelPendingRunIds((prev) => ({ ...prev, [runId]: true }));
    try {
      await cancelMutation.mutateAsync(runId);
    } catch {
      setCancelPendingRunIds((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
    }
  };

  const toggleCompareRun = (runId: string) => {
    setCompareRunIds((prev) => {
      if (prev.includes(runId)) {
        return prev.filter((id) => id !== runId);
      }
      if (prev.length >= 4) {
        return prev;
      }
      return [...prev, runId];
    });
  };

  const downloadBlob = (blob: Blob, fileName: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportTradesCsv = async () => {
    if (!selectedRunId) return;
    const blob = await api.exportBacktestTradesCsv(selectedRunId);
    downloadBlob(blob, `backtest_trades_${selectedRunId}.csv`);
  };

  const exportEquityCsv = async () => {
    if (!selectedRunId) return;
    const blob = await api.exportBacktestEquityCsv(selectedRunId);
    downloadBlob(blob, `backtest_equity_${selectedRunId}.csv`);
  };

  const selectedEquity = runResult.data?.equity_curve ?? [];
  const selectedDrawdown = runResult.data?.drawdown_curve ?? [];
  const startingValue = selectedEquity.length > 0 ? Number(selectedEquity[0].value || 0) : 0;
  const maxDrawdownPct = selectedDrawdown.reduce((acc, row) => Math.min(acc, Number(row.drawdown_pct || 0)), 0);
  const selectedEquitySeries = selectedEquity.map((row) => {
    const value = Number(row.value || 0);
    return {
      timestamp: row.timestamp,
      value,
      aboveStart: value >= startingValue ? value : null,
      belowStart: value < startingValue ? value : null,
    };
  });

  const compareMetricsRows = [
    { label: "Total PnL", key: "gross_profit" as const, format: (report: BacktestReport) => (Number(report.metrics?.gross_profit || 0) + Number(report.metrics?.gross_loss || 0)).toFixed(2) },
    { label: "Win Rate", key: "win_rate" as const, format: (report: BacktestReport) => `${(Number(report.metrics?.win_rate || 0) * 100).toFixed(1)}%` },
    { label: "Sharpe", key: "sharpe" as const, format: (report: BacktestReport) => Number(report.metrics?.sharpe || 0).toFixed(2) },
    { label: "Max Drawdown", key: "max_drawdown" as const, format: (report: BacktestReport) => `${(Number(report.metrics?.max_drawdown || 0) * 100).toFixed(2)}%` },
    { label: "Total Trades", key: "trades_count" as const, format: (report: BacktestReport) => String(report.metrics?.trades_count || 0) },
    {
      label: "Strategies",
      key: "strategies" as const,
      format: (report: BacktestReport) => {
        const set = new Set(
          (report.trades || [])
            .map((row) => String(row.strategy || "").trim())
            .filter(Boolean),
        );
        return Array.from(set).join(", ") || "-";
      },
    },
    { label: "Date Range", key: "date_range" as const, format: (report: BacktestReport) => `${report.run.start_ts.slice(0, 10)} -> ${report.run.end_ts.slice(0, 10)}` },
  ];

  const compareOverlayData = useMemo(() => {
    const ids = compareRunIds.slice(0, 4);
    if (ids.length < 2) {
      return [] as Array<Record<string, string | number | null>>;
    }
    const timeline = new Map<string, Record<string, string | number | null>>();
    ids.forEach((runId) => {
      const report = compareReports[runId];
      if (!report) {
        return;
      }
      (report.equity_curve || []).forEach((point) => {
        const ts = String(point.timestamp || "");
        if (!timeline.has(ts)) {
          timeline.set(ts, { timestamp: ts });
        }
        timeline.get(ts)![runId] = Number(point.value || 0);
      });
    });
    return Array.from(timeline.values()).sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)));
  }, [compareReports, compareRunIds]);

  const compareColors = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444"];

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Backtesting</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Historical paper-only replay. Uses strategy, risk, and paper execution logic with strict no-lookahead.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-border bg-card p-4">
          <h2 className="font-mono text-sm text-foreground">Run Backtest</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="font-mono text-xs">Timeframe</Label>
              <Select value={payload.timeframe} onValueChange={(v) => setPayload((prev) => ({ ...prev, timeframe: v as BacktestRunRequest["timeframe"] }))}>
                <SelectTrigger className="h-8 font-mono text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="5m">5m</SelectItem>
                  <SelectItem value="15m">15m</SelectItem>
                  <SelectItem value="1h">1h</SelectItem>
                  <SelectItem value="4h">4h</SelectItem>
                  <SelectItem value="1d">1d</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-xs">Initial Capital (USDC)</Label>
              <Input
                value={String(payload.initial_capital ?? 10000)}
                onChange={(e) => setPayload((prev) => ({ ...prev, initial_capital: Number(e.target.value || 0) }))}
                className="h-8 font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-xs">Start (ISO)</Label>
              <Input
                value={payload.start_ts}
                onChange={(e) => setPayload((prev) => ({ ...prev, start_ts: e.target.value }))}
                className="h-8 font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-xs">End (ISO)</Label>
              <Input
                value={payload.end_ts}
                onChange={(e) => setPayload((prev) => ({ ...prev, end_ts: e.target.value }))}
                className="h-8 font-mono text-xs"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button className="h-8 font-mono text-xs" onClick={onSubmit} disabled={runMutation.isPending}>
              {runMutation.isPending ? "Queueing..." : "Run Backtest"}
            </Button>
            {runMutation.error ? (
              <span className="font-mono text-xs text-destructive">{String(runMutation.error)}</span>
            ) : null}
          </div>
        </div>

        <div className="space-y-3 rounded-xl border border-border bg-card p-4">
          <h2 className="font-mono text-sm text-foreground">Recent Runs</h2>
          <div className="max-h-[260px] overflow-auto rounded-lg border border-border/60">
            <table className="w-full min-w-[560px] text-left font-mono text-xs">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="px-2 py-2">Compare</th>
                  <th className="px-2 py-2">Run</th>
                  <th className="px-2 py-2">Symbol</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Window</th>
                  <th className="px-2 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {(runs.data?.runs ?? []).map((row) => (
                  <tr
                    key={row.run_id}
                    className={`cursor-pointer border-t border-border/60 ${selectedRunId === row.run_id ? "bg-primary/10" : ""}`}
                    onClick={() => setSelectedRunId(row.run_id)}
                  >
                    <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={compareRunIds.includes(row.run_id)}
                        disabled={!compareRunIds.includes(row.run_id) && compareRunIds.length >= 4}
                        onChange={() => toggleCompareRun(row.run_id)}
                      />
                    </td>
                    <td className="px-2 py-2">{row.run_id.slice(0, 8)}</td>
                    <td className="px-2 py-2">{row.symbol}</td>
                    <td className="px-2 py-2">{cancelPendingRunIds[row.run_id] ? "cancelling" : row.status}</td>
                    <td className="px-2 py-2">{row.start_ts.slice(0, 10)} → {row.end_ts.slice(0, 10)}</td>
                    <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                      {row.status === "running" ? (
                        <Button
                          className="h-7 px-2 font-mono text-[10px]"
                          variant="outline"
                          disabled={Boolean(cancelPendingRunIds[row.run_id])}
                          onClick={() => onCancel(row.run_id)}
                        >
                          {cancelPendingRunIds[row.run_id] ? "Cancelling..." : "Cancel"}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="font-mono text-[10px] text-muted-foreground">
            Compare mode: select 2 to 4 runs from the first column.
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 font-mono text-sm text-foreground">Selected Run Details</h2>
        {!selectedRunId ? (
          <p className="font-mono text-xs text-muted-foreground">Select a run to inspect status and report.</p>
        ) : (
          <div className="space-y-2 font-mono text-xs">
            <p>Status: {selectedStatus}</p>
            <p>Active thread: {runStatus.data?.is_active_thread ? "yes" : "no"}</p>
            <div className="flex items-center gap-2">
              <Button className="h-8 font-mono text-xs" variant="outline" onClick={exportTradesCsv} disabled={!runResult.data}>
                Export Trades CSV
              </Button>
              <Button className="h-8 font-mono text-xs" variant="outline" onClick={exportEquityCsv} disabled={!runResult.data}>
                Export Equity CSV
              </Button>
            </div>
            {runResult.data?.metrics ? (
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="rounded border border-border/60 p-2">
                  Return: {(runResult.data.metrics.total_return * 100).toFixed(2)}%
                </div>
                <div className="rounded border border-border/60 p-2">
                  Win rate: {(runResult.data.metrics.win_rate * 100).toFixed(1)}%
                </div>
                <div className="rounded border border-border/60 p-2">
                  Max DD: {(runResult.data.metrics.max_drawdown * 100).toFixed(2)}%
                </div>
                <div className="rounded border border-border/60 p-2">
                  Sharpe: {runResult.data.metrics.sharpe.toFixed(2)}
                </div>
                <div className="rounded border border-border/60 p-2">
                  Trades: {runResult.data.metrics.trades_count}
                </div>
                <div className="rounded border border-border/60 p-2">
                  Exposure: {(runResult.data.metrics.exposure_ratio * 100).toFixed(1)}%
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground">Metrics are not available yet.</p>
            )}
            <p>Equity points: {selectedEquity.length}</p>
            <p>Trades: {runResult.data?.trades?.length ?? 0}</p>

            {selectedStatus === "completed" && selectedEquity.length > 0 ? (
              <div className="space-y-4">
                <div className="h-64 rounded border border-border/60 p-2">
                  <p className="mb-2 font-mono text-xs text-muted-foreground">Equity Curve</p>
                  <ResponsiveContainer width="100%" height="90%">
                    <LineChart data={selectedEquitySeries} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="timestamp" hide />
                      <YAxis width={80} tickFormatter={(v) => `${Number(v).toFixed(0)}`} />
                      <Tooltip
                        formatter={(value: number) => [`${Number(value).toFixed(3)} USDC`, "Equity"]}
                        labelFormatter={(label) => String(label)}
                      />
                      <ReferenceLine y={startingValue} stroke="#94a3b8" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="aboveStart" stroke="#22c55e" dot={false} strokeWidth={2} connectNulls />
                      <Line type="monotone" dataKey="belowStart" stroke="#ef4444" dot={false} strokeWidth={2} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="h-48 rounded border border-border/60 p-2">
                  <p className="mb-2 font-mono text-xs text-muted-foreground">Drawdown (%)</p>
                  <ResponsiveContainer width="100%" height="85%">
                    <AreaChart data={selectedDrawdown} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="timestamp" hide />
                      <YAxis width={70} tickFormatter={(v) => `${Number(v).toFixed(1)}%`} />
                      <Tooltip
                        formatter={(value: number) => [`${Number(value).toFixed(3)}%`, "Drawdown"]}
                        labelFormatter={(label) => String(label)}
                      />
                      <ReferenceLine
                        y={maxDrawdownPct}
                        stroke="#ef4444"
                        strokeDasharray="4 4"
                        label={{ value: `Max DD ${maxDrawdownPct.toFixed(2)}%`, fill: "#ef4444", position: "insideTopRight" }}
                      />
                      <Area type="monotone" dataKey="drawdown_pct" stroke="#ef4444" fill="#ef4444" fillOpacity={0.22} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {compareRunIds.length >= 2 ? (
        <div className="space-y-3 rounded-xl border border-border bg-card p-4">
          <h2 className="font-mono text-sm text-foreground">Compare Runs</h2>
          <div className="overflow-x-auto rounded border border-border/60">
            <table className="w-full min-w-[720px] text-left font-mono text-xs">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="px-2 py-2">Metric</th>
                  {compareRunIds.map((runId) => (
                    <th key={runId} className="px-2 py-2">{runId.slice(0, 8)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {compareMetricsRows.map((row) => (
                  <tr key={row.label} className="border-t border-border/60">
                    <td className="px-2 py-2 text-muted-foreground">{row.label}</td>
                    {compareRunIds.map((runId) => {
                      const report = compareReports[runId];
                      return (
                        <td key={`${row.label}-${runId}`} className="px-2 py-2">
                          {report ? row.format(report) : "loading"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="h-72 rounded border border-border/60 p-2">
            <p className="mb-2 font-mono text-xs text-muted-foreground">Equity Overlay</p>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={compareOverlayData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis width={80} />
                <Tooltip />
                {compareRunIds.map((runId, index) => (
                  <Line
                    key={runId}
                    type="monotone"
                    dataKey={runId}
                    dot={false}
                    stroke={compareColors[index % compareColors.length]}
                    strokeWidth={2}
                    name={runId.slice(0, 8)}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}
    </div>
  );
}
