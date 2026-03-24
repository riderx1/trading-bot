"""
db.py - SQLite database layer for the trading bot.

Tables:
  markets  - Polymarket YES/NO price snapshots
  trades   - Executed (paper or live) trade records
  signals  - External trend signals (e.g. Binance BTC trend)
  log      - Application log messages

All methods open a short-lived connection so they are safe to call from
multiple threads (SQLite WAL mode handles concurrent writers).
"""

import json
import logging
import math
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_config() -> dict:
    """Read config.json from the same directory as this module."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


class Database:
    """
    Manages a single SQLite file for the trading bot.

    Provides insert/fetch helpers for the four core tables:
      markets, trades, signals, log.

    Usage:
        db = Database()        # picks up path from config.json
        db = Database("my.db") # explicit path
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            cfg = _load_config()
            db_path = cfg["database"]["path"]
        self.db_path = self._resolve_db_path(db_path)
        self._init_tables()

    @staticmethod
    def _resolve_db_path(db_path: str) -> Path:
        candidate = Path(db_path)
        if candidate.is_absolute():
            return candidate
        return Path(__file__).parent / candidate

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl_type: str):
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row["name"] for row in cols}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")

    def _run_migrations(self, conn: sqlite3.Connection):
        # Add fields introduced after initial schema creation.
        self._ensure_column(conn, "signals", "strategy", "TEXT")
        self._ensure_column(conn, "signals", "timeframe", "TEXT")
        self._ensure_column(conn, "signals", "signal_strength", "TEXT")
        self._ensure_column(conn, "signals", "reasoning", "TEXT")
        self._ensure_column(conn, "signals", "move_pct", "REAL")
        self._ensure_column(conn, "signals", "regime", "TEXT")
        self._ensure_column(conn, "signals", "symbol", "TEXT")
        self._ensure_column(conn, "opportunities", "strategy", "TEXT")
        self._ensure_column(conn, "opportunities", "symbol", "TEXT")
        self._ensure_column(conn, "trades", "reason_code", "TEXT")

    def _init_tables(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS markets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_id TEXT NOT NULL,
            market_name TEXT NOT NULL,
            yes_price   REAL NOT NULL,
            no_price    REAL NOT NULL,
            yes_ask     REAL,
            no_ask      REAL,
            spread_bps  REAL,
            liquidity   REAL,
            end_date    TEXT,
            fetched_at  TEXT,
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_key           TEXT UNIQUE,
            market_row_id       INTEGER,
            market_id           TEXT NOT NULL,
            market_name         TEXT NOT NULL,
            type                TEXT NOT NULL,
            price               REAL NOT NULL,
            quantity            REAL NOT NULL,
            notional            REAL NOT NULL,
            signal_sequence_id  INTEGER,
            reason_code         TEXT,
            timestamp           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id   TEXT NOT NULL,
            market_name TEXT NOT NULL,
            side        TEXT NOT NULL,
            quantity    REAL NOT NULL,
            avg_entry   REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'open',
            opened_at   TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            closed_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS signal_sequences (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL,
            strategy    TEXT,
            regime      TEXT,
            consensus   TEXT NOT NULL,
            confidence  REAL NOT NULL,
            signal_strength TEXT,
            reasoning   TEXT,
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sequence_id     INTEGER,
            source          TEXT NOT NULL,
            strategy        TEXT,
            timeframe       TEXT,
            trend           TEXT NOT NULL,
            confidence      REAL,
            signal_strength TEXT,
            reasoning       TEXT,
            move_pct        REAL,
            regime          TEXT,
            value           REAL,
            timestamp       TEXT NOT NULL,
            symbol          TEXT
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_key     TEXT UNIQUE,
            market_id           TEXT NOT NULL,
            market_name         TEXT NOT NULL,
            signal_sequence_id  INTEGER,
            strategy            TEXT,
            timeframe           TEXT,
            trend               TEXT NOT NULL,
            confidence          REAL NOT NULL,
            signal_strength     TEXT,
            side                TEXT NOT NULL,
            yes_price           REAL,
            no_price            REAL,
            combined_price      REAL,
            gap_to_parity       REAL,
            edge                REAL,
            signal_threshold    REAL,
            reason_code         TEXT,
            reasoning           TEXT,
            timestamp           TEXT NOT NULL,
            symbol              TEXT
        );

        CREATE TABLE IF NOT EXISTS trades_simulated (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol              TEXT NOT NULL,
            strategy            TEXT NOT NULL,
            entry_price         REAL NOT NULL,
            exit_price          REAL NOT NULL,
            direction           INTEGER NOT NULL,
            pnl                 REAL NOT NULL,
            duration_seconds    INTEGER NOT NULL,
            duration            INTEGER,
            signal_strength     TEXT,
            regime              TEXT,
            timeframe           TEXT,
            entry_timestamp     TEXT,
            exit_timestamp      TEXT,
            timestamp           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS strategy_performance (
            strategy            TEXT PRIMARY KEY,
            trades              INTEGER NOT NULL DEFAULT 0,
            win_rate            REAL NOT NULL DEFAULT 0,
            avg_pnl             REAL NOT NULL DEFAULT 0,
            last_24h_pnl        REAL NOT NULL DEFAULT 0,
            score               REAL NOT NULL DEFAULT 0,
            updated_at          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bot_state (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            message     TEXT NOT NULL,
            level       TEXT NOT NULL,
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market_fair_values (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id           TEXT NOT NULL,
            market_name         TEXT,
            p_model             REAL NOT NULL,
            p_fair              REAL NOT NULL,
            p_mkt               REAL NOT NULL,
            edge_bp             INTEGER NOT NULL,
            arb_type            TEXT NOT NULL,
            symbol              TEXT,
            signal_sequence_id  INTEGER,
            timestamp           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id           TEXT NOT NULL,
            market_name         TEXT,
            arb_type            TEXT NOT NULL,
            p_fair              REAL,
            p_mkt               REAL,
            edge_bp             INTEGER,
            strategy            TEXT,
            trade_id            INTEGER,
            realized_pnl        REAL,
            status              TEXT NOT NULL DEFAULT 'open',
            why                 TEXT,
            symbol              TEXT,
            signal_sequence_id  INTEGER,
            timestamp           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS perp_basis_snapshots (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol                TEXT NOT NULL,
            binance_spot_price    REAL,
            binance_perp_price    REAL,
            binance_funding_rate  REAL,
            binance_basis_pct     REAL,
            hl_perp_price         REAL,
            hl_funding_rate       REAL,
            hl_open_interest      REAL,
            basis_diff            REAL,
            funding_spread        REAL,
            timestamp             TEXT NOT NULL
        );
        """

        with self._connect() as conn:
            conn.executescript(ddl)
            self._run_migrations(conn)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_trade_key ON trades(trade_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_open_market ON positions(market_id, side, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_sequence ON signals(sequence_id, timeframe)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_opportunities_recent ON opportunities(timestamp DESC)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunities_key ON opportunities(opportunity_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_simulated_symbol ON trades_simulated(symbol, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_simulated_strategy ON trades_simulated(strategy, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mfv_market ON market_fair_values(market_id, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_arb_opps_recent ON arbitrage_opportunities(timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_arb_opps_type ON arbitrage_opportunities(arb_type, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_perp_basis_symbol ON perp_basis_snapshots(symbol, timestamp DESC)")

    # ── Markets ─────────────────────────────────────────────────────────────────

    def insert_market(
        self,
        condition_id: str,
        market_name: str,
        yes_price: float,
        no_price: float,
        yes_ask: float,
        no_ask: float,
        spread_bps: float,
        liquidity: float,
        end_date: str | None,
        fetched_at: str,
    ) -> int:
        """
        Store a YES/NO price snapshot for a market.

        Returns:
            int: The auto-generated row id.
        """
        ts = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO markets (condition_id, market_name, yes_price, no_price, yes_ask, no_ask, spread_bps, liquidity, end_date, fetched_at, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    condition_id,
                    market_name,
                    yes_price,
                    no_price,
                    yes_ask,
                    no_ask,
                    spread_bps,
                    liquidity,
                    end_date,
                    fetched_at,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_latest_markets(self, limit: int = 50) -> list[dict]:
        """Return the `limit` most-recent market rows, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM markets ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Trades ──────────────────────────────────────────────────────────────────

    def _update_position_from_trade_conn(
        self,
        conn: sqlite3.Connection,
        market_id: str,
        market_name: str,
        side: str,
        price: float,
        quantity: float,
    ):
        now = datetime.utcnow().isoformat()
        row = conn.execute(
            "SELECT id, quantity, avg_entry FROM positions WHERE market_id=? AND side=? AND status='open' ORDER BY id DESC LIMIT 1",
            (market_id, side),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO positions (market_id, market_name, side, quantity, avg_entry, status, opened_at, updated_at) VALUES (?, ?, ?, ?, ?, 'open', ?, ?)",
                (market_id, market_name, side, quantity, price, now, now),
            )
            return

        new_qty = float(row["quantity"]) + quantity
        old_notional = float(row["quantity"]) * float(row["avg_entry"])
        new_avg = (old_notional + (quantity * price)) / new_qty
        conn.execute(
            "UPDATE positions SET quantity=?, avg_entry=?, updated_at=? WHERE id=?",
            (new_qty, new_avg, now, row["id"]),
        )

    def has_recent_trade(
        self, market_id: str, trade_type: str, within_seconds: int
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT timestamp FROM trades WHERE market_id=? AND type=? ORDER BY id DESC LIMIT 1",
                (market_id, trade_type),
            ).fetchone()
        if row is None:
            return False
        last = datetime.fromisoformat(row["timestamp"])
        age = (datetime.utcnow() - last).total_seconds()
        return age < within_seconds

    def insert_trade_if_not_exists(
        self,
        trade_key: str,
        market_row_id: int,
        market_id: str,
        market_name: str,
        trade_type: str,
        price: float,
        quantity: float,
        signal_sequence_id: int,
        reason_code: str,
    ) -> tuple[bool, int | None]:
        ts = datetime.utcnow().isoformat()
        notional = price * quantity
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO trades (trade_key, market_row_id, market_id, market_name, type, price, quantity, notional, signal_sequence_id, reason_code, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trade_key,
                    market_row_id,
                    market_id,
                    market_name,
                    trade_type,
                    price,
                    quantity,
                    notional,
                    signal_sequence_id,
                    reason_code,
                    ts,
                ),
            )
            if cur.rowcount == 0:
                return False, None

            trade_id = cur.lastrowid
            self._update_position_from_trade_conn(
                conn, market_id, market_name, trade_type, price, quantity
            )
            return True, trade_id

    def get_trades(self, limit: int = 50) -> list[dict]:
        """Return the `limit` most-recent trade rows, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_open_positions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status='open' ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_total_open_exposure_usdc(self) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(quantity * avg_entry), 0) AS exposure FROM positions WHERE status='open'"
            ).fetchone()
        return float(row["exposure"]) if row else 0.0

    def get_market_open_exposure_usdc(self, market_id: str) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(quantity * avg_entry), 0) AS exposure FROM positions WHERE status='open' AND market_id=?",
                (market_id,),
            ).fetchone()
        return float(row["exposure"]) if row else 0.0

    def get_cluster_open_exposure_usdc(self, cluster: str) -> float:
        if cluster == "BTC":
            where = "(LOWER(market_name) LIKE '%bitcoin%' OR LOWER(market_name) LIKE '%btc%')"
        else:
            where = "NOT (LOWER(market_name) LIKE '%bitcoin%' OR LOWER(market_name) LIKE '%btc%')"

        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COALESCE(SUM(quantity * avg_entry), 0) AS exposure FROM positions WHERE status='open' AND {where}"
            ).fetchone()
        return float(row["exposure"]) if row else 0.0

    def insert_signal_sequence(
        self,
        symbol: str,
        consensus: str,
        confidence: float,
        timestamp: str,
        signal_strength: str | None = None,
        reasoning: str | None = None,
        strategy: str | None = None,
        regime: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO signal_sequences (symbol, strategy, regime, consensus, confidence, signal_strength, reasoning, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (symbol, strategy, regime, consensus, confidence, signal_strength, reasoning, timestamp),
            )
            return cur.lastrowid

    def get_latest_signal_sequence_id(self) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM signal_sequences ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return int(row["id"]) if row else None

    # ── Signals ─────────────────────────────────────────────────────────────────

    def insert_signal(
        self,
        source: str,
        trend: str,
        value: float | None = None,
        sequence_id: int | None = None,
        timeframe: str | None = None,
        confidence: float | None = None,
        signal_strength: str | None = None,
        reasoning: str | None = None,
        move_pct: float | None = None,
        timestamp: str | None = None,
        symbol: str | None = None,
        strategy: str | None = None,
        regime: str | None = None,
    ) -> int:
        """
        Store a trading signal.

        Args:
            source: Signal origin, e.g. 'binance'.
            trend:  'bullish', 'bearish', or 'neutral'.
            value:  Optional numeric value (e.g. raw BTC price).
            symbol: Trading pair, e.g. 'BTCUSDT'.

        Returns:
            int: The auto-generated row id.
        """
        ts = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO signals (sequence_id, source, strategy, timeframe, trend, confidence, signal_strength, reasoning, move_pct, regime, value, timestamp, symbol)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sequence_id,
                    source,
                    strategy,
                    timeframe,
                    trend,
                    confidence,
                    signal_strength,
                    reasoning,
                    move_pct,
                    regime,
                    value,
                    ts,
                    symbol,
                ),
            )
            return cur.lastrowid

    def set_bot_state(self, key: str, value: str):
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bot_state (key, value, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now),
            )

    def get_bot_state(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM bot_state WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return default
        return row["value"]

    def get_latest_signals(self, limit: int = 20, symbol: str | None = None) -> list[dict]:
        """Return the `limit` most-recent signal rows, newest first. Optionally filter by symbol."""
        with self._connect() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM signals WHERE symbol=? ORDER BY id DESC LIMIT ?",
                    (symbol, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    def insert_opportunity_if_not_exists(
        self,
        opportunity_key: str,
        market_id: str,
        market_name: str,
        signal_sequence_id: int,
        timeframe: str,
        trend: str,
        confidence: float,
        signal_strength: str,
        side: str,
        yes_price: float,
        no_price: float,
        combined_price: float,
        gap_to_parity: float,
        edge: float,
        signal_threshold: float,
        reason_code: str,
        reasoning: str,
        timestamp: str | None = None,
        symbol: str | None = None,
        strategy: str | None = None,
    ) -> tuple[bool, int | None]:
        ts = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO opportunities (opportunity_key, market_id, market_name, signal_sequence_id, strategy, timeframe, trend, confidence, signal_strength, side, yes_price, no_price, combined_price, gap_to_parity, edge, signal_threshold, reason_code, reasoning, timestamp, symbol)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    opportunity_key,
                    market_id,
                    market_name,
                    signal_sequence_id,
                    strategy,
                    timeframe,
                    trend,
                    confidence,
                    signal_strength,
                    side,
                    yes_price,
                    no_price,
                    combined_price,
                    gap_to_parity,
                    edge,
                    signal_threshold,
                    reason_code,
                    reasoning,
                    ts,
                    symbol,
                ),
            )
            if cur.rowcount == 0:
                return False, None
            return True, cur.lastrowid

    def get_opportunities(self, limit: int = 50, symbol: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM opportunities WHERE symbol=? ORDER BY id DESC LIMIT ?",
                    (symbol, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM opportunities ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ── Simulation + performance ──────────────────────────────────────────────

    def insert_simulated_trade(
        self,
        symbol: str,
        strategy: str,
        entry_price: float,
        exit_price: float,
        direction: int,
        pnl: float,
        duration_seconds: int,
        signal_strength: str,
        regime: str,
        timeframe: str | None = None,
        entry_timestamp: str | None = None,
        exit_timestamp: str | None = None,
        timestamp: str | None = None,
    ) -> int:
        ts = timestamp or datetime.utcnow().isoformat()
        entry_ts = entry_timestamp or ts
        exit_ts = exit_timestamp or ts
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO trades_simulated (symbol, strategy, entry_price, exit_price, direction, pnl, duration_seconds, duration, signal_strength, regime, timeframe, entry_timestamp, exit_timestamp, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    symbol,
                    strategy,
                    float(entry_price),
                    float(exit_price),
                    int(direction),
                    float(pnl),
                    int(duration_seconds),
                    int(duration_seconds),
                    signal_strength,
                    regime,
                    timeframe,
                    entry_ts,
                    exit_ts,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_historical_win_rate(
        self,
        symbol: str,
        timeframe: str,
        strategy: str,
        signal_strength: str,
        regime: str,
        min_samples: int = 25,
    ) -> dict:
        """Return historical directional win-rate for context with sparse-data fallback."""

        def _query(filters: list[tuple[str, str]]) -> tuple[float | None, int]:
            clauses = ["trend IN ('bullish','bearish')", "move_pct IS NOT NULL"]
            params: list[str] = []
            for field, value in filters:
                clauses.append(f"{field}=?")
                params.append(value)

            where = " AND ".join(clauses)
            sql = (
                "SELECT "
                "COUNT(*) AS n, "
                "SUM(CASE WHEN (trend='bullish' AND move_pct > 0) OR (trend='bearish' AND move_pct < 0) THEN 1 ELSE 0 END) AS wins "
                f"FROM signals WHERE {where}"
            )
            with self._connect() as conn:
                row = conn.execute(sql, tuple(params)).fetchone()
            n = int(row["n"] or 0) if row else 0
            wins = int(row["wins"] or 0) if row else 0
            if n <= 0:
                return None, 0
            return float(wins / n), n

        fallback_queries = [
            ([
                ("symbol", symbol),
                ("timeframe", timeframe),
                ("strategy", strategy),
                ("signal_strength", signal_strength),
                ("regime", regime),
            ], "full_context"),
            ([
                ("symbol", symbol),
                ("timeframe", timeframe),
                ("strategy", strategy),
                ("signal_strength", signal_strength),
            ], "no_regime"),
            ([
                ("symbol", symbol),
                ("timeframe", timeframe),
                ("strategy", strategy),
            ], "symbol_tf_strategy"),
            ([
                ("symbol", symbol),
                ("timeframe", timeframe),
            ], "symbol_timeframe"),
            ([
                ("symbol", symbol),
            ], "symbol_global"),
            ([], "global"),
        ]

        selected_rate = 0.52
        selected_n = 0
        selected_source = "default"

        for query_filters, source in fallback_queries:
            rate, sample_n = _query(query_filters)
            if rate is None:
                continue
            selected_rate = float(rate)
            selected_n = int(sample_n)
            selected_source = source
            if sample_n >= min_samples or source == "global":
                break

        return {
            "win_rate": max(0.0, min(1.0, selected_rate)),
            "sample_size": selected_n,
            "source": selected_source,
        }

    def get_simulated_trades(
        self,
        limit: int = 200,
        symbol: str | None = None,
        strategy: str | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM trades_simulated"
        params: list = []
        filters = []
        if symbol:
            filters.append("symbol=?")
            params.append(symbol)
        if strategy:
            filters.append("strategy=?")
            params.append(strategy)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def _calculate_drawdown(self, pnls: list[float]) -> float:
        if not pnls:
            return 0.0
        peak = 0.0
        equity = 0.0
        max_dd = 0.0
        for pnl in pnls:
            equity += float(pnl)
            peak = max(peak, equity)
            drawdown = peak - equity
            max_dd = max(max_dd, drawdown)
        return float(max_dd)

    def _calculate_sharpe(self, pnls: list[float]) -> float:
        if len(pnls) < 2:
            return 0.0
        mean = sum(pnls) / len(pnls)
        variance = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
        stdev = math.sqrt(variance)
        if stdev == 0:
            return 0.0
        return float(mean / stdev)

    def _aggregate_metrics(self, rows: list[dict]) -> dict:
        if not rows:
            return {
                "trade_count": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "edge_per_setup": {},
            }

        pnls = [float(row.get("pnl") or 0.0) for row in rows]
        wins = sum(1 for pnl in pnls if pnl > 0)

        by_strength: dict[str, list[float]] = {}
        for row in rows:
            key = str(row.get("signal_strength") or "unknown").lower()
            by_strength.setdefault(key, []).append(float(row.get("pnl") or 0.0))

        edge_per_setup = {
            strength: (sum(values) / len(values)) if values else 0.0
            for strength, values in by_strength.items()
        }

        return {
            "trade_count": len(rows),
            "win_rate": wins / len(rows),
            "avg_pnl": sum(pnls) / len(rows),
            "total_pnl": sum(pnls),
            "max_drawdown": self._calculate_drawdown(pnls),
            "sharpe_ratio": self._calculate_sharpe(pnls),
            "edge_per_setup": edge_per_setup,
        }

    def get_performance_summary(self) -> dict:
        rows = self.get_simulated_trades(limit=5000)
        metrics = self._aggregate_metrics(rows)
        metrics["as_of"] = datetime.utcnow().isoformat()
        return metrics

    def get_recent_simulated_trades(self, limit: int = 50) -> list[dict]:
        return self.get_simulated_trades(limit=limit)

    def clear_simulated_trades(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM trades_simulated")

    def clear_strategy_performance(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM strategy_performance")

    def get_performance_by_strategy(self) -> list[dict]:
        rows = self.get_simulated_trades(limit=5000)
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("strategy") or "unknown"), []).append(row)

        results = []
        for strategy, strategy_rows in grouped.items():
            metrics = self._aggregate_metrics(strategy_rows)
            metrics["strategy"] = strategy
            results.append(metrics)
        return sorted(results, key=lambda item: item["total_pnl"], reverse=True)

    def get_performance_by_symbol(self) -> list[dict]:
        rows = self.get_simulated_trades(limit=5000)
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("symbol") or "UNKNOWN"), []).append(row)

        results = []
        for symbol, symbol_rows in grouped.items():
            metrics = self._aggregate_metrics(symbol_rows)
            metrics["symbol"] = symbol
            results.append(metrics)
        return sorted(results, key=lambda item: item["total_pnl"], reverse=True)

    def get_scalp_performance(self) -> dict:
        rows = self.get_simulated_trades(limit=10000)
        scalp_rows = [
            row
            for row in rows
            if str(row.get("timeframe") or "").lower() == "scalp"
            or "scalp" in str(row.get("strategy") or "").lower()
        ]
        overall = self._aggregate_metrics(scalp_rows)

        venue_map: dict[str, list[dict]] = {"polymarket": [], "hyperliquid": [], "unknown": []}
        asset_map: dict[str, list[dict]] = {}

        for row in scalp_rows:
            strategy = str(row.get("strategy") or "").lower()
            venue = "unknown"
            if "polymarket" in strategy:
                venue = "polymarket"
            elif "hyperliquid" in strategy or "hl" in strategy:
                venue = "hyperliquid"
            venue_map.setdefault(venue, []).append(row)

            symbol = str(row.get("symbol") or "UNKNOWN")
            asset_map.setdefault(symbol, []).append(row)

        by_venue = {
            venue: self._aggregate_metrics(venue_rows)
            for venue, venue_rows in venue_map.items()
        }
        by_asset = {
            symbol: self._aggregate_metrics(symbol_rows)
            for symbol, symbol_rows in asset_map.items()
        }

        return {
            "overall": overall,
            "by_venue": by_venue,
            "by_asset": by_asset,
            "as_of": datetime.utcnow().isoformat(),
        }

    def recompute_strategy_performance(self) -> list[dict]:
        strategies = self.get_performance_by_strategy()
        now = datetime.utcnow().isoformat()

        cutoff = datetime.utcnow().timestamp() - (24 * 60 * 60)
        recent_by_strategy: dict[str, float] = {}
        for row in self.get_simulated_trades(limit=5000):
            strategy = str(row.get("strategy") or "unknown")
            ts = row.get("timestamp")
            try:
                row_ts = datetime.fromisoformat(ts).timestamp() if ts else 0
            except ValueError:
                row_ts = 0
            if row_ts >= cutoff:
                recent_by_strategy[strategy] = recent_by_strategy.get(strategy, 0.0) + float(row.get("pnl") or 0.0)

        scored = []
        with self._connect() as conn:
            for item in strategies:
                strategy = item["strategy"]
                win_rate = float(item["win_rate"])
                avg_pnl = float(item["avg_pnl"])
                last_24h_pnl = float(recent_by_strategy.get(strategy, 0.0))
                recency_weight = 1.0 + min(0.5, max(-0.5, last_24h_pnl / 50.0))
                score = win_rate * avg_pnl * recency_weight
                conn.execute(
                    "INSERT INTO strategy_performance (strategy, trades, win_rate, avg_pnl, last_24h_pnl, score, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(strategy) DO UPDATE SET trades=excluded.trades, win_rate=excluded.win_rate, avg_pnl=excluded.avg_pnl, last_24h_pnl=excluded.last_24h_pnl, score=excluded.score, updated_at=excluded.updated_at",
                    (
                        strategy,
                        int(item["trade_count"]),
                        win_rate,
                        avg_pnl,
                        last_24h_pnl,
                        score,
                        now,
                    ),
                )
                scored.append(
                    {
                        "strategy": strategy,
                        "trades": int(item["trade_count"]),
                        "win_rate": win_rate,
                        "avg_pnl": avg_pnl,
                        "last_24h_pnl": last_24h_pnl,
                        "score": score,
                    }
                )

        return sorted(scored, key=lambda row: row["score"], reverse=True)

    def get_strategy_rankings(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT strategy, trades, win_rate, avg_pnl, last_24h_pnl, score, updated_at "
                "FROM strategy_performance ORDER BY score DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    # ── History ───────────────────────────────────────────────────────────────

    def get_history_signals(
        self,
        limit: int = 200,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str | None = None,
        start_ts: str | None = None,
        end_ts: str | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM signals"
        filters: list[str] = []
        params: list = []

        if symbol:
            filters.append("symbol=?")
            params.append(symbol)
        if timeframe and timeframe != "ALL":
            filters.append("timeframe=?")
            params.append(timeframe)
        if strategy and strategy != "ALL":
            filters.append("strategy=?")
            params.append(strategy)
        if start_ts:
            filters.append("timestamp>=?")
            params.append(start_ts)
        if end_ts:
            filters.append("timestamp<=?")
            params.append(end_ts)

        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_history_opportunities(
        self,
        limit: int = 200,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str | None = None,
        start_ts: str | None = None,
        end_ts: str | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM opportunities"
        filters: list[str] = []
        params: list = []

        if symbol:
            filters.append("symbol=?")
            params.append(symbol)
        if timeframe and timeframe != "ALL":
            filters.append("timeframe=?")
            params.append(timeframe)
        if strategy and strategy != "ALL":
            filters.append("strategy=?")
            params.append(strategy)
        if start_ts:
            filters.append("timestamp>=?")
            params.append(start_ts)
        if end_ts:
            filters.append("timestamp<=?")
            params.append(end_ts)

        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_history_trades(
        self,
        limit: int = 200,
        symbol: str | None = None,
        strategy: str | None = None,
        start_ts: str | None = None,
        end_ts: str | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM trades_simulated"
        filters: list[str] = []
        params: list = []

        if symbol:
            filters.append("symbol=?")
            params.append(symbol)
        if strategy and strategy != "ALL":
            filters.append("strategy=?")
            params.append(strategy)
        if start_ts:
            filters.append("timestamp>=?")
            params.append(start_ts)
        if end_ts:
            filters.append("timestamp<=?")
            params.append(end_ts)

        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    # ── Log ─────────────────────────────────────────────────────────────────────

    def insert_log(self, message: str, level: str = "INFO"):
        """
        Persist a log message to the database.

        Args:
            message: Human-readable log text.
            level:   Severity — 'INFO', 'WARNING', or 'ERROR'.
        """
        ts = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO log (message, level, timestamp) VALUES (?, ?, ?)",
                (message, level, ts),
            )

    def get_logs(self, limit: int = 100) -> list[dict]:
        """Return the `limit` most-recent log rows, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Fair value + arbitrage opportunities ─────────────────────────────────

    def insert_fair_value(
        self,
        market_id: str,
        market_name: str,
        p_model: float,
        p_fair: float,
        p_mkt: float,
        edge_bp: int,
        arb_type: str,
        symbol: str | None = None,
        signal_sequence_id: int | None = None,
        timestamp: str | None = None,
    ) -> int:
        """Persist one fair-value snapshot for a market."""
        ts = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO market_fair_values "
                "(market_id, market_name, p_model, p_fair, p_mkt, edge_bp, arb_type, symbol, signal_sequence_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (market_id, market_name, p_model, p_fair, p_mkt, edge_bp, arb_type, symbol, signal_sequence_id, ts),
            )
            return cur.lastrowid

    def get_latest_fair_value(self, market_id: str) -> dict | None:
        """Return the most recent fair-value row for a market, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_fair_values WHERE market_id=? ORDER BY id DESC LIMIT 1",
                (market_id,),
            ).fetchone()
        return dict(row) if row else None

    def insert_arb_opportunity(
        self,
        market_id: str,
        market_name: str,
        arb_type: str,
        p_fair: float,
        p_mkt: float,
        edge_bp: int,
        strategy: str | None = None,
        why: str | None = None,
        symbol: str | None = None,
        signal_sequence_id: int | None = None,
        status: str = "open",
        timestamp: str | None = None,
    ) -> int:
        """Persist one arbitrage opportunity record."""
        ts = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO arbitrage_opportunities "
                "(market_id, market_name, arb_type, p_fair, p_mkt, edge_bp, strategy, why, symbol, signal_sequence_id, status, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (market_id, market_name, arb_type, p_fair, p_mkt, edge_bp, strategy, why, symbol, signal_sequence_id, status, ts),
            )
            return cur.lastrowid

    def get_arb_opportunities(
        self,
        limit: int = 50,
        offset: int = 0,
        arb_type: str | None = None,
        status: str | None = None,
        symbol: str | None = None,
    ) -> list[dict]:
        """Return arbitrage opportunities with optional filters."""
        query = "SELECT * FROM arbitrage_opportunities"
        filters: list[str] = []
        params: list = []
        if arb_type:
            filters.append("arb_type=?")
            params.append(arb_type)
        if status:
            filters.append("status=?")
            params.append(status)
        if symbol:
            filters.append("symbol=?")
            params.append(symbol)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def get_performance_by_arb_type(self) -> list[dict]:
        """
        Aggregate arbitrage_opportunities by arb_type.

        Returns count, avg edge_bp, and latest timestamp per type.
        Since realized_pnl is only populated once outcomes are known
        (TODO: wire in outcome tracking), this is a proxy metric for now.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    arb_type,
                    COUNT(*) AS total,
                    AVG(edge_bp) AS avg_edge_bp,
                    MAX(edge_bp) AS max_edge_bp,
                    SUM(CASE WHEN status='executed' THEN 1 ELSE 0 END) AS executed,
                    AVG(CASE WHEN realized_pnl IS NOT NULL THEN realized_pnl ELSE NULL END) AS avg_realized_pnl,
                    MAX(timestamp) AS last_seen
                FROM arbitrage_opportunities
                GROUP BY arb_type
                ORDER BY total DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Perp basis / cross-venue funding ─────────────────────────────────────

    def insert_perp_basis(
        self,
        symbol: str,
        binance_spot_price: float | None,
        binance_perp_price: float | None,
        binance_funding_rate: float | None,
        hl_perp_price: float | None,
        hl_funding_rate: float | None,
        hl_open_interest: float | None,
    ) -> int:
        """
        Store a cross-venue perp basis snapshot.

        Computes basis_pct and funding_spread from the supplied values.
        basis_diff  = binance_perp - hl_perp  (USD)
        basis_pct   = (binance_perp - binance_spot) / binance_spot
        funding_spread = binance_funding_rate - hl_funding_rate
        """
        ts = datetime.utcnow().isoformat()
        spot = binance_spot_price or 0.0
        bin_perp = binance_perp_price or 0.0
        hl_perp = hl_perp_price or 0.0
        bin_fund = binance_funding_rate or 0.0
        hl_fund = hl_funding_rate or 0.0

        basis_pct = ((bin_perp - spot) / spot) if spot else 0.0
        basis_diff = bin_perp - hl_perp
        funding_spread = bin_fund - hl_fund

        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO perp_basis_snapshots "
                "(symbol, binance_spot_price, binance_perp_price, binance_funding_rate, "
                "binance_basis_pct, hl_perp_price, hl_funding_rate, hl_open_interest, "
                "basis_diff, funding_spread, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    symbol,
                    binance_spot_price,
                    binance_perp_price,
                    binance_funding_rate,
                    basis_pct,
                    hl_perp_price,
                    hl_funding_rate,
                    hl_open_interest,
                    basis_diff,
                    funding_spread,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_latest_perp_basis(self, symbol: str) -> dict | None:
        """Return the most-recent perp basis snapshot for a symbol."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM perp_basis_snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
        return dict(row) if row else None

    def get_perp_basis_history(
        self, symbol: str, limit: int = 120
    ) -> list[dict]:
        """Return recent perp basis snapshots for a symbol, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM perp_basis_snapshots WHERE symbol=? ORDER BY id DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        return [dict(r) for r in rows]
