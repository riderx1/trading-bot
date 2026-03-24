"""
api.py - FastAPI REST server for the trading bot dashboard.

Endpoints:
  GET /status   → bot status, uptime, thread health
  GET /markets  → latest Polymarket YES/NO price snapshots
  GET /signals  → latest Binance BTC trend signals
  GET /trades   → trade history (paper or live)
  GET /logs     → application log entries

The bot is started automatically on server startup and stopped on shutdown.

Run:
    python api.py
    # or
    uvicorn api:app --host 0.0.0.0 --port 8000
"""

import json
import re
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from bot import TradingBot
from db import Database
from ta_scanner import TechnicalScanner

SYMBOL_KEYWORDS = {
    "BTCUSDT": ["bitcoin", "btc"],
    "ETHUSDT": ["ethereum", "eth"],
    "SOLUSDT": ["solana", "sol"],
}

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Trading Bot API",
    description="REST API for the Polymarket crypto trading bot.",
    version="0.1.0",
)

# Allow the Next.js dashboard (localhost:3000 or Vercel) to reach this server.
# In production, replace allow_origins=["*"] with your exact dashboard domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Shared instances ───────────────────────────────────────────────────────────

# One bot + DB instance shared across all requests for the process lifetime.
bot = TradingBot()
db = Database()
scanner = TechnicalScanner(bot.config)
bot.attach_scanner(scanner)
_start_time = datetime.utcnow()


def _strategy_to_venue(strategy: str) -> str:
    key = str(strategy or "").strip().lower()
    polymarket_strategies = {"yes_no", "arbitrage", "polymarket_scalp"}
    if key in polymarket_strategies:
        return "polymarket"
    return "hyperliquid"


def _group_wallets_by_venue(snapshot: dict, cfg: dict) -> dict:
    bots = snapshot.get("bots", {}) if isinstance(snapshot, dict) else {}
    wallet_cfg = cfg.get("paper_wallets", {}) if isinstance(cfg, dict) else {}
    polymarket_cfg = wallet_cfg.get("polymarket", {}) if isinstance(wallet_cfg, dict) else {}
    hyperliquid_cfg = wallet_cfg.get("hyperliquid", {}) if isinstance(wallet_cfg, dict) else {}

    grouped = {
        "polymarket": {},
        "hyperliquid": {},
    }

    for label, balance in polymarket_cfg.items():
        grouped["polymarket"][label] = {
            "balance": float(balance or 0.0),
            "pnl": 0.0,
        }
    for label, balance in hyperliquid_cfg.items():
        grouped["hyperliquid"][label] = {
            "balance": float(balance or 0.0),
            "pnl": 0.0,
        }

    for strategy, row in bots.items():
        available = float((row or {}).get("available_usdc") or 0.0)
        locked = float((row or {}).get("locked_usdc") or 0.0)
        equity = float((row or {}).get("equity_usdc") or 0.0)
        strategy_pnl = equity - (available + locked)
        venue = _strategy_to_venue(strategy)
        grouped.setdefault(venue, {})[strategy] = {
            "balance": equity,
            "pnl": strategy_pnl,
        }

    total = 0.0
    for venue_wallets in grouped.values():
        for row in venue_wallets.values():
            total += float(row.get("balance") or 0.0)

    grouped["total"] = round(total, 6)
    return grouped


# ── Lifecycle events ───────────────────────────────────────────────────────────


@app.on_event("startup")
async def _on_startup():
    """Start the trading bot when the FastAPI server starts."""
    if getattr(bot, "execution_mode", "paper") != "paper":
        raise RuntimeError("Refusing startup: execution mode must be 'paper'.")
    bot.start()
    scanner.start()


