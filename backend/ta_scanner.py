"""Technical analysis scanner using CCXT + pandas-ta."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd
try:
    import pandas_ta as ta
except ImportError:  # pragma: no cover - runtime environment dependent
    ta = None

logger = logging.getLogger("TechnicalScanner")


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class TechnicalScanner:
    """Background TA scanner that emits non-trading alerts only."""

    def __init__(self, config: dict):
        scan_cfg = config.get("technical_scan", {})
        self.enabled = bool(scan_cfg.get("enabled", True))
        self.scan_interval_seconds = int(scan_cfg.get("scan_interval_seconds", 300))
        self.min_candles = int(scan_cfg.get("min_candles", 260))
        self.low_vol_atr_ratio = float(scan_cfg.get("low_vol_atr_ratio", 0.0035))

        base_watch = scan_cfg.get("watchlist", [])
        self.watchlist = [str(pair).upper() for pair in base_watch if str(pair).strip()]
        bases = ["BTC", "ETH", "SOL", *self.watchlist]
        self.pairs = sorted({f"{base}/USDT" for base in bases})

        self.timeframes = ["15m", "1h", "4h", "1d", "1w"]
        self.timeframe_labels = {
            "15m": "15m",
            "1h": "1H",
            "4h": "4H",
            "1d": "Daily",
            "1w": "Weekly",
        }
        self.exchange_ids = ["binance", "toobit", "hyperliquid"]

        self.latest_alerts: list[dict] = []
        self.last_scan_at: str | None = None
        self.last_error: str | None = None

        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        if ta is None:
            self.enabled = False
            self.last_error = (
                "pandas-ta is not available in this Python environment. "
                "Install dependencies from requirements.txt in a supported runtime."
            )
            self._exchanges = {}
            logger.warning(self.last_error)
            return

        self._exchanges = self._init_exchanges()

    def _init_exchanges(self) -> dict[str, ccxt.Exchange]:
        exchanges = {}
        for exchange_id in self.exchange_ids:
            exchange_cls = getattr(ccxt, exchange_id, None)
            if exchange_cls is None:
                logger.warning("CCXT exchange '%s' not found", exchange_id)
                continue
            try:
                options: dict = {"enableRateLimit": True}
                # Restrict Binance to spot markets only — avoids the
                # dapi.binance.com derivatives endpoint which may be
                # geo-blocked or unreachable on the host machine.
                if exchange_id == "binance":
                    options["options"] = {"defaultType": "spot"}
                ex = exchange_cls(options)
                ex.load_markets()
                exchanges[exchange_id] = ex
                logger.info("Initialized CCXT exchange: %s (%d markets)", exchange_id, len(ex.markets))
            except Exception as exc:
                logger.warning("Failed to initialize %s: %s", exchange_id, exc)
        return exchanges

    def start(self):
        if not self.enabled or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True, name="TechnicalScanner")
        self._thread.start()
        logger.info("Technical scanner started (interval=%ss)", self.scan_interval_seconds)

    def stop(self):
        self._running = False
        logger.info("Technical scanner stopped")

    @property
    def thread_alive(self) -> bool:
        return self._thread.is_alive() if self._thread is not None else False

    def get_latest_alerts(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self.latest_alerts[:limit])

    def _scan_loop(self):
        while self._running:
            started = _now_iso()
            try:
                alerts = self._scan_once()
                with self._lock:
                    self.latest_alerts = alerts
                    self.last_scan_at = started
                    self.last_error = None
                self._write_scan_log(started, alerts)
            except Exception as exc:
                self.last_error = str(exc)
                logger.error("Technical scan error: %s", exc)
            time.sleep(self.scan_interval_seconds)

    def _candidate_symbols(self, pair: str) -> list[str]:
        base = pair.split("/")[0]
        return [
            f"{base}/USDT",
            f"{base}/USDT:USDT",
            f"{base}/USD:USD",
            f"{base}/USD",
        ]

    def _resolve_symbol(self, exchange: ccxt.Exchange, pair: str) -> str | None:
        for candidate in self._candidate_symbols(pair):
            if candidate in exchange.markets:
                return candidate
        return None

    def _fetch_ohlcv_df(self, exchange: ccxt.Exchange, symbol: str, timeframe: str) -> pd.DataFrame | None:
        try:
            rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=self.min_candles)
            if not rows or len(rows) < 60:
                return None
            df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna().reset_index(drop=True)
            return df if len(df) >= 60 else None
        except Exception:
            return None

    def _funding_rate(self, exchange: ccxt.Exchange, symbol: str) -> float | None:
        if not exchange.has.get("fetchFundingRate"):
            return None
        try:
            rate = exchange.fetch_funding_rate(symbol)
            return _safe_float(rate.get("fundingRate"), default=np.nan)
        except Exception:
            return None

    def _indicator_hits(self, df: pd.DataFrame, funding_rate: float | None) -> tuple[list[str], dict]:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        hits: list[str] = []
        details: dict[str, str] = {}

        rsi = ta.rsi(close, length=14)
        if rsi is not None and len(rsi) >= 1:
            rsi_last = _safe_float(rsi.iloc[-1], default=np.nan)
            if rsi_last < 30:
                hits.append("RSI oversold")
                details["rsi"] = f"{rsi_last:.2f} (<30)"
            elif rsi_last > 70:
                hits.append("RSI overbought")
                details["rsi"] = f"{rsi_last:.2f} (>70)"

        macd = ta.macd(close, fast=12, slow=26, signal=9)
        macd_bull = False
        macd_bear = False
        if macd is not None and len(macd) >= 3:
            macd_line = macd.iloc[:, 0]
            signal_line = macd.iloc[:, 1]
            prev_cross = _safe_float(macd_line.iloc[-2]) - _safe_float(signal_line.iloc[-2])
            curr_cross = _safe_float(macd_line.iloc[-1]) - _safe_float(signal_line.iloc[-1])
            if prev_cross <= 0 < curr_cross:
                hits.append("MACD bullish crossover")
                macd_bull = True
            elif prev_cross >= 0 > curr_cross:
                hits.append("MACD bearish crossover")
                macd_bear = True

            if len(close) >= 6:
                price_delta = _safe_float(close.iloc[-1]) - _safe_float(close.iloc[-5])
                macd_delta = _safe_float(macd_line.iloc[-1]) - _safe_float(macd_line.iloc[-5])
                if price_delta < 0 and macd_delta > 0:
                    hits.append("MACD bullish divergence")
                    macd_bull = True
                elif price_delta > 0 and macd_delta < 0:
                    hits.append("MACD bearish divergence")
                    macd_bear = True

        bb = ta.bbands(close, length=20, std=2)
        if bb is not None and len(bb) >= 20:
            upper = bb.iloc[:, 0]
            middle = bb.iloc[:, 1]
            lower = bb.iloc[:, 2]
            bandwidth = (upper - lower) / middle.replace(0, np.nan)
            bw_now = _safe_float(bandwidth.iloc[-1], default=np.nan)
            bw_avg = _safe_float(bandwidth.tail(20).mean(), default=np.nan)
            if not np.isnan(bw_now) and not np.isnan(bw_avg) and bw_now < (bw_avg * 0.7):
                hits.append("Bollinger squeeze")
            if len(close) >= 3:
                if (close.tail(3) > upper.tail(3)).all():
                    hits.append("Bollinger band walk upper")
                elif (close.tail(3) < lower.tail(3)).all():
                    hits.append("Bollinger band walk lower")

        ema21 = ta.ema(close, length=21)
        ema50 = ta.ema(close, length=50)
        ema100 = ta.ema(close, length=100)
        ema200 = ta.ema(close, length=200)
        if all(x is not None and len(x) >= 1 for x in [ema21, ema50, ema100, ema200]):
            e21 = _safe_float(ema21.iloc[-1])
            e50 = _safe_float(ema50.iloc[-1])
            e100 = _safe_float(ema100.iloc[-1])
            e200 = _safe_float(ema200.iloc[-1])
            if e21 > e50 > e100 > e200:
                hits.append("EMA ribbon bullish")
            elif e21 < e50 < e100 < e200:
                hits.append("EMA ribbon bearish")

        vol_avg = _safe_float(volume.tail(20).mean(), default=0.0)
        vol_now = _safe_float(volume.iloc[-1], default=0.0)
        vol_spike = vol_avg > 0 and vol_now > (2.0 * vol_avg)
        if vol_spike:
            hits.append("Volume spike >2x")

        if funding_rate is not None and not np.isnan(funding_rate):
            if funding_rate > 0.0005:
                hits.append("Funding rate high (>0.05%)")
            elif funding_rate < -0.0003:
                hits.append("Funding rate low (<-0.03%)")

        rsi_oversold = any("RSI oversold" == h for h in hits)
        rsi_overbought = any("RSI overbought" == h for h in hits)
        align_bull = rsi_oversold and macd_bull and vol_spike
        align_bear = rsi_overbought and macd_bear and vol_spike
        details["always_alert"] = "true" if (align_bull or align_bear) else "false"

        return hits, details

    def _atr_ratio(self, df: pd.DataFrame) -> float:
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        if atr is None or len(atr) == 0:
            return 0.0
        close_last = _safe_float(df["close"].iloc[-1], default=0.0)
        return (_safe_float(atr.iloc[-1]) / close_last) if close_last > 0 else 0.0

    def _score(self, tf_hits: dict[str, list[str]], always_alert: bool) -> tuple[str, str]:
        tf_with_hits = [tf for tf, hits in tf_hits.items() if hits]
        unique_categories = set()
        for hits in tf_hits.values():
            for hit in hits:
                unique_categories.add(hit.split(" ")[0])

        if always_alert or (len(unique_categories) >= 3 and len(tf_with_hits) >= 2):
            return "HIGH", "3+ indicators across 2+ timeframes or RSI+MACD+volume aligned"
        if len(unique_categories) >= 2 or len(tf_with_hits) == 1:
            return "MEDIUM", "2 confluences or single timeframe confirmation"
        return "WATCH", "Early setup without full confirmation"

    def _support_resistance(self, df: pd.DataFrame) -> tuple[float, float]:
        lookback = min(len(df), 50)
        support = _safe_float(df["low"].tail(lookback).min())
        resistance = _safe_float(df["high"].tail(lookback).max())
        return support, resistance

    def _scan_pair_exchange(self, exchange_id: str, exchange: ccxt.Exchange, pair: str) -> dict | None:
        symbol = self._resolve_symbol(exchange, pair)
        if symbol is None:
            return None

        ticker = exchange.fetch_ticker(symbol)
        price = _safe_float(ticker.get("last"), default=0.0)
        change_24h = _safe_float(ticker.get("percentage"), default=0.0)

        funding = self._funding_rate(exchange, symbol)
        tf_hits: dict[str, list[str]] = {}
        tf_details: dict[str, dict] = {}
        atr_ratio_reference = 0.0

        for timeframe in self.timeframes:
            df = self._fetch_ohlcv_df(exchange, symbol, timeframe)
            if df is None:
                tf_hits[self.timeframe_labels[timeframe]] = []
                continue
            hits, details = self._indicator_hits(df, funding)
            tf_hits[self.timeframe_labels[timeframe]] = hits
            tf_details[self.timeframe_labels[timeframe]] = details
            if timeframe == "15m":
                atr_ratio_reference = self._atr_ratio(df)

        always_alert = any(
            details.get("always_alert") == "true"
            for details in tf_details.values()
        )
        score, reasoning = self._score(tf_hits, always_alert)

        if atr_ratio_reference < self.low_vol_atr_ratio and score != "HIGH" and not always_alert:
            return None

        support_df = self._fetch_ohlcv_df(exchange, symbol, "1h")
        if support_df is None:
            support_df = self._fetch_ohlcv_df(exchange, symbol, "15m")
        if support_df is None:
            return None
        support, resistance = self._support_resistance(support_df)

        triggered = {tf: hits for tf, hits in tf_hits.items() if hits}
        if not triggered:
            return None

        action = {
            "HIGH": "prepare and tighten stop",
            "MEDIUM": "prepare",
            "WATCH": "watch",
        }[score]

        return {
            "timestamp": _now_iso(),
            "exchange": exchange_id,
            "pair": pair,
            "price": price,
            "change_24h_pct": change_24h,
            "triggered": triggered,
            "support_below": support,
            "resistance_above": resistance,
            "suggested_action": action,
            "confidence": score,
            "confidence_reasoning": reasoning,
        }

    def _scan_once(self) -> list[dict]:
        alerts: list[dict] = []
        for exchange_id, exchange in self._exchanges.items():
            for pair in self.pairs:
                try:
                    alert = self._scan_pair_exchange(exchange_id, exchange, pair)
                    if alert is not None:
                        alerts.append(alert)
                except Exception as exc:
                    logger.warning("Scan failed for %s %s: %s", exchange_id, pair, exc)
        rank = {"HIGH": 0, "MEDIUM": 1, "WATCH": 2}
        alerts.sort(key=lambda x: (rank.get(x["confidence"], 9), -abs(_safe_float(x["change_24h_pct"]))))
        return alerts

    def _write_scan_log(self, started: str, alerts: list[dict]):
        day = datetime.utcnow().strftime("%Y-%m-%d")
        root = Path(__file__).resolve().parents[1]
        log_dir = root / "memory" / "scans"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{day}.md"

        lines = [f"## Scan {started} UTC", ""]
        if not alerts:
            lines.append("- No alerts this scan.")
        else:
            for alert in alerts:
                lines.append(
                    f"- [{alert['confidence']}] {alert['exchange']} {alert['pair']} "
                    f"price={alert['price']:.4f} change24h={alert['change_24h_pct']:.2f}% action={alert['suggested_action']}"
                )
                for tf, hits in alert["triggered"].items():
                    lines.append(f"  - {tf}: {', '.join(hits)}")
                lines.append(
                    f"  - support={alert['support_below']:.4f} resistance={alert['resistance_above']:.4f}"
                )
        lines.append("")

        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
