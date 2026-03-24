"""Backtest analytics and report helpers."""

from __future__ import annotations

import math
from datetime import datetime


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(max(0.0, variance))


def _downside_stdev(values: list[float]) -> float:
    downside = [min(0.0, v) for v in values]
    return _stdev(downside)


def _max_drawdown(equity_curve: list[dict]) -> float:
    if not equity_curve:
        return 0.0
    peak = float(equity_curve[0]["equity"])
    max_dd = 0.0
    for row in equity_curve:
        equity = float(row.get("equity") or 0.0)
        peak = max(peak, equity)
        if peak <= 0:
            continue
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)
    return max_dd


def build_equity_curve(
    trades: list[dict],
    *,
    starting_equity: float,
) -> list[dict]:
    ordered = sorted(trades, key=lambda row: str(row.get("exit_timestamp") or row.get("timestamp") or ""))
    equity = float(starting_equity)
    out: list[dict] = []
    peak = equity

    for row in ordered:
        pnl = float(row.get("pnl") or 0.0)
        ts = str(row.get("exit_timestamp") or row.get("timestamp") or "")
        equity += pnl
        peak = max(peak, equity)
        dd = 0.0 if peak <= 0 else (peak - equity) / peak
        out.append({"ts": ts, "equity": equity, "drawdown": dd})

    return out


def compute_drawdown_curve(equity_curve: list[dict]) -> list[dict]:
    """Compute drawdown curve in percent from equity points."""
    if not equity_curve:
        return []

    rolling_max = 0.0
    out: list[dict] = []
    for row in equity_curve:
        ts = str(row.get("ts") or row.get("timestamp") or "")
        equity = float(row.get("equity") or row.get("value") or 0.0)
        rolling_max = max(rolling_max, equity)
        if rolling_max <= 0:
            drawdown_pct = 0.0
        else:
            drawdown_pct = ((equity - rolling_max) / rolling_max) * 100.0
        out.append({"timestamp": ts, "drawdown_pct": drawdown_pct})
    return out


def compute_metrics(
    trades: list[dict],
    *,
    equity_curve: list[dict],
    start_ts: str,
    end_ts: str,
    starting_equity: float,
) -> dict:
    trades_count = len(trades)
    pnls = [float(t.get("pnl") or 0.0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_pnl = sum(pnls)
    total_return = 0.0 if starting_equity <= 0 else (total_pnl / starting_equity)

    start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
    duration_days = max((end_dt - start_dt).total_seconds() / 86400.0, 1e-9)

    annualized_return = ((1.0 + total_return) ** (365.0 / duration_days) - 1.0) if total_return > -1.0 else -1.0

    mean_pnl = _mean(pnls)
    std_pnl = _stdev(pnls)
    downside_std = _downside_stdev(pnls)

    sharpe = 0.0 if std_pnl == 0 else (mean_pnl / std_pnl) * math.sqrt(max(trades_count, 1))
    sortino = 0.0 if downside_std == 0 else (mean_pnl / downside_std) * math.sqrt(max(trades_count, 1))

    max_drawdown = _max_drawdown(equity_curve)
    calmar = 0.0 if max_drawdown == 0 else annualized_return / max_drawdown

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = float("inf") if gross_loss == 0 and gross_profit > 0 else (gross_profit / gross_loss if gross_loss > 0 else 0.0)

    win_rate = (len(wins) / trades_count) if trades_count else 0.0
    expectancy = mean_pnl

    holding_periods = [float(t.get("duration_seconds") or 0.0) for t in trades]
    avg_holding_period_seconds = _mean(holding_periods)

    # Exposure ratio approximation: total hold time over window time.
    total_hold_seconds = sum(holding_periods)
    window_seconds = max((end_dt - start_dt).total_seconds(), 1.0)
    exposure_ratio = min(1.0, max(0.0, total_hold_seconds / window_seconds))

    fees_paid = sum(float(t.get("fees_paid") or 0.0) for t in trades)
    slippage_paid = sum(float(t.get("slippage_paid") or 0.0) for t in trades)

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "win_rate": win_rate,
        "profit_factor": 0.0 if math.isinf(profit_factor) else profit_factor,
        "expectancy": expectancy,
        "trades_count": trades_count,
        "avg_holding_period_seconds": avg_holding_period_seconds,
        "exposure_ratio": exposure_ratio,
        "gross_profit": gross_profit,
        "gross_loss": -gross_loss,
        "fees_paid": fees_paid,
        "slippage_paid": slippage_paid,
    }
