"""Backtest data loading utilities with on-disk caching.

This module provides deterministic, cache-first historical loaders used by the
paper-only backtest runner. All returned rows are sorted by timestamp ascending
and intended to be consumed in forward-only order.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests


BINANCE_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "BTCUSDT": ["bitcoin", "btc"],
    "ETHUSDT": ["ethereum", "eth"],
    "SOLUSDT": ["solana", "sol"],
}


@dataclass(frozen=True)
class CandleRow:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MarketRow:
    timestamp: str
    market_id: str
    market_name: str
    yes_price: float
    no_price: float
    yes_ask: float | None
    no_ask: float | None
    spread_bps: float | None
    liquidity: float | None
    end_date: str | None


@dataclass(frozen=True)
class BasisRow:
    timestamp: str
    symbol: str
    binance_spot_price: float | None
    binance_perp_price: float | None
    hl_perp_price: float | None
    funding_spread: float | None


def _parse_iso_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_iso_utc(value: datetime) -> str:
    dt = value.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_window(start_ts: str, end_ts: str) -> tuple[datetime, datetime]:
    start_dt = _parse_iso_ts(start_ts)
    end_dt = _parse_iso_ts(end_ts)
    if end_dt <= start_dt:
        raise ValueError("end_ts must be greater than start_ts")
    return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc)


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out) or math.isinf(out):
        return default
    return out


class BacktestDataLoader:
    """Cache-first historical data loader for backtests."""

    def __init__(
        self,
        db,
        *,
        cache_dir: str | Path | None = None,
        binance_base_url: str = "https://api.binance.com",
        timeout_seconds: float = 20.0,
    ):
        self.db = db
        self.timeout_seconds = float(timeout_seconds)
        self.binance_base_url = binance_base_url.rstrip("/")
        default_cache = Path(__file__).resolve().parent / "cache"
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_binance_candles(
        self,
        *,
        symbol: str,
        interval: str,
        start_ts: str,
        end_ts: str,
        refresh: bool = False,
    ) -> list[CandleRow]:
        """Load Binance klines with file cache and deterministic ordering."""
        if interval not in BINANCE_INTERVAL_MS:
            raise ValueError(f"Unsupported interval '{interval}'")
        start_dt, end_dt = _normalize_window(start_ts, end_ts)
        normalized_symbol = symbol.upper()

        cache_path = self._cache_path(
            "binance",
            f"{normalized_symbol}_{interval}_{start_dt.strftime('%Y%m%d%H%M%S')}_{end_dt.strftime('%Y%m%d%H%M%S')}.csv",
        )
        if cache_path.exists() and not refresh:
            return self._read_candle_cache(cache_path)

        rows = self._fetch_binance_klines(
            symbol=normalized_symbol,
            interval=interval,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        self._write_candle_cache(cache_path, rows)
        return rows

    def load_polymarket_snapshots(
        self,
        *,
        symbol: str,
        start_ts: str,
        end_ts: str,
    ) -> list[MarketRow]:
        """Load market snapshots from local DB for a symbol and window."""
        start_dt, end_dt = _normalize_window(start_ts, end_ts)
        keywords = SYMBOL_KEYWORDS.get(symbol.upper(), [symbol.lower()])

        sql = (
            "SELECT condition_id, market_name, yes_price, no_price, yes_ask, no_ask, "
            "spread_bps, liquidity, end_date, timestamp "
            "FROM markets "
            "WHERE timestamp >= ? AND timestamp < ? "
            "ORDER BY timestamp ASC, id ASC"
        )

        with self.db._connect() as conn:  # noqa: SLF001
            raw = conn.execute(sql, (start_dt.isoformat(), end_dt.isoformat())).fetchall()

        filtered: list[MarketRow] = []
        for row in raw:
            name = str(row["market_name"] or "")
            lowered = name.lower()
            if not any(keyword in lowered for keyword in keywords):
                continue
            filtered.append(
                MarketRow(
                    timestamp=str(row["timestamp"]),
                    market_id=str(row["condition_id"]),
                    market_name=name,
                    yes_price=float(row["yes_price"]),
                    no_price=float(row["no_price"]),
                    yes_ask=_safe_float(row["yes_ask"]),
                    no_ask=_safe_float(row["no_ask"]),
                    spread_bps=_safe_float(row["spread_bps"]),
                    liquidity=_safe_float(row["liquidity"]),
                    end_date=str(row["end_date"]) if row["end_date"] else None,
                )
            )
        return filtered

    def load_perp_basis(
        self,
        *,
        symbol: str,
        start_ts: str,
        end_ts: str,
    ) -> list[BasisRow]:
        """Load historical perp basis context from local DB."""
        start_dt, end_dt = _normalize_window(start_ts, end_ts)
        sql = (
            "SELECT symbol, binance_spot_price, binance_perp_price, hl_perp_price, "
            "funding_spread, timestamp "
            "FROM perp_basis_snapshots "
            "WHERE symbol = ? AND timestamp >= ? AND timestamp < ? "
            "ORDER BY timestamp ASC, id ASC"
        )
        with self.db._connect() as conn:  # noqa: SLF001
            raw = conn.execute(
                sql,
                (symbol.upper(), start_dt.isoformat(), end_dt.isoformat()),
            ).fetchall()

        return [
            BasisRow(
                timestamp=str(row["timestamp"]),
                symbol=str(row["symbol"]),
                binance_spot_price=_safe_float(row["binance_spot_price"]),
                binance_perp_price=_safe_float(row["binance_perp_price"]),
                hl_perp_price=_safe_float(row["hl_perp_price"]),
                funding_spread=_safe_float(row["funding_spread"]),
            )
            for row in raw
        ]

    def history_up_to(
        self,
        rows: Iterable[CandleRow],
        *,
        at_ts: str,
        lookback: int,
    ) -> list[CandleRow]:
        """Return only candles with timestamp <= at_ts (no lookahead)."""
        bound = _parse_iso_ts(at_ts)
        eligible = [r for r in rows if _parse_iso_ts(r.timestamp) <= bound]
        if lookback <= 0:
            return eligible
        return eligible[-lookback:]

    def nearest_market_snapshot(
        self,
        rows: list[MarketRow],
        *,
        at_ts: str,
    ) -> list[MarketRow]:
        """Return latest snapshot per market_id with timestamp <= at_ts."""
        bound = _parse_iso_ts(at_ts)
        latest_by_market: dict[str, MarketRow] = {}
        for row in rows:
            row_dt = _parse_iso_ts(row.timestamp)
            if row_dt > bound:
                continue
            previous = latest_by_market.get(row.market_id)
            if previous is None or _parse_iso_ts(previous.timestamp) <= row_dt:
                latest_by_market[row.market_id] = row
        return list(latest_by_market.values())

    def _cache_path(self, namespace: str, filename: str) -> Path:
        bucket = self.cache_dir / namespace
        bucket.mkdir(parents=True, exist_ok=True)
        return bucket / filename

    def _read_candle_cache(self, path: Path) -> list[CandleRow]:
        rows: list[CandleRow] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    CandleRow(
                        timestamp=str(row["timestamp"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
        rows.sort(key=lambda r: r.timestamp)
        return rows

    def _write_candle_cache(self, path: Path, rows: list[CandleRow]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "timestamp": row.timestamp,
                        "open": row.open,
                        "high": row.high,
                        "low": row.low,
                        "close": row.close,
                        "volume": row.volume,
                    }
                )

    def _fetch_binance_klines(
        self,
        *,
        symbol: str,
        interval: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[CandleRow]:
        step_ms = BINANCE_INTERVAL_MS[interval]
        cursor = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        rows: list[CandleRow] = []

        while cursor < end_ms:
            url = f"{self.binance_base_url}/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": str(cursor),
                "endTime": str(end_ms),
                "limit": "1000",
            }
            response = requests.get(url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if not payload:
                break

            batch_count = 0
            for item in payload:
                open_time = int(item[0])
                close_time = open_time + step_ms
                if close_time > end_ms:
                    continue
                rows.append(
                    CandleRow(
                        timestamp=_to_iso_utc(datetime.fromtimestamp(open_time / 1000, tz=timezone.utc)),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                    )
                )
                batch_count += 1

            if batch_count == 0:
                break
            cursor = int(payload[-1][0]) + step_ms

        rows.sort(key=lambda r: r.timestamp)

        # De-duplicate by candle timestamp in case of API pagination overlap.
        deduped: dict[str, CandleRow] = {row.timestamp: row for row in rows}
        return list(sorted(deduped.values(), key=lambda r: r.timestamp))


def to_json_serializable_candles(rows: Iterable[CandleRow]) -> list[dict]:
    return [
        {
            "timestamp": row.timestamp,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in rows
    ]


def to_json_serializable_markets(rows: Iterable[MarketRow]) -> list[dict]:
    return [
        {
            "timestamp": row.timestamp,
            "market_id": row.market_id,
            "market_name": row.market_name,
            "yes_price": row.yes_price,
            "no_price": row.no_price,
            "yes_ask": row.yes_ask,
            "no_ask": row.no_ask,
            "spread_bps": row.spread_bps,
            "liquidity": row.liquidity,
            "end_date": row.end_date,
        }
        for row in rows
    ]


def to_json_serializable_basis(rows: Iterable[BasisRow]) -> list[dict]:
    return [
        {
            "timestamp": row.timestamp,
            "symbol": row.symbol,
            "binance_spot_price": row.binance_spot_price,
            "binance_perp_price": row.binance_perp_price,
            "hl_perp_price": row.hl_perp_price,
            "funding_spread": row.funding_spread,
        }
        for row in rows
    ]
