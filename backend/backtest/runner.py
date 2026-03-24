"""Paper-only backtest runner orchestrator."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import bot as bot_module
from db import Database
from execution_client import build_paper_execution_clients
from risk_engine import RiskEngine
from simulation import SimulationEngine

from .data_loader import BacktestDataLoader, CandleRow, MarketRow
from .reporter import build_equity_curve, compute_metrics
from .results_store import BacktestResultsStore


TIMEFRAME_BAR_SPAN = {
    "5m": 1,
    "15m": 3,
    "1h": 12,
    "4h": 48,
    "1d": 288,
}


@dataclass
class BacktestRequest:
    symbol: str
    venue: str
    market_type: str
    timeframe: str
    start_ts: str
    end_ts: str
    initial_capital: float
    lookback_bars: int
    enable_signal_strategy: bool
    enable_yes_no_arb: bool
    enable_model_vs_market: bool
    slippage_bps: float
    fee_bps: float

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "BacktestRequest":
        return cls(
            symbol=str(payload.get("symbol") or "BTCUSDT").upper(),
            venue=str(payload.get("venue") or "polymarket").lower(),
            market_type=str(payload.get("market_type") or "updown").lower(),
            timeframe=str(payload.get("timeframe") or "5m"),
            start_ts=str(payload.get("start_ts")),
            end_ts=str(payload.get("end_ts")),
            initial_capital=float(payload.get("initial_capital") or 10_000.0),
            lookback_bars=int(payload.get("lookback_bars") or 300),
            enable_signal_strategy=bool(payload.get("enable_signal_strategy", True)),
            enable_yes_no_arb=bool(payload.get("enable_yes_no_arb", True)),
            enable_model_vs_market=bool(payload.get("enable_model_vs_market", True)),
            slippage_bps=float(payload.get("slippage_bps") or 8.0),
            fee_bps=float(payload.get("fee_bps") or 0.0),
        )


class BacktestRunner:
    """Runs a single backtest run_id and writes artifacts to BacktestResultsStore."""

    def __init__(self, results_store: BacktestResultsStore):
        self.results_store = results_store
        self._stop_requested = False

    def run(self, run_id: str, req: BacktestRequest) -> None:
        self.results_store.mark_started(run_id)
        self.results_store.append_event(run_id, "INFO", "backtest_started", payload=req.__dict__)

        isolated_db_path = Path(__file__).resolve().parent / "cache" / f"run_{run_id}.db"
        isolated_db_path.parent.mkdir(parents=True, exist_ok=True)
        replay_db = Database(str(isolated_db_path))

        # Safety: construct TradingBot with an injected DB factory so __init__
        # cannot write to the default live DB path.
        original_database_factory = bot_module.Database
        bot_module.Database = lambda: replay_db
        try:
            bot = bot_module.TradingBot()
        finally:
            bot_module.Database = original_database_factory

        # Force strict paper mode and deterministic replay behavior.
        bot.execution_mode = "paper"
        bot.config["execution_mode"] = "paper"
        bot.config.setdefault("execution", {})["mode"] = "paper"
        bot.config.setdefault("trading", {})["execution_mode"] = "paper"
        assert bot.execution_mode == "paper", "Backtest must run in paper mode only"
        assert bot.config.get("execution_mode") == "paper", "Backtest config must remain paper-only"
        bot.max_signal_age_seconds = 10**12
        bot.max_market_age_seconds = 10**12
        bot.emit_signals_only = False

        # Re-wire dependencies to use isolated DB.
        risk_cfg = dict(bot.config.get("trading", {}))
        risk_cfg["execution_mode"] = "paper"
        risk_cfg["risk"] = bot.config.get("risk", {})
        bot.risk_engine = RiskEngine(risk_cfg)
        bot.simulation = SimulationEngine(replay_db, bot.config)
        pm_client, hl_client = build_paper_execution_clients(mode="paper", db=replay_db, trading_cfg=bot.config["trading"])
        bot.polymarket_execution_client = pm_client
        bot.hyperliquid_execution_client = hl_client

        # Keep backtest offline: no live book requests.
        bot.polymarket.get_top_of_book = lambda token_id: {}

        loader = BacktestDataLoader(replay_db)

        try:
            candles = loader.load_binance_candles(
                symbol=req.symbol,
                interval=req.timeframe,
                start_ts=req.start_ts,
                end_ts=req.end_ts,
            )
            markets = loader.load_polymarket_snapshots(
                symbol=req.symbol,
                start_ts=req.start_ts,
                end_ts=req.end_ts,
            )

            if not candles:
                raise ValueError("No Binance candles available for requested window")
            if not markets:
                raise ValueError("No Polymarket snapshots available for requested window")

            self.results_store.append_event(
                run_id,
                "INFO",
                "data_loaded",
                payload={
                    "candles": len(candles),
                    "markets": len(markets),
                },
            )

            for idx, candle in enumerate(candles):
                if self._stop_requested:
                    self.results_store.append_event(run_id, "INFO", "backtest_cancelled")
                    self.results_store.update_run_status(run_id, "cancelled")
                    return
                if idx < req.lookback_bars:
                    continue

                signal_snapshot = self._build_snapshot(bot, candles, idx, req.symbol, req.timeframe)
                if signal_snapshot is None:
                    continue

                bot.latest_signals[req.symbol] = signal_snapshot
                bot.latest_signal = signal_snapshot

                market_rows = loader.nearest_market_snapshot(markets, at_ts=candle.timestamp)
                if not market_rows:
                    continue

                for market_row in market_rows:
                    if req.market_type == "updown" and (not bot._is_supported_up_down_market(market_row.market_name)):  # noqa: SLF001
                        continue

                    market = self._market_row_to_dict(market_row)
                    market_id = replay_db.insert_market(
                        condition_id=market["market_id"],
                        market_name=market["market_name"],
                        yes_price=float(market["yes_price"]),
                        no_price=float(market["no_price"]),
                        yes_ask=float(market["yes_ask"] or market["yes_price"]),
                        no_ask=float(market["no_ask"] or market["no_price"]),
                        spread_bps=float(market["spread_bps"] or 0.0),
                        liquidity=float(market["liquidity"] or 0.0),
                        end_date=market.get("end_date"),
                        fetched_at=market["fetched_at"],
                    )

                    if req.enable_yes_no_arb:
                        bot._evaluate_arbitrage(market, market_id, symbol=req.symbol)  # noqa: SLF001
                    if req.enable_model_vs_market:
                        bot._evaluate_fair_value_arb(market, market_id, symbol=req.symbol)  # noqa: SLF001
                    if req.enable_signal_strategy:
                        bot._evaluate_signal(market, market_id, signal_snapshot, symbol=req.symbol)  # noqa: SLF001

                if idx % 200 == 0:
                    self.results_store.append_event(
                        run_id,
                        "INFO",
                        "replay_progress",
                        payload={"processed_candles": idx, "total_candles": len(candles)},
                    )

            closed_trades = self._close_open_trades(replay_db, markets, req)
            equity_curve = build_equity_curve(closed_trades, starting_equity=req.initial_capital)
            metrics = compute_metrics(
                closed_trades,
                equity_curve=equity_curve,
                start_ts=req.start_ts,
                end_ts=req.end_ts,
                starting_equity=req.initial_capital,
            )

            for row in equity_curve:
                self.results_store.append_equity(run_id, row["ts"], row["equity"], row["drawdown"])
            for row in closed_trades:
                self.results_store.append_trade(run_id, row)

            self.results_store.upsert_metrics(run_id, metrics)
            self.results_store.mark_completed(run_id)
            self.results_store.append_event(
                run_id,
                "INFO",
                "backtest_completed",
                payload={"trades": len(closed_trades), "metrics": metrics},
            )
        except Exception as exc:
            self.results_store.mark_failed(run_id, str(exc))
            self.results_store.append_event(run_id, "ERROR", "backtest_failed", payload={"error": str(exc)})
            raise

    def _build_snapshot(
        self,
        bot: bot_module.TradingBot,
        candles: list[CandleRow],
        idx: int,
        symbol: str,
        base_interval: str,
    ) -> dict | None:
        current = candles[idx]
        current_dt = datetime.fromisoformat(current.timestamp.replace("Z", "+00:00"))
        signals_by_interval: dict[str, dict] = {}

        for timeframe in bot.signal_intervals:
            bars = TIMEFRAME_BAR_SPAN.get(timeframe)
            if bars is None:
                continue
            start_idx = idx - bars
            if start_idx < 0:
                continue
            prior = candles[start_idx]
            if prior.close <= 0:
                continue
            move_pct = (current.close - prior.close) / prior.close
            confidence = min(1.0, abs(move_pct) / max(bot.signal_neutral_band_pct, 1e-6))
            if abs(move_pct) < bot.signal_neutral_band_pct:
                trend = "neutral"
            else:
                trend = "bullish" if move_pct > 0 else "bearish"

            signals_by_interval[timeframe] = {
                "trend": trend,
                "confidence": confidence,
                "move_pct": move_pct,
                "reasoning": f"historical_replay bars={bars}",
            }

        if not bot._is_signal_complete(signals_by_interval):  # noqa: SLF001
            return None

        trend, confidence, signal_strength, reasoning = bot._combine_trends(signals_by_interval, symbol)  # noqa: SLF001
        regime = bot._infer_regime(signals_by_interval)  # noqa: SLF001
        strategy = bot._select_strategy(trend, confidence, regime)  # noqa: SLF001

        return {
            "signal_sequence_id": idx + 1,
            "source": "binance_replay",
            "trend": trend,
            "confidence": confidence,
            "value": float(current.close),
            "timestamp": current_dt.isoformat(),
            "timeframes": signals_by_interval,
            "signal_strength": signal_strength,
            "reasoning": reasoning,
            "regime": regime,
            "strategy": strategy,
            "symbol": symbol,
            "micro_data": {
                "symbol": symbol,
                "source_interval": base_interval,
                "move_pct_short": signals_by_interval.get("5m", {}).get("move_pct", 0.0),
                "time_horizon": "short",
                "volume_spike": False,
                "volume_ratio": 1.0,
                "spread_bps": 0.0,
            },
        }

    def _market_row_to_dict(self, row: MarketRow) -> dict:
        return {
            "market_id": row.market_id,
            "market_name": row.market_name,
            "yes_price": row.yes_price,
            "no_price": row.no_price,
            "yes_ask": row.yes_ask,
            "no_ask": row.no_ask,
            "spread_bps": row.spread_bps,
            "liquidity": row.liquidity,
            "end_date": row.end_date,
            "fetched_at": row.timestamp,
            "timestamp": row.timestamp,
        }

    def _close_open_trades(self, replay_db: Database, markets: list[MarketRow], req: BacktestRequest) -> list[dict]:
        latest_by_market: dict[str, MarketRow] = {}
        for row in markets:
            previous = latest_by_market.get(row.market_id)
            if previous is None or previous.timestamp <= row.timestamp:
                latest_by_market[row.market_id] = row

        with replay_db._connect() as conn:  # noqa: SLF001
            open_rows = conn.execute(
                "SELECT * FROM trades_simulated WHERE COALESCE(status, 'closed')='open' ORDER BY id ASC"
            ).fetchall()

            closed_trades: list[dict] = []
            for row in open_rows:
                row_dict = dict(row)
                market_id = str(row_dict.get("symbol") or "")
                market = latest_by_market.get(market_id)
                if market is None:
                    continue

                direction = int(row_dict.get("direction") or 0)
                entry_price = float(row_dict.get("entry_price") or 0.0)
                size = float(row_dict.get("size") or 0.0)
                if entry_price <= 0 or size <= 0 or direction == 0:
                    continue

                side = "YES" if direction > 0 else "NO"
                exit_price_raw = market.yes_price if direction > 0 else market.no_price
                exit_price = max(1e-9, float(exit_price_raw))
                qty = size / entry_price

                gross_pnl = (exit_price - entry_price) * qty * direction
                fee_cost = size * (req.fee_bps / 10_000.0)
                slippage_cost = size * (req.slippage_bps / 10_000.0)
                net_pnl = gross_pnl - fee_cost - slippage_cost

                open_ts_raw = str(row_dict.get("entry_timestamp") or row_dict.get("timestamp") or "")
                open_ts = datetime.fromisoformat(open_ts_raw.replace("Z", "+00:00"))
                close_ts = datetime.fromisoformat(market.timestamp.replace("Z", "+00:00"))
                hold_seconds = max(0, int((close_ts - open_ts).total_seconds()))

                conn.execute(
                    "UPDATE trades_simulated SET status='closed', pnl=?, exit_price=?, duration_seconds=?, duration=?, exit_timestamp=?, timestamp=? WHERE id=?",
                    (
                        float(net_pnl),
                        float(exit_price),
                        hold_seconds,
                        hold_seconds,
                        close_ts.isoformat(),
                        close_ts.isoformat(),
                        int(row_dict["id"]),
                    ),
                )

                closed_trades.append(
                    {
                        **row_dict,
                        "ts": close_ts.isoformat(),
                        "timestamp": close_ts.isoformat(),
                        "exit_timestamp": close_ts.isoformat(),
                        "symbol": market_id,
                        "market_id": market_id,
                        "side": side,
                        "qty": qty,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": net_pnl,
                        "strategy": row_dict.get("strategy"),
                        "confidence": row_dict.get("confidence"),
                        "edge": row_dict.get("edge"),
                        "duration_seconds": hold_seconds,
                        "hold_seconds": hold_seconds,
                        "venue": row_dict.get("venue"),
                        "fees_paid": fee_cost,
                        "slippage_paid": slippage_cost,
                    }
                )

        return closed_trades


class BacktestManager:
    """Tracks backtest jobs and executes them in background threads."""

    def __init__(self, store: BacktestResultsStore):
        self.store = store
        self._threads: dict[str, threading.Thread] = {}
        self._active_runners: dict[str, BacktestRunner] = {}
        self._lock = threading.Lock()

    def queue_run(self, payload: dict[str, Any]) -> str:
        req = BacktestRequest.from_payload(payload)
        run_id = self.store.create_run(
            symbol=req.symbol,
            venue=req.venue,
            market_type=req.market_type,
            start_ts=req.start_ts,
            end_ts=req.end_ts,
            timeframe=req.timeframe,
            strategy_scope="signal+arb",
            params=req.__dict__,
        )

        runner = BacktestRunner(self.store)
        thread = threading.Thread(target=self._run_thread, args=(run_id, req, runner), daemon=True)
        with self._lock:
            self._active_runners[run_id] = runner
            self._threads[run_id] = thread
        thread.start()
        return run_id

    def _run_thread(self, run_id: str, req: BacktestRequest, runner: BacktestRunner) -> None:
        try:
            runner.run(run_id, req)
        finally:
            with self._lock:
                self._active_runners.pop(run_id, None)
                self._threads.pop(run_id, None)

    def cancel_run(self, run_id: str) -> bool:
        with self._lock:
            runner = self._active_runners.get(run_id)
        if runner is None:
            return False
        runner._stop_requested = True
        self.store.update_run_status(run_id, "cancelling")
        self.store.append_event(run_id, "INFO", "cancellation_requested")
        return True

    def get_status(self, run_id: str) -> dict | None:
        run = self.store.get_run(run_id)
        if run is None:
            return None
        with self._lock:
            thread = self._threads.get(run_id)
        return {
            "run": run,
            "is_active_thread": bool(thread and thread.is_alive()),
            "latest_events": self.store.get_events(run_id, limit=10),
        }