@app.on_event("shutdown")
async def _on_shutdown():
    """Cleanly stop the bot when the server receives a shutdown signal."""
    bot.stop()
    scanner.stop()


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/status", summary="Bot status and health")
def get_status(symbol: str = Query(default="BTCUSDT")):
    """
    Return the current bot status.

    Response fields:
      status                  — 'running' or 'stopped'
      mode                    — trading mode: 'arbitrage', 'signal', or 'both'
    emit_signals_only       — true when bot emits opportunities without placing trades
      paper_trading           — true if no real funds are used
      uptime_seconds          — seconds since the API server started
      binance_thread_alive    — whether the Binance polling thread is active
      polymarket_thread_alive — whether the Polymarket polling thread is active
    """
    uptime = (datetime.utcnow() - _start_time).total_seconds()
    target_symbol = (symbol or "BTCUSDT").upper()
    latest_signal = bot.latest_signals.get(target_symbol, {})
    latest_perp_context = bot.latest_perp_context.get(target_symbol, {})
    latest_micro_data = bot.latest_micro_data.get(target_symbol, {})
    orchestrated = bot.latest_orchestrated_decisions.get(target_symbol, {})
    wallets = bot.simulation.get_wallet_snapshot()
    return {
        "status": bot.bot_status,
        "mode": bot.mode,
        "execution_mode": getattr(bot, "execution_mode", "paper"),
        "paper_trading_only": getattr(bot, "execution_mode", "paper") == "paper",
        "emit_signals_only": bot.emit_signals_only,
        "paper_trading": bot.paper_trading,
        "paper_wallets": wallets,
        "paper_wallets_by_venue": _group_wallets_by_venue(wallets, bot.config),
        "consensus_blocked_count": bot._stats.get("consensus_blocked_count", 0),
        "symbol": target_symbol,
        "supported_symbols": bot.supported_symbols,
        "signal_intervals": bot.signal_intervals,
        "market_focus": bot.polymarket.focus_keywords,
        "latest_signal": latest_signal,
        "latest_perp_context": latest_perp_context,
        "latest_micro_data": latest_micro_data,
        "orchestrated_decision": orchestrated,
        "directional_decision": orchestrated.get("directional_decision", {}),
        "arbitrage_decision": orchestrated.get("arbitrage_decision", {}),
        "decision_explainability": orchestrated.get("decision_explainability", {}),
        "latest_scalping_signal": orchestrated.get("latest_scalping_signal"),
        "last_signal_sequence_id": bot.last_signal_sequence_id,
        "last_processed_market_timestamp": bot.last_processed_market_timestamp,
        "uptime_seconds": round(uptime, 1),
        "binance_thread_alive": (
            bot._binance_thread.is_alive()
            if bot._binance_thread is not None
            else False
        ),
        "binance_threads_alive": {sym: (bot._binance_thread.is_alive() if bot._binance_thread is not None else False) for sym in bot.supported_symbols},
        "polymarket_thread_alive": (
            bot._poly_thread.is_alive()
            if bot._poly_thread is not None
            else False
        ),
        "hyperliquid_thread_alive": (
            bot._hl_thread.is_alive()
            if getattr(bot, "_hl_thread", None) is not None
            else False
        ),
        "ta_scanner_thread_alive": scanner.thread_alive,
        "ta_scanner_last_scan_at": scanner.last_scan_at,
        "ta_scanner_last_error": scanner.last_error,
    }


