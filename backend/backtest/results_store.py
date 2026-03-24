"""Persistence layer for backtest runs and analytics artifacts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


class BacktestResultsStore:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent / "backtest_results.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_tables(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS backtest_runs (
            run_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            symbol TEXT NOT NULL,
            venue TEXT NOT NULL,
            market_type TEXT NOT NULL,
            start_ts TEXT NOT NULL,
            end_ts TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            strategy_scope TEXT,
            params_json TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS backtest_equity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            equity REAL NOT NULL,
            drawdown REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS backtest_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            symbol TEXT NOT NULL,
            market_id TEXT,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            pnl REAL,
            strategy TEXT,
            confidence REAL,
            edge REAL,
            hold_seconds INTEGER,
            venue TEXT,
            note TEXT,
            FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS backtest_metrics (
            run_id TEXT PRIMARY KEY,
            total_return REAL NOT NULL,
            annualized_return REAL NOT NULL,
            max_drawdown REAL NOT NULL,
            sharpe REAL NOT NULL,
            sortino REAL NOT NULL,
            calmar REAL NOT NULL,
            win_rate REAL NOT NULL,
            profit_factor REAL NOT NULL,
            expectancy REAL NOT NULL,
            trades_count INTEGER NOT NULL,
            avg_holding_period_seconds REAL NOT NULL,
            exposure_ratio REAL NOT NULL,
            gross_profit REAL NOT NULL,
            gross_loss REAL NOT NULL,
            fees_paid REAL NOT NULL,
            slippage_paid REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS backtest_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            payload_json TEXT,
            FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_ts ON backtest_trades(run_id, ts);
        CREATE INDEX IF NOT EXISTS idx_backtest_equity_run_ts ON backtest_equity(run_id, ts);
        CREATE INDEX IF NOT EXISTS idx_backtest_events_run_ts ON backtest_events(run_id, ts);
        """
        with self._connect() as conn:
            conn.executescript(ddl)

    def create_run(
        self,
        *,
        symbol: str,
        venue: str,
        market_type: str,
        start_ts: str,
        end_ts: str,
        timeframe: str,
        strategy_scope: str,
        params: dict,
    ) -> str:
        run_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO backtest_runs (run_id, status, symbol, venue, market_type, start_ts, end_ts, timeframe, strategy_scope, params_json, created_at) "
                "VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    symbol,
                    venue,
                    market_type,
                    start_ts,
                    end_ts,
                    timeframe,
                    strategy_scope,
                    json.dumps(params),
                    now,
                ),
            )
        return run_id

    def mark_started(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtest_runs SET status='running', started_at=? WHERE run_id=?",
                (datetime.utcnow().isoformat(), run_id),
            )

    def mark_completed(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtest_runs SET status='completed', completed_at=? WHERE run_id=?",
                (datetime.utcnow().isoformat(), run_id),
            )

    def mark_failed(self, run_id: str, error_message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtest_runs SET status='failed', completed_at=?, error_message=? WHERE run_id=?",
                (datetime.utcnow().isoformat(), str(error_message)[:3000], run_id),
            )

    def update_run_status(self, run_id: str, status: str, error_message: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        terminal = status in {"completed", "failed", "cancelled"}
        completed_at = now if terminal else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtest_runs SET status=?, completed_at=COALESCE(?, completed_at), error_message=COALESCE(?, error_message) WHERE run_id=?",
                (status, completed_at, error_message, run_id),
            )

    def append_event(self, run_id: str, level: str, message: str, payload: dict | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO backtest_events (run_id, ts, level, message, payload_json) VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    datetime.utcnow().isoformat(),
                    level.upper(),
                    message,
                    json.dumps(payload or {}),
                ),
            )

    def append_equity(self, run_id: str, ts: str, equity: float, drawdown: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO backtest_equity (run_id, ts, equity, drawdown) VALUES (?, ?, ?, ?)",
                (run_id, ts, float(equity), float(drawdown)),
            )

    def append_trade(self, run_id: str, trade: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO backtest_trades "
                "(run_id, ts, symbol, market_id, side, qty, entry_price, exit_price, pnl, strategy, confidence, edge, hold_seconds, venue, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    str(trade.get("ts") or datetime.utcnow().isoformat()),
                    str(trade.get("symbol") or ""),
                    str(trade.get("market_id") or "") if trade.get("market_id") is not None else None,
                    str(trade.get("side") or ""),
                    float(trade.get("qty") or 0.0),
                    float(trade.get("entry_price") or 0.0),
                    float(trade.get("exit_price")) if trade.get("exit_price") is not None else None,
                    float(trade.get("pnl")) if trade.get("pnl") is not None else None,
                    str(trade.get("strategy") or ""),
                    float(trade.get("confidence")) if trade.get("confidence") is not None else None,
                    float(trade.get("edge")) if trade.get("edge") is not None else None,
                    int(trade.get("hold_seconds") or 0),
                    str(trade.get("venue") or ""),
                    str(trade.get("note") or ""),
                ),
            )

    def upsert_metrics(self, run_id: str, metrics: dict) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO backtest_metrics "
                "(run_id, total_return, annualized_return, max_drawdown, sharpe, sortino, calmar, win_rate, profit_factor, expectancy, trades_count, avg_holding_period_seconds, exposure_ratio, gross_profit, gross_loss, fees_paid, slippage_paid, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET "
                "total_return=excluded.total_return, annualized_return=excluded.annualized_return, max_drawdown=excluded.max_drawdown, sharpe=excluded.sharpe, sortino=excluded.sortino, calmar=excluded.calmar, "
                "win_rate=excluded.win_rate, profit_factor=excluded.profit_factor, expectancy=excluded.expectancy, trades_count=excluded.trades_count, avg_holding_period_seconds=excluded.avg_holding_period_seconds, "
                "exposure_ratio=excluded.exposure_ratio, gross_profit=excluded.gross_profit, gross_loss=excluded.gross_loss, fees_paid=excluded.fees_paid, slippage_paid=excluded.slippage_paid, created_at=excluded.created_at",
                (
                    run_id,
                    float(metrics.get("total_return") or 0.0),
                    float(metrics.get("annualized_return") or 0.0),
                    float(metrics.get("max_drawdown") or 0.0),
                    float(metrics.get("sharpe") or 0.0),
                    float(metrics.get("sortino") or 0.0),
                    float(metrics.get("calmar") or 0.0),
                    float(metrics.get("win_rate") or 0.0),
                    float(metrics.get("profit_factor") or 0.0),
                    float(metrics.get("expectancy") or 0.0),
                    int(metrics.get("trades_count") or 0),
                    float(metrics.get("avg_holding_period_seconds") or 0.0),
                    float(metrics.get("exposure_ratio") or 0.0),
                    float(metrics.get("gross_profit") or 0.0),
                    float(metrics.get("gross_loss") or 0.0),
                    float(metrics.get("fees_paid") or 0.0),
                    float(metrics.get("slippage_paid") or 0.0),
                    now,
                ),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM backtest_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["params"] = json.loads(payload.pop("params_json") or "{}")
        return payload

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (int(limit), int(offset)),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["params"] = json.loads(item.pop("params_json") or "{}")
            out.append(item)
        return out

    def get_metrics(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM backtest_metrics WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def get_trades(self, run_id: str, limit: int = 2000) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backtest_trades WHERE run_id=? ORDER BY ts ASC LIMIT ?",
                (run_id, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_equity_curve(self, run_id: str, limit: int = 10000) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, equity, drawdown FROM backtest_equity WHERE run_id=? ORDER BY ts ASC LIMIT ?",
                (run_id, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_events(self, run_id: str, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, level, message, payload_json FROM backtest_events WHERE run_id=? ORDER BY ts ASC LIMIT ?",
                (run_id, int(limit)),
            ).fetchall()

        out: list[dict] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
            out.append(item)
        return out

    def get_full_report(self, run_id: str) -> dict | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        equity_rows = self.get_equity_curve(run_id)
        equity_curve = [
            {
                "timestamp": str(row.get("ts") or ""),
                "value": float(row.get("equity") or 0.0),
            }
            for row in equity_rows
        ]
        drawdown_curve = [
            {
                "timestamp": str(row.get("ts") or ""),
                "drawdown_pct": float(row.get("drawdown") or 0.0) * 100.0,
            }
            for row in equity_rows
        ]
        return {
            "run": run,
            "metrics": self.get_metrics(run_id),
            "equity_curve": equity_curve,
            "drawdown_curve": drawdown_curve,
            "trades": self.get_trades(run_id),
            "events": self.get_events(run_id),
        }