@app.get("/paper-wallets", summary="Paper wallet balances by bot/strategy")
def get_paper_wallets():
    try:
        raw = bot.simulation.get_wallet_snapshot()
        return _group_wallets_by_venue(raw, bot.config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/paper-wallets/reset", summary="Reset paper wallets (optional history clear)")
def reset_paper_wallets(
    clear_history: bool = Query(default=False, description="Clear simulated trades and rankings"),
    confirm: bool = Query(default=False, description="Safety flag, must be true to execute reset"),
):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to reset paper wallets.",
        )
    try:
        snapshot = bot.simulation.reset_wallets(clear_history=clear_history)
        return {
            "status": "ok",
            "message": "paper wallets reset",
            "result": _group_wallets_by_venue(snapshot, bot.config),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/simulated-trades", summary="Simulated trades")
def get_simulated_trades(
    limit: int = Query(default=200, ge=1, le=2000, description="Max rows to return"),
    symbol: str | None = Query(default=None, description="Optional symbol filter"),
    strategy: str | None = Query(default=None, description="Optional strategy filter"),
):
    try:
        return {
            "trades": db.get_simulated_trades(
                limit=limit,
                symbol=(symbol.upper() if symbol else None),
                strategy=strategy,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/paper-trades/active", summary="Active paper trades with unrealized PnL")
def get_active_paper_trades(
    symbol: str | None = Query(default=None, description="Optional symbol filter"),
    strategy: str | None = Query(default=None, description="Optional strategy filter"),
):
    try:
        latest_spot_prices: dict[str, float] = {}
        for sym, payload in bot.latest_signals.items():
            value = payload.get("value") if isinstance(payload, dict) else None
            if value is None:
                continue
            try:
                latest_spot_prices[str(sym).upper()] = float(value)
            except (TypeError, ValueError):
                continue

        trades = bot.simulation.get_active_trades_snapshot(
            latest_spot_prices=latest_spot_prices,
            latest_perp_context=bot.latest_perp_context,
        )

        if symbol:
            target_symbol = symbol.upper()
            trades = [row for row in trades if str(row.get("symbol", "")).upper() == target_symbol]
        if strategy:
            trades = [row for row in trades if str(row.get("strategy", "")) == strategy]

        open_rows = db.get_open_simulated_trades(
            limit=500,
            symbol=(symbol.upper() if symbol else None),
            strategy=strategy,
        )
        normalized_open = [
            {
                "trade_type": "single",
                "venue": row.get("venue") or "polymarket",
                "symbol": str(row.get("symbol") or ""),
                "strategy": str(row.get("strategy") or ""),
                "direction": int(row.get("direction") or 0),
                "side": "LONG" if int(row.get("direction") or 0) > 0 else "SHORT",
                "entry_price": float(row.get("entry_price") or 0.0),
                "current_price": None,
                "quantity": None,
                "stake_usdc": float(row.get("size") or 0.0),
                "unrealized_pnl": float(row.get("pnl") or 0.0),
                "opened_at": str(row.get("entry_timestamp") or row.get("timestamp") or ""),
                "duration_seconds": int(row.get("duration_seconds") or 0),
                "signal_strength": row.get("signal_strength"),
                "regime": row.get("regime"),
                "timeframe": row.get("timeframe"),
            }
            for row in open_rows
        ]
        merged = trades + normalized_open
        merged.sort(key=lambda row: str(row.get("opened_at") or ""), reverse=True)

        return {
            "count": len(merged),
            "trades": merged,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/performance/summary", summary="Performance summary")
def get_performance_summary():
    try:
        payload = db.get_performance_summary()
        payload["venue"] = "mixed"
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/performance/by-strategy", summary="Performance by strategy")
def get_performance_by_strategy():
    try:
        return {"strategies": db.get_performance_by_strategy()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/performance/by-symbol", summary="Performance by symbol")
def get_performance_by_symbol():
    try:
        return {"symbols": db.get_performance_by_symbol()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/performance/recent-trades", summary="Recent simulated trades")
def get_performance_recent_trades(
    limit: int = Query(default=50, ge=1, le=1000, description="Max rows to return"),
    symbol: str | None = Query(default=None, description="Optional symbol filter"),
    strategy: str | None = Query(default=None, description="Optional strategy filter"),
):
    try:
        if symbol or strategy:
            rows = db.get_simulated_trades(
                limit=limit,
                symbol=(symbol.upper() if symbol else None),
                strategy=strategy,
            )
        else:
            rows = db.get_recent_simulated_trades(limit=limit)
        return {"trades": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/strategy/rankings", summary="Strategy rankings")
def get_strategy_rankings(recompute: bool = Query(default=False)):
    try:
        if recompute:
            rankings = db.recompute_strategy_performance()
            return {
                "strategies": [
                    {
                        **row,
                        "venue": _strategy_to_venue(str(row.get("strategy") or "")),
                    }
                    for row in rankings
                ]
            }
        return {
            "strategies": [
                {
                    **row,
                    "venue": _strategy_to_venue(str(row.get("strategy") or "")),
                }
                for row in db.get_strategy_rankings()
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/strategies/rankings", summary="Strategy rankings (alias)")
def get_strategies_rankings_alias(recompute: bool = Query(default=False)):
    return get_strategy_rankings(recompute=recompute)


@app.get("/history/signals", summary="Signal history with filters")
def get_history_signals(
    limit: int = Query(default=200, ge=1, le=2000),
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    start_date: str | None = Query(default=None, description="ISO datetime lower bound"),
    end_date: str | None = Query(default=None, description="ISO datetime upper bound"),
):
    try:
        return {
            "signals": db.get_history_signals(
                limit=limit,
                symbol=(symbol.upper() if symbol else None),
                timeframe=timeframe,
                strategy=strategy,
                start_ts=start_date,
                end_ts=end_date,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/history/opportunities", summary="Opportunity history with filters")
def get_history_opportunities(
    limit: int = Query(default=200, ge=1, le=2000),
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    try:
        return {
            "opportunities": db.get_history_opportunities(
                limit=limit,
                symbol=(symbol.upper() if symbol else None),
                timeframe=timeframe,
                strategy=strategy,
                start_ts=start_date,
                end_ts=end_date,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/history/trades", summary="Simulated trade history with filters")
def get_history_trades(
    limit: int = Query(default=200, ge=1, le=2000),
    symbol: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    try:
        return {
            "trades": db.get_history_trades(
                limit=limit,
                symbol=(symbol.upper() if symbol else None),
                strategy=strategy,
                start_ts=start_date,
                end_ts=end_date,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/markets", summary="Latest Polymarket price snapshots")
def get_markets(
    limit: int = Query(default=50, ge=1, le=500, description="Max rows to return"),
    symbol: str = Query(default="BTCUSDT", description="Trading symbol filter"),
):
    """
    Return the most recent YES/NO price snapshots from Polymarket.

    Query params:
      limit — max number of rows (1–500, default 50)
    """
    try:
        target_symbol = (symbol or "BTCUSDT").upper()
        symbol_keywords = SYMBOL_KEYWORDS.get(target_symbol, SYMBOL_KEYWORDS["BTCUSDT"])
        markets = db.get_latest_markets(limit=limit * 5)
        filtered_markets = [
            market
            for market in markets
            if bot.polymarket.is_relevant_market(market.get("market_name", ""))
            and any(
                re.search(
                    rf"\\b{re.escape(keyword)}\\b",
                    market.get("market_name", "").lower(),
                )
                for keyword in symbol_keywords
            )
        ]

        # Keep only the newest row per market_name to avoid repeated snapshots.
        deduped_markets = []
        seen_names = set()
        for market in filtered_markets:
            name = market.get("market_name", "")
            if name in seen_names:
                continue
            seen_names.add(name)
            deduped_markets.append(market)
            if len(deduped_markets) >= limit:
                break

        # Fallback: if there are no symbol-matching markets, return latest crypto
        # markets so the dashboard still shows active Polymarket pairs.
        if not deduped_markets:
            for market in markets:
                name = market.get("market_name", "")
                if name in seen_names:
                    continue
                if not bot.polymarket.is_relevant_market(name):
                    continue
                seen_names.add(name)
                deduped_markets.append(market)
                if len(deduped_markets) >= limit:
                    break

        return {"markets": deduped_markets}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/signals", summary="Latest BTC trend signals")
def get_signals(
    limit: int = Query(default=20, ge=1, le=200, description="Max rows to return"),
    symbol: str = Query(default="BTCUSDT", description="Trading symbol filter"),
):
    """
    Return the most recent trading signals (Binance BTC price/trend).

    Query params:
      limit — max number of rows (1–200, default 20)
    """
    try:
        target_symbol = (symbol or "BTCUSDT").upper()
        return {"signals": db.get_latest_signals(limit=limit, symbol=target_symbol)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/trades", summary="Trade history")
def get_trades(
    limit: int = Query(default=50, ge=1, le=500, description="Max rows to return"),
):
    """
    Return the most recent trade records (paper or live).

    Query params:
      limit — max number of rows (1–500, default 50)
    """
    try:
        return {"trades": db.get_trades(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/opportunities", summary="Signal opportunities")
def get_opportunities(
    limit: int = Query(default=100, ge=1, le=1000, description="Max rows to return"),
    symbol: str = Query(default="BTCUSDT", description="Trading symbol filter"),
    include_fair_value: bool = Query(default=False, description="Attach latest fair value fields by market_id"),
):
    """
    Return latest signal opportunities generated by the bot.

    These are signal candidates only and may not correspond to executed trades.
    """
    try:
        target_symbol = (symbol or "BTCUSDT").upper()
        raw = db.get_opportunities(limit=limit * 5, symbol=target_symbol)

        # Fallback to all symbols if no opportunities exist for selected symbol.
        if not raw:
            raw = db.get_opportunities(limit=limit * 5)

        allowed_timeframes = set(bot.signal_intervals)
        filtered = [
            row
            for row in raw
            if row.get("timeframe") in allowed_timeframes
        ]

        # Keep the newest row per (market, timeframe, side, trend).
        deduped = []
        seen = set()
        for row in filtered:
            key = (
                row.get("market_id"),
                row.get("timeframe"),
                row.get("side"),
                row.get("trend"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
            if len(deduped) >= limit:
                break

        if include_fair_value:
            for row in deduped:
                market_id = row.get("market_id")
                if not market_id:
                    continue
                fv = db.get_latest_fair_value(market_id)
                if not fv:
                    continue
                row["p_model"] = fv.get("p_model")
                row["p_fair"] = fv.get("p_fair")
                row["p_mkt"] = fv.get("p_mkt")
                row["edge_bp"] = fv.get("edge_bp")
                row["arb_type"] = fv.get("arb_type")

        return {"opportunities": deduped}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/arbitrage/opportunities", summary="Arbitrage opportunities")
def get_arbitrage_opportunities(
    limit: int = Query(default=100, ge=1, le=1000, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    arb_type: str | None = Query(default=None, description="Optional arb_type filter"),
    status: str | None = Query(default=None, description="Optional status filter"),
    symbol: str | None = Query(default=None, description="Optional symbol filter"),
):
    try:
        rows = db.get_arb_opportunities(
            limit=limit,
            offset=offset,
            arb_type=arb_type,
            status=status,
            symbol=(symbol.upper() if symbol else None),
        )
        return {
            "opportunities": rows,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(rows),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/performance/arb-types", summary="Performance by arbitrage type")
def get_performance_by_arb_types():
    try:
        return {"arb_types": db.get_performance_by_arb_type()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/scalp/performance", summary="Scalp strategy performance")
def get_scalp_performance():
    try:
        return db.get_scalp_performance()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/perp-basis/latest", summary="Latest cross-venue perp basis snapshot")
def get_latest_perp_basis(
    symbol: str = Query(default="BTCUSDT", description="Trading symbol filter"),
):
    try:
        target_symbol = (symbol or "BTCUSDT").upper()
        row = db.get_latest_perp_basis(target_symbol)
        return {
            "symbol": target_symbol,
            "snapshot": row,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/perp-basis/history", summary="Recent cross-venue perp basis snapshots")
def get_perp_basis_history(
    symbol: str = Query(default="BTCUSDT", description="Trading symbol filter"),
    limit: int = Query(default=60, ge=1, le=500, description="Max rows to return"),
):
    try:
        target_symbol = (symbol or "BTCUSDT").upper()
        rows = db.get_perp_basis_history(target_symbol, limit=limit)
        return {
            "symbol": target_symbol,
            "snapshots": rows,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/diagnostics/calibration", summary="Signal calibration diagnostics")
def get_calibration_diagnostics(
    window_minutes: int = Query(default=120, ge=5, le=1440, description="Lookback window in minutes"),
):
    try:
        return db.get_calibration_diagnostics(window_minutes=window_minutes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/positions", summary="Open positions")
def get_positions():
    try:
        return {
            "positions": db.get_open_positions(),
            "total_exposure_usdc": db.get_total_open_exposure_usdc(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health/dependencies", summary="Dependency health status")
def get_dependency_health():
    signal = bot.latest_signal or {}
    signal_age_seconds = None
    if signal.get("timestamp"):
        signal_age_seconds = (
            datetime.utcnow() - datetime.fromisoformat(signal["timestamp"])
        ).total_seconds()
    return {
        "binance_thread_alive": (
            bot._binance_thread.is_alive()
            if bot._binance_thread is not None
            else False
        ),
        "binance_threads_alive": {
            sym: (bot._binance_thread.is_alive() if bot._binance_thread is not None else False)
            for sym in bot.supported_symbols
        },
        "polymarket_thread_alive": (
            bot._poly_thread.is_alive()
            if bot._poly_thread is not None
            else False
        ),
        "hyperliquid_thread_alive": (
            bot._hl_thread.is_alive()
            if getattr(bot, "_hl_thread", None) is not None
            else False
        ),
        "signal_age_seconds": signal_age_seconds,
    }


@app.get("/logs", summary="Application log entries")
def get_logs(
    limit: int = Query(default=100, ge=1, le=1000, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    Return the most recent application log entries.

    Query params:
      limit — max number of rows (1–1000, default 100)
    """
    try:
        rows = db.get_logs(limit=limit + offset)
        return {"logs": rows[offset:offset + limit]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/ta/alerts", summary="Technical analysis alerts")
def get_ta_alerts(
    limit: int = Query(default=50, ge=1, le=300, description="Max alerts to return"),
):
    try:
        return {"alerts": scanner.get_latest_alerts(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/ta/status", summary="Technical scanner status")
def get_ta_status():
    return {
        "enabled": scanner.enabled,
        "thread_alive": scanner.thread_alive,
        "last_scan_at": scanner.last_scan_at,
        "last_error": scanner.last_error,
        "pairs": scanner.pairs,
        "timeframes": scanner.timeframes,
        "exchanges": list(scanner._exchanges.keys()),
    }


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        cfg = json.load(f)
    api_cfg = cfg.get("api", {})
    uvicorn.run(
        "api:app",
        host=api_cfg.get("host", "0.0.0.0"),
        port=api_cfg.get("port", 8000),
        reload=False,
    )
