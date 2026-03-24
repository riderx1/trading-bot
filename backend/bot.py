"""
bot.py - Core trading bot logic.

Responsibilities:
    1. Poll Polymarket crypto markets for YES/NO prices.
    2. Poll Binance BTC spot data for multi-timeframe momentum signals.
    3. Evaluate Polymarket trade opportunities in two modes:
             - 'arbitrage': buy YES+NO when combined price < arb_threshold
             - 'signal':    use BTC trend to pick YES or NO direction
    4. Execute paper trades (simulated) or live trades when enabled.
    5. Persist all prices, signals, trades, and log messages to SQLite.

Run standalone:
        python bot.py

Or import TradingBot and start() it from api.py.
"""

import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from db import Database
from execution_client import build_paper_execution_clients
from hyperliquid_client import HyperliquidClient
from orchestrator import Orchestrator
from fair_value_engine import FairValueEngine
from risk_engine import RiskEngine
from simulation import SimulationEngine
from strategy_taxonomy import normalize_strategy, strategy_domain
from validators import (
    validate_binance_klines_payload,
    validate_binance_price_payload,
    validate_config,
    validate_polymarket_market_item,
)

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("TradingBot")
# ── Symbol keyword mapping ─────────────────────────────────────────────────────
SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "BTCUSDT": ["bitcoin", "btc"],
    "ETHUSDT": ["ethereum", "eth"],
    "SOLUSDT": ["solana", "sol"],
}



def load_config() -> dict:
    """Load and return the contents of config.json."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


def _parse_json_list(value) -> list:
    """Return a list from either a JSON-encoded string or an existing list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _age_seconds(iso_ts: str) -> float:
    return (datetime.utcnow() - datetime.fromisoformat(iso_ts)).total_seconds()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


# ── Polymarket Client ──────────────────────────────────────────────────────────


class PolymarketClient:
    """
    Thin wrapper around the Polymarket Gamma REST API.

    Fetches active prediction markets and extracts YES/NO token prices.

    Docs: https://docs.polymarket.com / https://gamma-api.polymarket.com
    """

    BASE_URL = "https://gamma-api.polymarket.com"
    DATA_API_URL = "https://data-api.polymarket.com"
    CLOB_API_URL = "https://clob.polymarket.com"

    def __init__(
        self,
        api_key: str = "",
        wallet_address: str = "",
        focus_keywords: list[str] | None = None,
    ):
        self.api_key = api_key
        self.focus_keywords = [k.lower() for k in (focus_keywords or [])]
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def is_relevant_market(self, market_name: str) -> bool:
        """Return True when the market matches the configured topic focus."""
        if not self.focus_keywords:
            return True
        name = (market_name or "").lower()
        normalized_name = re.sub(r"[^a-z0-9]+", " ", name)
        return any(
            re.search(rf"\b{re.escape(keyword.lower())}\b", normalized_name)
            for keyword in self.focus_keywords
        )

    def _safe_get(self, url: str, params: dict | None = None, timeout: int = 8):
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return None

    def get_data_market_activity(self, market_id: str) -> dict | None:
        """Read-only Data API market activity snapshot (best-effort)."""
        if not market_id:
            return None
        return self._safe_get(f"{self.DATA_API_URL}/activity", params={"market": market_id})

    def get_clob_orderbook(self, token_id: str) -> dict | None:
        """Read-only CLOB top-of-book snapshot for a token id (best-effort)."""
        if not token_id:
            return None
        return self._safe_get(f"{self.CLOB_API_URL}/book", params={"token_id": token_id})

    def get_clob_midpoint(self, token_id: str) -> dict | None:
        """Read-only CLOB midpoint snapshot for a token id (best-effort)."""
        if not token_id:
            return None
        return self._safe_get(f"{self.CLOB_API_URL}/midpoint", params={"token_id": token_id})

    def get_top_of_book(self, token_id: str) -> dict:
        """Return normalized top-of-book values from CLOB endpoints when available."""
        book = self.get_clob_orderbook(token_id)
        midpoint = self.get_clob_midpoint(token_id)

        best_bid = None
        best_ask = None
        midpoint_price = None

        if isinstance(book, dict):
            bids = book.get("bids") or []
            asks = book.get("asks") or []
            if bids:
                try:
                    best_bid = float(bids[0].get("price") or bids[0].get("px") or 0.0)
                except Exception:
                    best_bid = None
            if asks:
                try:
                    best_ask = float(asks[0].get("price") or asks[0].get("px") or 0.0)
                except Exception:
                    best_ask = None

        if isinstance(midpoint, dict):
            try:
                midpoint_price = float(
                    midpoint.get("midpoint")
                    or midpoint.get("mid")
                    or midpoint.get("price")
                    or 0.0
                )
            except Exception:
                midpoint_price = None

        spread_bps = None
        if best_bid and best_ask and best_bid > 0 and best_ask > 0:
            mid = (best_bid + best_ask) / 2.0
            if mid > 0:
                spread_bps = ((best_ask - best_bid) / mid) * 10_000.0

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "midpoint": midpoint_price,
            "spread_bps": spread_bps,
        }

    def get_markets(self, limit: int = 20) -> list[dict]:
        """
        Fetch active markets with YES/NO prices.

        Each returned dict has keys:
          market_name, yes_price, no_price, condition_id

        Returns an empty list on error (error is logged).
        """
        try:
            page_size = 100
            max_pages = 10
            markets = []
            seen_condition_ids = set()

            for page in range(max_pages):
                resp = self.session.get(
                    f"{self.BASE_URL}/markets",
                    params={
                        "active": "true",
                        "closed": "false",
                        "limit": page_size,
                        "offset": page * page_size,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                items = resp.json()
                if not items:
                    break

                for item in items:
                    validate_polymarket_market_item(item)
                    condition_id = item.get("conditionId", "")
                    if condition_id in seen_condition_ids:
                        continue

                    yes_token_id = None
                    no_token_id = None

                    outcomes = _parse_json_list(item.get("outcomes"))
                    outcome_prices = _parse_json_list(item.get("outcomePrices"))
                    outcome_map = {}

                    for outcome, price in zip(outcomes, outcome_prices):
                        try:
                            outcome_map[str(outcome)] = float(price)
                        except (TypeError, ValueError):
                            continue

                    if not outcome_map:
                        # Fall back to alternate shapes some responses may include.
                        for token in item.get("tokens", []):
                            outcome = token.get("outcome")
                            try:
                                price = float(token.get("price", 0))
                            except (TypeError, ValueError):
                                continue
                            if outcome:
                                outcome_map[str(outcome)] = price

                    for token in item.get("tokens", []):
                        outcome = str(token.get("outcome") or "").strip().lower()
                        token_id = token.get("token_id") or token.get("tokenId") or token.get("id")
                        token_id = str(token_id) if token_id is not None else None
                        if outcome == "yes":
                            yes_token_id = token_id
                        elif outcome == "no":
                            no_token_id = token_id

                    market_name = item.get("question", item.get("slug", "unknown"))
                    if not self.is_relevant_market(market_name):
                        continue

                    seen_condition_ids.add(condition_id)

                    markets.append(
                        {
                            "market_id": condition_id,
                            "market_name": market_name,
                            # Handle both capitalization variants from the API.
                            "yes_price": outcome_map.get(
                                "Yes", outcome_map.get("YES", 0.5)
                            ),
                            "no_price": outcome_map.get(
                                "No", outcome_map.get("NO", 0.5)
                            ),
                            "yes_ask": outcome_map.get(
                                "Yes", outcome_map.get("YES", 0.5)
                            ),
                            "no_ask": outcome_map.get(
                                "No", outcome_map.get("NO", 0.5)
                            ),
                            "spread_bps": float(item.get("spread") or 0.0)
                            * 10000.0,
                            "liquidity": float(
                                item.get("liquidityNum", item.get("liquidity", 0.0))
                            ),
                            "yes_token_id": yes_token_id,
                            "no_token_id": no_token_id,
                            "end_date": item.get("endDate"),
                            "fetched_at": datetime.utcnow().isoformat(),
                        }
                    )
                    if len(markets) >= limit:
                        return markets

            return markets
        except requests.RequestException as exc:
            logger.error("Polymarket API error: %s", exc)
            return []


# ── Binance Client ─────────────────────────────────────────────────────────────


class BinanceClient:
    """
    Fetches price data from the Binance public REST API.

    No API key is required for spot price and kline endpoints.
    Implements simple exponential back-off on HTTP 429 (rate-limit) responses.
    """

    DEFAULT_BASE_URLS = [
        "https://data-api.binance.vision",
        "https://api.binance.com",
        "https://api-gcp.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api4.binance.com",
    ]
    MAX_RETRIES = 3
    BASE_DELAY = 5  # seconds; doubled on each retry

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        symbol: str = "BTCUSDT",
        base_urls: list[str] | None = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret  # reserved for authenticated endpoints
        self.symbol = symbol
        self.base_urls = base_urls or self.DEFAULT_BASE_URLS
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-MBX-APIKEY": api_key})

    def _get(self, path: str, params: dict, timeout: int = 5) -> requests.Response:
        """Try the configured Binance hosts in order until one succeeds."""
        last_error = None
        for base_url in self.base_urls:
            try:
                return self.session.get(
                    f"{base_url}/api/v3/{path}",
                    params=params,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Binance host %s failed: %s", base_url, exc)

        if last_error is not None:
            raise last_error
        raise requests.RequestException("No Binance base URLs configured")

    def get_price(self) -> float | None:
        """
        Fetch the latest spot price for self.symbol.

        Returns the price as a float, or None if all retries fail.
        Uses exponential back-off on HTTP 429 responses.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._get("ticker/price", {"symbol": self.symbol})
                if resp.status_code == 429:
                    wait = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Binance rate limit hit. Backing off %ds (attempt %d).",
                        wait,
                        attempt + 1,
                    )
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                payload = resp.json()
                validate_binance_price_payload(payload)
                return float(payload["price"])
            except requests.RequestException as exc:
                logger.error(
                    "Binance get_price error (attempt %d): %s", attempt + 1, exc
                )
                time.sleep(self.BASE_DELAY)
            except (TypeError, ValueError) as exc:
                logger.error("Binance price schema error: %s", exc)
                return None
        return None

    def get_klines(self, interval: str = "1m", limit: int = 5) -> list[dict]:
        """
        Fetch recent OHLCV candlestick data.

        Args:
            interval: Binance interval string, e.g. '1m', '5m', '1h'.
            limit:    Number of candles to fetch.

        Returns a list of dicts with keys: open, high, low, close, volume.
        Returns an empty list on error.
        """
        try:
            resp = self._get(
                "klines",
                {
                    "symbol": self.symbol,
                    "interval": interval,
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            validate_binance_klines_payload(payload)
            return [
                {
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in payload
            ]
        except requests.RequestException as exc:
            logger.error("Binance get_klines error: %s", exc)
            return []
        except (TypeError, ValueError) as exc:
            logger.error("Binance kline schema error: %s", exc)
            return []

    def classify_trend(self, interval: str = "5m") -> str:
        return self.analyze_trend(interval=interval)["trend"]

    def get_perp_price(self) -> float | None:
        """
        Fetch the perpetual futures mark price for self.symbol from Binance Futures.
        Returns None on error or if the futures API is unavailable.
        """
        try:
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": self.symbol},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            mark = data.get("markPrice") or data.get("indexPrice")
            return float(mark) if mark else None
        except Exception as exc:
            logger.debug("Binance perp price fetch failed (%s): %s", self.symbol, exc)
            return None

    def get_funding_rate(self) -> float | None:
        """
        Fetch the latest perpetual funding rate for self.symbol from Binance Futures.
        Returns the hourly funding rate as a raw fraction (e.g. 0.0001 = 0.01%/hr).
        Returns None on error.
        """
        try:
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": self.symbol},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            rate = data.get("lastFundingRate")
            return float(rate) if rate is not None else None
        except Exception as exc:
            logger.debug("Binance funding rate fetch failed (%s): %s", self.symbol, exc)
            return None

    def analyze_trend(
        self,
        interval: str = "5m",
        neutral_band_pct: float = 0.0015,
        momentum_scale: float = 2.4,
    ) -> dict:
        """
        Analyze BTC momentum for a timeframe.

        Uses direction, recent move strength, and candle breadth to produce a
        trend plus a confidence score in the range [0, 1].
        """
        klines = self.get_klines(interval=interval, limit=12)
        if not klines or len(klines) < 6:
            return {
                "trend": "neutral",
                "confidence": 0.0,
                "move_pct": 0.0,
                "reasoning": "insufficient_candles",
            }

        closed_klines = klines[:-1]
        first_open = closed_klines[0]["open"]
        last_close = closed_klines[-1]["close"]
        change_pct = (last_close - first_open) / first_open

        recent_slice = closed_klines[-4:]
        recent_open = recent_slice[0]["open"]
        recent_close = recent_slice[-1]["close"]
        recent_change_pct = (recent_close - recent_open) / recent_open

        bullish_candles = sum(
            1 for candle in closed_klines[-6:] if candle["close"] > candle["open"]
        )
        bearish_candles = sum(
            1 for candle in closed_klines[-6:] if candle["close"] < candle["open"]
        )
        candle_bias = (bullish_candles - bearish_candles) / 6.0

        momentum_raw = (
            (abs(change_pct) / neutral_band_pct) * 0.55
            + (abs(recent_change_pct) / neutral_band_pct) * 0.35
            + (abs(candle_bias) * 0.10)
        )
        confidence = min(1.0, momentum_raw / momentum_scale)

        if (
            abs(change_pct) < neutral_band_pct
            and abs(recent_change_pct) < neutral_band_pct
        ):
            trend = "neutral"
        elif (
            change_pct > 0
            and recent_change_pct > -(neutral_band_pct * 0.5)
            and candle_bias >= -0.1
        ):
            trend = "bullish"
        elif (
            change_pct < 0
            and recent_change_pct < (neutral_band_pct * 0.5)
            and candle_bias <= 0.1
        ):
            trend = "bearish"
        elif confidence >= 0.55:
            trend = "bullish" if change_pct > 0 else "bearish"
        else:
            trend = "neutral"

        reasoning = (
            f"move={change_pct:.4f}; recent={recent_change_pct:.4f}; "
            f"candle_bias={candle_bias:.2f}; momentum={confidence:.2f}"
        )
        return {
            "trend": trend,
            "confidence": confidence,
            "move_pct": change_pct,
            "reasoning": reasoning,
        }


# ── Strategy Worker ──────────────────────────────────────────────────────────


class StrategyWorker:
    """
    Autonomous per-strategy unit for the 10-bot Hyperliquid paper trading suite.

    Each worker:
    - Has its own entry-condition logic tuned to its strategy type.
    - Tracks a per-symbol cooldown so concurrent workers don't step on each other.
    - Never shares state with sibling workers.

    Capital allocation ($14 USDC each) is enforced by SimulationEngine wallets.
    """

    # Minimum confidence required before directional entry (per strategy).
    _CONF_FLOOR: dict[str, float] = {
        "trend":          0.55,
        "momentum":       0.35,
        "ta_confluence":  0.40,
        "reversal":       0.35,
        "breakout":       0.60,
        "mean_reversion": 0.30,
        "scalping":       0.20,   # uses micro conditions, not confidence
        "funding_arb":    0.0,
        "basis_arb":      0.0,
        "volatility":     0.0,
    }

    def __init__(self, strategy: str) -> None:
        self.strategy = strategy
        self._cooldowns: dict[str, float] = {}   # symbol → expiry epoch-seconds
        self._lock = threading.Lock()

    def is_on_cooldown(self, symbol: str) -> bool:
        with self._lock:
            return time.time() < self._cooldowns.get(symbol, 0.0)

    def set_cooldown(self, symbol: str, seconds: float) -> None:
        with self._lock:
            self._cooldowns[symbol] = time.time() + seconds

    # ── Directional evaluation ────────────────────────────────────────────────

    def evaluate_directional(
        self,
        signal_snapshot: dict,
        symbol: str,
    ) -> tuple[bool, int, str]:
        """
        Decide whether to enter based on a Binance signal snapshot.

        Returns:
            (should_enter, direction, reason_string)
            direction: +1 = long/buy, -1 = short/sell
        """
        if self.is_on_cooldown(symbol):
            return False, 0, "cooldown"

        trend = str(signal_snapshot.get("trend") or "neutral")
        confidence = float(signal_snapshot.get("confidence") or 0.0)
        regime = str(signal_snapshot.get("regime") or "CHOP")
        micro_data = signal_snapshot.get("micro_data") or {}
        timeframes = signal_snapshot.get("timeframes") or {}
        conf_floor = self._CONF_FLOOR.get(self.strategy, 0.4)

        if self.strategy == "scalping":
            move_pct = float(micro_data.get("move_pct_short") or 0.0)
            spread_bps = float(micro_data.get("spread_bps") or 999.0)
            volume_spike = bool(micro_data.get("volume_spike"))
            if not (volume_spike and spread_bps <= 15.0 and abs(move_pct) >= 0.001):
                return False, 0, f"scalp:no_setup spread={spread_bps:.0f}bp vol={volume_spike}"
            return True, (1 if move_pct > 0 else -1), f"scalp:move={move_pct:.4f} spread={spread_bps:.0f}bp"

        if self.strategy == "reversal":
            if regime != "REVERSAL":
                return False, 0, f"reversal:regime={regime}!=REVERSAL"
            if trend == "neutral" or confidence < conf_floor:
                return False, 0, f"reversal:trend={trend} conf={confidence:.2f}"
            return True, (-1 if trend == "bullish" else 1), f"reversal:fade trend={trend} conf={confidence:.2f}"

        if self.strategy == "trend":
            htf = [timeframes.get(tf, {}).get("trend", "neutral") for tf in ("1h", "4h", "1d")]
            aligned = htf.count(trend)
            if trend == "neutral" or aligned < 2 or confidence < conf_floor:
                return False, 0, f"trend:htf_aligned={aligned}/3 conf={confidence:.2f}"
            return True, (1 if trend == "bullish" else -1), f"trend:htf_aligned={aligned}/3 conf={confidence:.2f}"

        if self.strategy == "momentum":
            stf = [timeframes.get(tf, {}).get("trend", "neutral") for tf in ("5m", "15m")]
            if trend == "neutral" or confidence < conf_floor or trend not in stf:
                return False, 0, f"momentum:stf={stf} conf={confidence:.2f}"
            return True, (1 if trend == "bullish" else -1), f"momentum:stf={'/'.join(stf)} conf={confidence:.2f}"

        if self.strategy == "ta_confluence":
            if trend == "neutral" or confidence < conf_floor:
                return False, 0, f"ta_confluence:trend={trend} conf={confidence:.2f}"
            return True, (1 if trend == "bullish" else -1), f"ta_confluence:trend={trend} conf={confidence:.2f}"

        if self.strategy == "breakout":
            move_5m = abs(float((timeframes.get("5m") or {}).get("move_pct") or 0.0))
            if trend == "neutral" or confidence < conf_floor or move_5m < 0.003:
                return False, 0, f"breakout:move_5m={move_5m:.4f} conf={confidence:.2f}"
            return True, (1 if trend == "bullish" else -1), f"breakout:move_5m={move_5m:.4f} conf={confidence:.2f}"

        if self.strategy == "mean_reversion":
            if regime == "TRENDING" or trend == "neutral" or confidence < conf_floor:
                return False, 0, f"mean_rev:regime={regime} trend={trend}"
            move_1h = float((timeframes.get("1h") or {}).get("move_pct") or 0.0)
            if abs(move_1h) < 0.005:
                return False, 0, f"mean_rev:move_1h={move_1h:.4f}<0.005"
            return True, (-1 if move_1h > 0 else 1), f"mean_rev:move_1h={move_1h:.4f} regime={regime}"

        return False, 0, f"{self.strategy}:no_directional_rule"

    # ── Arb evaluation ────────────────────────────────────────────────────────

    def evaluate_arb(
        self,
        perp_context: dict,
        symbol: str,
        min_funding_spread: float = 0.0001,
        min_basis_bp: float = 5.0,
    ) -> tuple[bool, int, str]:
        """
        Decide whether to enter an arb position from perp context data.

        Returns (should_enter, direction, reason_string).
        """
        if self.is_on_cooldown(symbol):
            return False, 0, "cooldown"

        if self.strategy == "funding_arb":
            funding_spread = float(perp_context.get("funding_spread") or 0.0)
            hl_fund = float(perp_context.get("hl_funding_rate") or 0.0)
            if abs(funding_spread) < min_funding_spread:
                return False, 0, f"funding_arb:spread={funding_spread:.6f}<min={min_funding_spread}"
            direction = 1 if hl_fund < 0 else -1
            return True, direction, f"funding_arb:spread={funding_spread:.6f} hl_rate={hl_fund:.6f}"

        if self.strategy == "basis_arb":
            basis_diff = float(perp_context.get("basis_diff") or 0.0)
            bin_perp = float(perp_context.get("binance_perp_price") or 0.0)
            hl_perp = float(perp_context.get("hl_perp_price") or 0.0)
            if not (bin_perp and hl_perp):
                return False, 0, "basis_arb:missing_perp_prices"
            bp = abs(basis_diff / max(bin_perp, hl_perp, 1.0)) * 10_000
            if bp < min_basis_bp:
                return False, 0, f"basis_arb:bp={bp:.1f}<min={min_basis_bp}"
            return True, (-1 if basis_diff > 0 else 1), f"basis_arb:bp={bp:.1f} bin={bin_perp:.2f} hl={hl_perp:.2f}"

        return False, 0, f"{self.strategy}:no_arb_rule"


# ── Trading Bot ───────────────────────────────────────────────────────────────


class TradingBot:
    def __init__(self):
        self.config = load_config()
        validate_config(self.config)

        self.db = Database()
        self.db.set_bot_state("running", False)

        trading_cfg = self.config["trading"]
        self.paper_trading: bool = bool(trading_cfg.get("paper_trading", True))
        if not self.paper_trading:
            self.paper_trading = True
            trading_cfg["paper_trading"] = True
            logger.warning("paper_trading was disabled in config, forcing paper_trading=true (live trading blocked).")
        self.execution_mode: str = str(
            self.config.get(
                "execution_mode",
                self.config.get("execution", {}).get("mode", "paper"),
            )
        ).strip().lower()
        if self.execution_mode != "paper":
            raise ValueError(
                f"Invalid execution_mode='{self.execution_mode}'. Only 'paper' is supported."
            )
        self.config["execution_mode"] = "paper"
        if "execution" not in self.config:
            self.config["execution"] = {}
        self.config["execution"]["mode"] = "paper"
        self.mode: str = trading_cfg["mode"]
        self.arb_threshold: float = trading_cfg["arb_threshold"]
        self.signal_threshold: float = trading_cfg["signal_threshold"]
        self.trade_size: float = trading_cfg["trade_size_usdc"]
        self.min_confidence: float = trading_cfg["min_confidence"]
        self.max_signal_age_seconds: int = trading_cfg["max_signal_age_seconds"]
        self.max_market_age_seconds: int = trading_cfg["max_market_age_seconds"]
        self.trade_bucket_seconds: int = trading_cfg["trade_bucket_seconds"]
        self.cooldown_seconds: int = trading_cfg["cooldown_seconds"]
        self.emit_signals_only: bool = bool(trading_cfg.get("emit_signals_only", False))
        self.min_edge: float = float(trading_cfg["min_edge"])
        self.signal_neutral_band_pct: float = float(
            trading_cfg["signal_neutral_band_pct"]
        )
        self.momentum_scale: float = float(trading_cfg["momentum_scale"])
        self.medium_signal_floor: float = float(trading_cfg["medium_signal_floor"])
        self.strong_signal_floor: float = float(trading_cfg["strong_signal_floor"])
        self.probability_floor: float = float(trading_cfg["probability_floor"])
        self.probability_ceiling: float = float(trading_cfg["probability_ceiling"])
        self.higher_timeframe_boost: float = float(trading_cfg["higher_timeframe_boost"])
        self.conflict_penalty: float = float(trading_cfg["conflict_penalty"])
        self.ta_alignment_boost: float = float(trading_cfg["ta_alignment_boost"])
        self.ta_conflict_penalty: float = float(trading_cfg["ta_conflict_penalty"])
        self.confidence_cap: float = float(trading_cfg.get("confidence_cap", 0.75))
        self.low_sample_threshold: int = int(trading_cfg.get("low_sample_threshold", 25))
        self.low_sample_penalty: float = float(trading_cfg.get("low_sample_penalty", 0.12))
        self.medium_horizon_conf_multiplier: float = float(trading_cfg.get("medium_horizon_conf_multiplier", 0.65))
        self.long_horizon_conf_multiplier: float = float(trading_cfg.get("long_horizon_conf_multiplier", 0.15))
        self.block_long_horizon_markets: bool = bool(trading_cfg.get("block_long_horizon_markets", True))
        self.max_position_per_trade_usdc: float = float(trading_cfg.get("max_position_per_trade_usdc", self.trade_size))
        capital_cfg = self.config.get("capital_allocation", {})
        self.capital_allocation_directional: float = float(capital_cfg.get("directional", 0.7))
        self.capital_allocation_arbitrage: float = float(capital_cfg.get("arbitrage", 0.3))
        self.confidence_density_threshold: float = float(trading_cfg.get("confidence_density_threshold", 12.0))
        self.confidence_density_window_minutes: int = int(trading_cfg.get("confidence_density_window_minutes", 30))
        self.strategies: list[str] = [
            "trend",
            "momentum",
            "ta_confluence",
            "reversal",
            "breakout",
            "mean_reversion",
            "funding_arb",
            "basis_arb",
            "volatility",
            "scalping",
        ]

        # Runtime state
        self.running: bool = False
        self.bot_status: str = "stopped"
        self.latest_markets: list[dict] = []
        self.latest_signal: dict = {}
        self.latest_signals: dict[str, dict] = {}
        self._stats: dict[str, int] = {
            "consensus_blocked_count": 0,
        }
        self.scanner: Any | None = None
        self.last_signal_sequence_id: int | None = self.db.get_latest_signal_sequence_id()
        self.last_processed_market_timestamp: str | None = self.db.get_bot_state(
            "last_processed_market_timestamp", None
        )
        self._lock = threading.Lock()  # protects shared state above

        # Thread handles (set in start())
        self._binance_thread: threading.Thread | None = None
        self._poly_thread: threading.Thread | None = None

        # API clients
        poly_cfg = self.config.get("polymarket", {})
        bin_cfg = self.config["binance"]
        primary_symbol = str(bin_cfg.get("symbol", "BTCUSDT")).upper()
        self.signal_intervals: list[str] = bin_cfg.get(
            "signal_intervals", ["5m", "15m", "1h", "4h", "1d"]
        )
        self.polymarket = PolymarketClient(
            api_key=poly_cfg.get("api_key", ""),
            wallet_address=poly_cfg.get("wallet_address", ""),
            focus_keywords=poly_cfg.get("focus_keywords"),
        )
        self.binance = BinanceClient(
            api_key=bin_cfg.get("api_key", ""),
            api_secret=bin_cfg.get("api_secret", ""),
            symbol=primary_symbol,
            base_urls=bin_cfg.get("base_urls"),
        )
        configured_symbols = bin_cfg.get(
            "symbols",
            bin_cfg.get("supported_symbols", [primary_symbol]),
        )
        self.symbols: list[str] = [
            str(sym).upper() for sym in configured_symbols if str(sym).strip()
        ]
        if not self.symbols:
            self.symbols = [primary_symbol]
        self.supported_symbols: list[str] = list(self.symbols)
        self._binance_clients: dict[str, BinanceClient] = {
            sym: BinanceClient(
                api_key=bin_cfg.get("api_key", ""),
                api_secret=bin_cfg.get("api_secret", ""),
                symbol=sym,
                base_urls=bin_cfg.get("base_urls"),
            )
            for sym in self.symbols
        }
        risk_cfg = dict(trading_cfg)
        risk_cfg["execution_mode"] = self.execution_mode
        risk_cfg["risk"] = self.config.get("risk", {})
        self.risk_engine = RiskEngine(risk_cfg)
        self.simulation = SimulationEngine(self.db, self.config)
        (
            self.polymarket_execution_client,
            self.hyperliquid_execution_client,
        ) = build_paper_execution_clients(
            mode=self.execution_mode,
            db=self.db,
            trading_cfg=self.config["trading"],
        )
        self.orchestrator = Orchestrator(self.db, self.config)
        self.latest_orchestrated_decisions: dict[str, dict] = {}
        self.latest_micro_data: dict[str, dict] = {}
        fv_cfg = self.config.get("fair_value", {})
        self.fair_value_engine = FairValueEngine(
            model_vs_market_threshold_bp=int(fv_cfg.get("model_vs_market_threshold_bp", 600)),
            yes_no_sum_threshold=self.arb_threshold,
        )
        # ── Hyperliquid perp client ──────────────────────────────────────────
        hl_cfg = self.config.get("hyperliquid", {})
        hl_symbols = hl_cfg.get("symbols") or self.symbols
        self.hyperliquid = HyperliquidClient(symbols=hl_symbols)
        self._hl_thread: threading.Thread | None = None
        # latest perp context: symbol → {funding_rate, basis_pct, hl_perp_price,
        #                                  binance_perp_price, basis_diff, funding_spread}
        self.latest_perp_context: dict[str, dict] = {}

        self.allowed_market_timeframes: dict[str, str] = {
            "5m": r"(?<!\d)5\s*(m|min|mins|minute|minutes)\b|\b5m\b",
            "15m": r"(?<!\d)15\s*(m|min|mins|minute|minutes)\b|\b15m\b",
            "1h": r"\b1\s*(h|hr|hour|hours)\b|\b60\s*(m|min|mins|minute|minutes)\b|\b1h\b",
            "4h": r"\b4\s*(h|hr|hour|hours)\b|\b240\s*(m|min|mins|minute|minutes)\b|\b4h\b",
            "1d": r"\b24\s*(h|hr|hour|hours)\b|\b1\s*(d|day|days)\b|\b1d\b|\btoday\b",
        }

        # ── Strategy workers (10 independent bots, one per strategy) ──────────
        self._strategy_workers: dict[str, StrategyWorker] = {
            s: StrategyWorker(s) for s in self.strategies
        }

    # ── Internal logging ────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "INFO"):
        """Write to both the Python logger (console) and the SQLite log table."""
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(message)
        try:
            self.db.insert_log(message, level)
        except Exception as exc:  # never let DB errors crash the polling loop
            logger.error("DB log write failed: %s", exc)

    def attach_scanner(self, scanner: Any):
        self.scanner = scanner

    def _signal_strength_label(self, confidence: float, trend: str) -> str:
        if trend == "neutral":
            return "weak"
        if confidence >= self.strong_signal_floor:
            return "strong"
        if confidence >= self.medium_signal_floor:
            return "medium"
        return "weak"

    def _infer_regime(self, signals_by_interval: dict[str, dict]) -> str:
        if not signals_by_interval:
            return "CHOP"

        moves = [abs(float(signal.get("move_pct") or 0.0)) for signal in signals_by_interval.values()]
        avg_vol = sum(moves) / max(len(moves), 1)
        trends = [str(signal.get("trend") or "neutral") for signal in signals_by_interval.values()]
        directional = [trend for trend in trends if trend in {"bullish", "bearish"}]
        trend_consistency = len(set(directional)) <= 1 if directional else False

        short_moves = [
            abs(float(signals_by_interval.get(tf, {}).get("move_pct") or 0.0))
            for tf in ("5m", "15m")
            if tf in signals_by_interval
        ]
        long_moves = [
            abs(float(signals_by_interval.get(tf, {}).get("move_pct") or 0.0))
            for tf in ("1h", "4h", "1d")
            if tf in signals_by_interval
        ]
        short_avg = sum(short_moves) / max(len(short_moves), 1)
        long_avg = sum(long_moves) / max(len(long_moves), 1)
        expanding = short_avg > (long_avg * 1.15 if long_avg > 0 else 0.0)

        if avg_vol < 0.006 and not trend_consistency:
            return "CHOP"
        if not trend_consistency and avg_vol > 0.01:
            return "REVERSAL"
        if trend_consistency and expanding:
            return "TRENDING"
        if not trend_consistency:
            return "REVERSAL"
        return "CHOP"

    def _direction_from_trend(self, trend: str) -> int:
        if trend == "bullish":
            return 1
        if trend == "bearish":
            return -1
        return 0

    def _select_strategy(
        self,
        trend: str,
        confidence: float,
        regime: str,
        reason_code: str | None = None,
        edge: float | None = None,
        micro_data: dict | None = None,
    ) -> str:
        if self._is_scalping_setup(micro_data):
            return "scalping"
        if reason_code and "arb" in reason_code:
            return "funding_arb"
        if edge is not None and edge >= max(self.min_edge, 0.01):
            return "funding_arb"
        if regime == "REVERSAL":
            return "reversal"
        if confidence >= self.strong_signal_floor and trend in {"bullish", "bearish"}:
            return "momentum"
        return "ta_confluence"

    def _strategy_score_map(self) -> dict[str, float]:
        rankings = self.db.get_strategy_rankings()
        if not rankings:
            return {
                "momentum": 0.0,
                "ta_confluence": 0.0,
                "reversal": 0.0,
                "trend": 0.0,
                "breakout": 0.0,
                "mean_reversion": 0.0,
                "funding_arb": 0.0,
                "basis_arb": 0.0,
                "volatility": 0.0,
                "scalping": 0.0,
            }
        return {
            normalize_strategy(str(row.get("strategy") or "")): float(row.get("score") or 0.0)
            for row in rankings
        }

    def _apply_signal_scarcity(self, confidence: float, strategy: str, symbol: str) -> float:
        recent_signals = self.db.get_signal_density(
            window_minutes=self.confidence_density_window_minutes,
            symbol=symbol,
            strategy=normalize_strategy(strategy),
        )
        threshold = max(1.0, float(self.confidence_density_threshold))
        signal_density = recent_signals / threshold
        scarcity_factor = 1.0 / (1.0 + signal_density)
        return max(0.0, min(0.75, float(confidence) * scarcity_factor))

    def _apply_strategy_confidence_adjustment(self, confidence: float, strategy: str) -> float:
        strategy = normalize_strategy(strategy)
        scores = self._strategy_score_map()
        if not scores:
            return max(0.0, min(self.confidence_cap, confidence))

        max_score = max(scores.values()) if scores else 0.0
        target_score = float(scores.get(strategy, 0.0))
        if max_score <= 0:
            normalized_score = 1.0
        else:
            normalized_score = max(0.25, min(1.0, target_score / max_score))
        return max(0.0, min(self.confidence_cap, confidence * normalized_score))

    def _normalize_confidence(
        self,
        confidence: float,
        *,
        has_htf_conflict: bool,
        ta_disagreement: bool,
        sample_size: int,
    ) -> float:
        adjusted = float(confidence)
        if has_htf_conflict:
            adjusted -= self.conflict_penalty
        if ta_disagreement:
            adjusted -= self.ta_conflict_penalty
        if sample_size < self.low_sample_threshold:
            scarcity = (self.low_sample_threshold - sample_size) / max(self.low_sample_threshold, 1)
            adjusted -= scarcity * self.low_sample_penalty
        return max(0.0, min(self.confidence_cap, adjusted))

    def _market_horizon(self, market: dict) -> tuple[str, float | None]:
        end_date = str(market.get("end_date") or "").strip()
        if end_date:
            try:
                dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                now = datetime.now(dt.tzinfo)
                days = max(0.0, (dt - now).total_seconds() / 86400.0)
                if days <= 7:
                    return "short", days
                if days <= 30:
                    return "medium", days
                return "long", days
            except ValueError:
                pass

        market_name = _normalize_text(str(market.get("market_name") or ""))
        if any(token in market_name for token in ["today", "tonight", "tomorrow", "this week", "7d", "7 days"]):
            return "short", None
        if any(token in market_name for token in ["this month", "30d", "30 days", "next month"]):
            return "medium", None
        return "long", None

    def _horizon_confidence_multiplier(self, horizon: str) -> float:
        if horizon == "short":
            return 1.0
        if horizon == "medium":
            return self.medium_horizon_conf_multiplier
        return self.long_horizon_conf_multiplier

    def _expected_probability(
        self,
        *,
        symbol: str,
        timeframe: str,
        strategy: str,
        signal_strength: str,
        regime: str,
    ) -> dict:
        return self.db.get_historical_win_rate(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            signal_strength=signal_strength,
            regime=regime,
            min_samples=self.low_sample_threshold,
        )

    def _edge_from_context(self, expected_side_probability: float, market_price: float) -> float:
        raw_edge = max(0.0, float(expected_side_probability) - float(market_price))
        return max(0.0, min(0.10, raw_edge))

    def _risk_factor_for_setup(self, signal_strength: str, confidence: float) -> float:
        strength = str(signal_strength or "weak").lower()
        if strength == "strong" and confidence >= 0.65:
            return 1.0
        if strength in {"strong", "medium"} and confidence >= 0.5:
            return 0.65
        return 0.35

    def _position_size_usdc(self, strategy: str, confidence: float, edge: float, risk_factor: float) -> float:
        strategy = normalize_strategy(strategy)
        wallets = self.simulation.get_wallet_snapshot().get("bots", {})
        wallet_row = wallets.get(strategy, {})
        wallet_equity = float(wallet_row.get("equity_usdc") or self.trade_size)
        size = wallet_equity * max(0.0, min(self.confidence_cap, confidence)) * max(0.0, min(0.10, edge)) * max(0.05, min(1.0, risk_factor))
        if strategy_domain(strategy) == "arbitrage":
            size *= max(0.0, min(1.0, self.capital_allocation_arbitrage))
        else:
            size *= max(0.0, min(1.0, self.capital_allocation_directional))
        max_position = self.max_position_per_trade_usdc * (0.3 if strategy == "scalping" else 1.0)
        return max(0.0, min(max_position, size))

    def _strategy_min_edge(self, strategy: str) -> float:
        if strategy == "scalping":
            return 0.003
        return self.min_edge

    def _is_scalping_setup(self, micro_data: dict | None) -> bool:
        if not isinstance(micro_data, dict):
            return False
        move_pct = float(micro_data.get("move_pct_short") or 0.0)
        spread_bps = float(micro_data.get("spread_bps") or 0.0)
        if spread_bps > 15.0:
            return False
        if not bool(micro_data.get("volume_spike")):
            return False
        return abs(move_pct) >= 0.001

    def _infer_ta_direction(self, hits: list[str]) -> str:
        bullish_markers = ("bullish", "oversold", "band walk upper")
        bearish_markers = ("bearish", "overbought", "band walk lower")
        bull = 0
        bear = 0
        for hit in hits:
            lowered = hit.lower()
            if any(marker in lowered for marker in bullish_markers):
                bull += 1
            if any(marker in lowered for marker in bearish_markers):
                bear += 1
        if bull > bear:
            return "bullish"
        if bear > bull:
            return "bearish"
        return "neutral"

    def _get_ta_alignment(self, trend: str, symbol: str | None = None) -> dict[str, Any]:
        if self.scanner is None or trend == "neutral":
            return {"boost": 0.0, "reasoning": "ta=unavailable"}

        try:
            alerts = self.scanner.get_latest_alerts(limit=20)
        except Exception:
            return {"boost": 0.0, "reasoning": "ta=unavailable"}

        target_pair = (symbol or self.binance.symbol).replace("USDT", "/USDT")
        for alert in alerts:
            if alert.get("pair") != target_pair:
                continue
            hits = []
            for tf_hits in (alert.get("triggered") or {}).values():
                hits.extend(tf_hits)
            ta_direction = self._infer_ta_direction(hits)
            if ta_direction == "neutral":
                return {
                    "boost": 0.0,
                    "reasoning": f"ta=mixed {alert.get('exchange', 'unknown')}",
                }
            if ta_direction == trend:
                return {
                    "boost": self.ta_alignment_boost,
                    "reasoning": f"ta=aligned {alert.get('exchange', 'unknown')} {alert.get('confidence', 'WATCH')}",
                }
            return {
                "boost": -self.ta_conflict_penalty,
                "reasoning": f"ta=conflict {alert.get('exchange', 'unknown')} {alert.get('confidence', 'WATCH')}",
            }

        return {"boost": 0.0, "reasoning": "ta=no-btc-alert"}

    def _combine_trends(
        self, signals_by_interval: dict[str, dict], symbol: str | None = None
    ) -> tuple[str, float, str, str]:
        """Collapse multi-timeframe trends into weighted consensus + confidence."""
        weights = {"5m": 1.0, "15m": 1.5, "1h": 2.5, "4h": 3.0, "1d": 4.0}
        score = 0.0
        total = 0.0
        bullish_higher = []
        bearish_higher = []
        conflicts = []

        for interval, signal in signals_by_interval.items():
            weight = weights.get(interval, 1.0)
            total += weight
            weighted_confidence = weight * (0.55 + (0.45 * signal.get("confidence", 0.0)))
            if signal["trend"] == "bullish":
                score += weighted_confidence
                if interval in {"1h", "4h", "1d"}:
                    bullish_higher.append(interval)
            elif signal["trend"] == "bearish":
                score -= weighted_confidence
                if interval in {"1h", "4h", "1d"}:
                    bearish_higher.append(interval)

        confidence = abs(score) / total if total else 0.0
        trend_1h = signals_by_interval.get("1h", {}).get("trend", "neutral")
        trend_4h = signals_by_interval.get("4h", {}).get("trend", "neutral")
        if trend_1h != "neutral" and trend_4h != "neutral" and trend_1h != trend_4h:
            self._stats["consensus_blocked_count"] = (
                self._stats.get("consensus_blocked_count", 0) + 1
            )
            logger.info(
                f"[CONSENSUS_BLOCKED] count={self._stats['consensus_blocked_count']} "
                "reason=1h_4h_conflict"
            )
            return (
                "neutral",
                max(0.0, confidence - self.conflict_penalty),
                "weak",
                f"higher_tf=1h:{trend_1h},4h:{trend_4h}; consensus=blocked",
            )
        if trend_1h == "neutral" or trend_4h == "neutral":
            confidence = max(0.0, confidence - (self.conflict_penalty * 0.5))

        if bullish_higher and bearish_higher:
            conflicts = sorted(bullish_higher + bearish_higher)
            confidence = max(0.0, confidence - self.conflict_penalty)

        if confidence < self.min_confidence or score == 0:
            return "neutral", confidence, "weak", "higher_tf=mixed; consensus=neutral"

        trend = "bullish" if score > 0 else "bearish"
        aligned_higher = [
            timeframe
            for timeframe in ("1h", "4h", "1d")
            if signals_by_interval.get(timeframe, {}).get("trend") == trend
        ]
        if "1h" in aligned_higher and "4h" in aligned_higher:
            confidence = min(1.0, confidence + self.higher_timeframe_boost)

        ta_alignment = self._get_ta_alignment(trend, symbol)
        confidence = min(1.0, max(0.0, confidence + ta_alignment["boost"]))
        signal_strength = self._signal_strength_label(confidence, trend)
        avg_momentum = sum(
            sig.get("confidence", 0.0) for sig in signals_by_interval.values()
        ) / max(len(signals_by_interval), 1)
        reasoning = (
            f"higher_tf={'/'.join(aligned_higher) if aligned_higher else 'none'}; "
            f"conflicts={','.join(conflicts) if conflicts else 'none'}; "
            f"momentum_avg={avg_momentum:.2f}; {ta_alignment['reasoning']}"
        )
        return trend, confidence, signal_strength, reasoning

    def _is_signal_complete(self, signals_by_interval: dict[str, dict]) -> bool:
        return set(self.signal_intervals).issubset(set(signals_by_interval.keys()))

    def _cluster_for_market(self, market_name: str) -> str:
        lowered = market_name.lower()
        if "bitcoin" in lowered or "btc" in lowered:
            return "BTC"
        return "NON_BTC"

    def _symbol_for_market(self, market_name: str) -> str:
        normalized = _normalize_text(market_name)
        for symbol, keywords in SYMBOL_KEYWORDS.items():
            if symbol not in self.symbols:
                continue
            if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords):
                return symbol
        return self.binance.symbol

    def _detect_market_timeframe(self, market_name: str) -> str | None:
        normalized = _normalize_text(market_name)
        for timeframe, pattern in self.allowed_market_timeframes.items():
            if re.search(pattern, normalized):
                return timeframe
        return None

    def _is_supported_up_down_market(self, market_name: str) -> bool:
        normalized = _normalize_text(market_name)
        has_direction = any(
            token in normalized
            for token in [" up ", " down ", " higher ", " lower ", "increase", "decrease"]
        )
        if not has_direction:
            padded = f" {normalized} "
            has_direction = any(
                token in padded
                for token in [" up ", " down ", " higher ", " lower "]
            )
        return has_direction

    def _validate_freshness(self, market: dict, signal_snapshot: dict) -> tuple[bool, str]:
        if _age_seconds(signal_snapshot["timestamp"]) > self.max_signal_age_seconds:
            return False, "stale_signal"
        if _age_seconds(market["fetched_at"]) > self.max_market_age_seconds:
            return False, "stale_market"
        return True, "ok"

    def _build_signal_snapshot(self, symbol: str | None = None) -> dict | None:
        """Fetch the latest Binance price and multi-timeframe trends."""
        active_symbol = symbol or self.binance.symbol
        client = self._binance_clients.get(active_symbol, self.binance)
        price = client.get_price()
        if price is None:
            return None

        timestamp = datetime.utcnow().isoformat()
        signals_by_interval = {}
        for signal_interval in self.signal_intervals:
            interval_analysis = client.analyze_trend(
                interval=signal_interval,
                neutral_band_pct=self.signal_neutral_band_pct,
                momentum_scale=self.momentum_scale,
            )
            signal = {
                "source": f"binance:{signal_interval}",
                "interval": signal_interval,
                "trend": interval_analysis["trend"],
                "confidence": min(self.confidence_cap, float(interval_analysis["confidence"])),
                "reasoning": interval_analysis["reasoning"],
                "move_pct": interval_analysis["move_pct"],
                "value": price,
                "timestamp": timestamp,
            }
            signals_by_interval[signal_interval] = signal

        if not self._is_signal_complete(signals_by_interval):
            return None

        consensus, confidence, signal_strength, reasoning = self._combine_trends(
            signals_by_interval,
            symbol=active_symbol,
        )
        regime = self._infer_regime(signals_by_interval)
        micro_data = self._build_micro_data(active_symbol)

        return {
            "source": "binance",
            "trend": consensus,
            "confidence": confidence,
            "signal_strength": signal_strength,
            "reasoning": reasoning,
            "regime": regime,
            "value": price,
            "timestamp": timestamp,
            "timeframes": signals_by_interval,
            "micro_data": micro_data,
        }

    def _build_micro_data(self, symbol: str | None = None) -> dict:
        active_symbol = symbol or self.binance.symbol
        client = self._binance_clients.get(active_symbol, self.binance)
        candles_1m = client.get_klines(interval="1m", limit=20)
        candles_5m = client.get_klines(interval="5m", limit=8)
        source = candles_1m[:-1] if len(candles_1m) >= 6 else candles_5m[:-1]

        if len(source) < 4:
            return {
                "symbol": active_symbol,
                "time_horizon": "scalp",
                "move_pct_short": 0.0,
                "volume_spike": False,
                "volume_ratio": 0.0,
                "spread_bps": 999.0,
                "source_interval": "1m" if len(candles_1m) >= 6 else "5m",
            }

        recent = source[-3:]
        start_price = float(recent[0]["open"] or 0.0)
        end_price = float(recent[-1]["close"] or 0.0)
        move_pct_short = ((end_price - start_price) / start_price) if start_price > 0 else 0.0
        latest_volume = float(recent[-1]["volume"] or 0.0)
        avg_volume = sum(float(candle["volume"] or 0.0) for candle in source[-10:]) / max(min(len(source), 10), 1)
        volume_ratio = (latest_volume / avg_volume) if avg_volume > 0 else 0.0
        volume_spike = volume_ratio >= 1.8
        latest_close = float(recent[-1]["close"] or 0.0)
        latest_high = float(recent[-1]["high"] or latest_close)
        latest_low = float(recent[-1]["low"] or latest_close)
        spread_bps = ((latest_high - latest_low) / latest_close) * 10000.0 if latest_close > 0 else 999.0

        return {
            "symbol": active_symbol,
            "time_horizon": "scalp",
            "move_pct_short": move_pct_short,
            "volume_spike": volume_spike,
            "volume_ratio": volume_ratio,
            "spread_bps": spread_bps,
            "source_interval": "1m" if len(candles_1m) >= 6 else "5m",
        }

    def _persist_signal_snapshot(self, signal_snapshot: dict, symbol: str | None = None):
        """Store per-timeframe signals in the database."""
        active_symbol = symbol or self.binance.symbol
        regime = str(signal_snapshot.get("regime") or "CHOP")
        strategy = self._select_strategy(
            trend=str(signal_snapshot.get("trend") or "neutral"),
            confidence=float(signal_snapshot.get("confidence") or 0.0),
            regime=regime,
            micro_data=signal_snapshot.get("micro_data"),
        )
        strategy = normalize_strategy(strategy)
        self.latest_micro_data[active_symbol] = dict(signal_snapshot.get("micro_data") or {})

        has_htf_conflict = "conflicts=" in str(signal_snapshot.get("reasoning") or "") and "none" not in str(signal_snapshot.get("reasoning") or "")
        ta_disagreement = "ta=conflict" in str(signal_snapshot.get("reasoning") or "")
        context_stats = self._expected_probability(
            symbol=active_symbol,
            timeframe="consensus",
            strategy=strategy,
            signal_strength=str(signal_snapshot.get("signal_strength") or "weak"),
            regime=regime,
        )

        normalized_confidence = self._normalize_confidence(
            float(signal_snapshot.get("confidence") or 0.0),
            has_htf_conflict=has_htf_conflict,
            ta_disagreement=ta_disagreement,
            sample_size=int(context_stats.get("sample_size") or 0),
        )
        adjusted_confidence = self._apply_strategy_confidence_adjustment(
            normalized_confidence,
            strategy,
        )
        adjusted_confidence = self._apply_signal_scarcity(
            adjusted_confidence,
            strategy,
            active_symbol,
        )
        signal_snapshot["base_confidence"] = float(signal_snapshot.get("confidence") or 0.0)
        signal_snapshot["confidence"] = adjusted_confidence
        sequence_id = self.db.insert_signal_sequence(
            symbol=active_symbol,
            consensus=signal_snapshot["trend"],
            confidence=signal_snapshot.get("confidence", 0.0),
            signal_strength=signal_snapshot.get("signal_strength"),
            reasoning=signal_snapshot.get("reasoning"),
            timestamp=signal_snapshot["timestamp"],
            strategy=strategy,
            regime=regime,
        )
        signal_snapshot["signal_sequence_id"] = sequence_id
        signal_snapshot["strategy"] = strategy
        self.last_signal_sequence_id = sequence_id
        self.db.set_bot_state("last_signal_sequence_id", str(sequence_id))

        for signal in signal_snapshot["timeframes"].values():
            self.db.insert_signal(
                signal["source"],
                signal["trend"],
                signal["value"],
                sequence_id=sequence_id,
                timeframe=signal["interval"],
                confidence=signal.get("confidence"),
                signal_strength=signal_snapshot.get("signal_strength"),
                reasoning=signal.get("reasoning"),
                move_pct=signal.get("move_pct"),
                regime=regime,
                timestamp=signal["timestamp"],
                symbol=active_symbol,
                strategy=strategy,
            )

        direction = self._direction_from_trend(signal_snapshot.get("trend", "neutral"))
        # NOTE: simulation.on_signal is now handled per-strategy by StrategyWorker
        # via _dispatch_directional_workers called from _poll_binance.
        _ = direction  # retained for orchestrated-decision use below

        orchestrated = self.orchestrator.output_decision(
            active_symbol,
            signal_snapshot,
            ta_alignment=0.0,
            market_summary=None,
            micro_data=signal_snapshot.get("micro_data"),
        )
        self.latest_orchestrated_decisions[active_symbol] = orchestrated
        self.db.set_bot_state(
            f"orchestrated_decision:{active_symbol}",
            json.dumps(orchestrated),
        )

    def _expected_probability(self, signal_snapshot: dict | None = None, **context) -> dict:
        """Backward-compatible wrapper for calibrated expected probability lookup."""
        if signal_snapshot is not None and not context:
            inferred_symbol = str(signal_snapshot.get("symbol") or self.binance.symbol)
            inferred_timeframe = str(signal_snapshot.get("timeframe") or "consensus")
            inferred_strategy = normalize_strategy(str(signal_snapshot.get("strategy") or "ta_confluence"))
            inferred_strength = str(signal_snapshot.get("signal_strength") or "weak")
            inferred_regime = str(signal_snapshot.get("regime") or "CHOP")
            return self.db.get_historical_win_rate(
                symbol=inferred_symbol,
                timeframe=inferred_timeframe,
                strategy=inferred_strategy,
                signal_strength=inferred_strength,
                regime=inferred_regime,
                min_samples=self.low_sample_threshold,
            )

        return self.db.get_historical_win_rate(
            symbol=str(context.get("symbol") or self.binance.symbol),
            timeframe=str(context.get("timeframe") or "consensus"),
            strategy=normalize_strategy(str(context.get("strategy") or "ta_confluence")),
            signal_strength=str(context.get("signal_strength") or "weak"),
            regime=str(context.get("regime") or "CHOP"),
            min_samples=self.low_sample_threshold,
        )

    # ── Trade logic ─────────────────────────────────────────────────────────────

    def _evaluate_arbitrage(self, market: dict, market_id: int, symbol: str | None = None):
        """
        Pure arbitrage check: if YES + NO < arb_threshold, buy both sides.

        At settlement exactly one token pays 1.0 USDC, so buying both when
        their sum is < 1 guarantees a risk-free profit equal to (1 - sum).

        In paper trading mode the trade is recorded but no order is submitted.
        """
        combined = (market["yes_price"] or 0) + (market["no_price"] or 0)
        if combined < self.arb_threshold:
            msg = (
                f"[ARB] {market['market_name']}: "
                f"YES={market['yes_price']:.4f} + NO={market['no_price']:.4f}"
                f" = {combined:.4f} < threshold {self.arb_threshold}"
            )
            self._log(msg)
            signal_snapshot = {
                "signal_sequence_id": self.last_signal_sequence_id or 0,
                "trend": "neutral",
                "confidence": 1.0,
                "signal_strength": "strong",
                "timestamp": datetime.utcnow().isoformat(),
                "strategy": "yes_no",
            }
            reasoning = (
                f"combined={combined:.4f} below arb_threshold={self.arb_threshold:.4f}; "
                "paired YES/NO pricing implies locked spread"
            )
            active_symbol = symbol or self.binance.symbol
            if self.emit_signals_only:
                self._record_signal_opportunity(
                    market,
                    side="YES",
                    signal_snapshot=signal_snapshot,
                    reason_code="arb_gap_yes",
                    timeframe="consensus",
                    reasoning=reasoning,
                    symbol=active_symbol,
                    strategy="yes_no",
                )
                self._record_signal_opportunity(
                    market,
                    side="NO",
                    signal_snapshot=signal_snapshot,
                    reason_code="arb_gap_no",
                    timeframe="consensus",
                    reasoning=reasoning,
                    symbol=active_symbol,
                    strategy="yes_no",
                )
                return
            self._execute_trade(market_id, market, "YES", signal_snapshot)
            self._execute_trade(market_id, market, "NO", signal_snapshot)

    def _evaluate_fair_value_arb(
        self,
        market: dict,
        market_row_id: int,
        symbol: str | None = None,
    ):
        """
        Run FairValueEngine probability estimation for a market and persist results.

        Always called for every supported up/down market regardless of trading mode.
        Stores:
          - market_fair_values: per-market p_model vs p_mkt snapshot.
          - arbitrage_opportunities: when edge exceeds model_vs_market threshold.

        For model_vs_market opportunities, also routes into the standard
        _record_signal_opportunity pipeline so they appear on the dashboard.
        """
        active_symbol = symbol or self.binance.symbol
        with self._lock:
            signal_snapshot = self.latest_signals.get(active_symbol, {}).copy()
            perp_context = self.latest_perp_context.get(active_symbol, {}).copy()
        if not signal_snapshot:
            return

        ta_features: dict | None = None
        if self.scanner is not None:
            ta_align = self._get_ta_alignment(
                str(signal_snapshot.get("trend") or "neutral"), active_symbol
            )
            ta_features = {"boost": ta_align.get("boost", 0.0)}

        try:
            result = self.fair_value_engine.estimate(
                signal_snapshot=signal_snapshot,
                market=market,
                ta_features=ta_features,
                perp_context=perp_context,
            )
        except Exception as exc:
            self._log(
                f"[FVE] Estimation error for {market.get('market_name', '?')}: {exc}",
                level="WARNING",
            )
            return

        self.db.insert_fair_value(
            market_id=str(market.get("market_id") or ""),
            market_name=str(market.get("market_name") or ""),
            p_model=result.p_model,
            p_fair=result.p_fair,
            p_mkt=result.p_mkt,
            edge_bp=result.edge_bp,
            arb_type=result.arb_type,
            symbol=active_symbol,
            signal_sequence_id=int(
                signal_snapshot.get("signal_sequence_id")
                or self.last_signal_sequence_id
                or 0
            ),
        )

        orchestrated = self.orchestrator.output_decision(
            active_symbol,
            signal_snapshot,
            ta_alignment=float(ta_features.get("boost") or 0.0) if ta_features else 0.0,
            market_summary={
                "best_edge": abs(result.edge_bp) / 10_000.0,
                "best_side": "YES" if result.edge_bp > 0 else "NO",
                "arb_type": result.arb_type,
                "market_name": str(market.get("market_name") or ""),
            },
            fv_result=result,
            perp_context=perp_context,
            micro_data=signal_snapshot.get("micro_data"),
        )
        self.latest_orchestrated_decisions[active_symbol] = orchestrated
        self.db.set_bot_state(
            f"orchestrated_decision:{active_symbol}",
            json.dumps(orchestrated),
        )

        if not result.is_opportunity:
            return

        self._log(
            f"[FVE] {result.arb_type} | {market.get('market_name', '')} | "
            f"p_model={result.p_model:.3f} p_mkt={result.p_mkt:.3f} "
            f"edge={result.edge_bp:+d}bp"
        )

        self.db.insert_arb_opportunity(
            market_id=str(market.get("market_id") or ""),
            market_name=str(market.get("market_name") or ""),
            arb_type=result.arb_type,
            p_fair=result.p_fair,
            p_mkt=result.p_mkt,
            edge_bp=result.edge_bp,
            strategy="volatility" if result.arb_type == "model_vs_market" else "funding_arb",
            why=result.why,
            venue="hyperliquid",
            symbol=active_symbol,
            signal_sequence_id=int(
                signal_snapshot.get("signal_sequence_id")
                or self.last_signal_sequence_id
                or 0
            ),
        )

        if result.arb_type != "model_vs_market":
            return

        horizon, _ = self._market_horizon(market)
        if horizon == "long" and self.block_long_horizon_markets:
            return

        side = "YES" if result.edge_bp > 0 else "NO"

        local_snapshot = {
            "signal_sequence_id": (
                signal_snapshot.get("signal_sequence_id") or self.last_signal_sequence_id or 0
            ),
            "trend": str(signal_snapshot.get("trend") or "neutral"),
            "confidence": result.confidence,
            "signal_strength": signal_snapshot.get("signal_strength") or "weak",
            "timestamp": datetime.utcnow().isoformat(),
            "reasoning": signal_snapshot.get("reasoning") or "",
            "regime": str(signal_snapshot.get("regime") or "CHOP"),
        }
        timeframe = self._detect_market_timeframe(market.get("market_name", "")) or "1d"
        self._record_signal_opportunity(
            market=market,
            side=side,
            signal_snapshot=local_snapshot,
            reason_code=f"fve_model_vs_market_{side.lower()}",
            timeframe=timeframe,
            reasoning=result.why,
            symbol=active_symbol,
            strategy="model_vs_market",
        )

    def _record_signal_opportunity(
        self,
        market: dict,
        side: str,
        signal_snapshot: dict,
        reason_code: str,
        timeframe: str,
        reasoning: str,
        symbol: str | None = None,
        strategy: str | None = None,
    ):
        active_symbol = symbol or self.binance.symbol
        active_strategy = strategy or self._select_strategy(
            trend=str(signal_snapshot.get("trend") or "neutral"),
            confidence=float(signal_snapshot.get("confidence") or 0.0),
            regime=str(signal_snapshot.get("regime") or "CHOP"),
            reason_code=reason_code,
            micro_data=signal_snapshot.get("micro_data"),
        )
        active_strategy = normalize_strategy(active_strategy)
        yes_price = float(market.get("yes_price") or 0.0)
        no_price = float(market.get("no_price") or 0.0)
        combined_price = yes_price + no_price
        gap_to_parity = 1.0 - combined_price
        base_confidence = float(signal_snapshot.get("confidence", 0.0))
        signal_strength = str(signal_snapshot.get("signal_strength") or "weak")
        regime = str(signal_snapshot.get("regime") or "CHOP")
        signal_sequence_id = int(signal_snapshot.get("signal_sequence_id", 0))
        market_price = yes_price if side == "YES" else no_price

        horizon, _ = self._market_horizon(market)
        if horizon == "long" and self.block_long_horizon_markets:
            self._log(
                f"[SIGNAL_SKIP] {market.get('market_name', 'unknown')} {side} blocked for long horizon",
                level="INFO",
            )
            return

        expected_stats = self._expected_probability(
            symbol=active_symbol,
            timeframe=timeframe,
            strategy=active_strategy,
            signal_strength=signal_strength,
            regime=regime,
        )
        expected_yes = float(expected_stats.get("win_rate") or 0.5)
        expected_side = expected_yes if side == "YES" else (1.0 - expected_yes)
        edge = self._edge_from_context(expected_side, market_price)

        horizon_multiplier = self._horizon_confidence_multiplier(horizon)
        edge = max(0.0, min(0.10, edge * horizon_multiplier))
        confidence = self._normalize_confidence(
            base_confidence,
            has_htf_conflict="conflicts=" in str(signal_snapshot.get("reasoning") or "") and "none" not in str(signal_snapshot.get("reasoning") or ""),
            ta_disagreement="ta=conflict" in str(signal_snapshot.get("reasoning") or ""),
            sample_size=int(expected_stats.get("sample_size") or 0),
        )
        confidence = max(0.0, min(self.confidence_cap, confidence * horizon_multiplier))
        confidence = self._apply_strategy_confidence_adjustment(confidence, active_strategy)
        # REMOVED: duplicate scarcity pass
        # confidence = self._apply_signal_scarcity(confidence, active_strategy, active_symbol)

        min_edge = self._strategy_min_edge(active_strategy)
        if edge <= min_edge:
            self._log(
                f"[SIGNAL_SKIP] {market.get('market_name', 'unknown')} {side} tf={timeframe} edge={edge:.4f} <= min_edge={min_edge:.4f} reason={reason_code}",
                level="INFO",
            )
            return
        time_bucket = int(time.time() // self.trade_bucket_seconds)
        opportunity_key = (
            f"{market.get('market_id', '')}:{timeframe}:{side}:"
            f"{signal_sequence_id}:{time_bucket}"
        )

        inserted, opportunity_id = self.db.insert_opportunity_if_not_exists(
            opportunity_key=opportunity_key,
            market_id=str(market.get("market_id") or ""),
            market_name=str(market.get("market_name") or "unknown"),
            signal_sequence_id=signal_sequence_id,
            timeframe=timeframe,
            trend=str(signal_snapshot.get("trend") or "neutral"),
            confidence=confidence,
            signal_strength=signal_strength,
            side=side,
            yes_price=yes_price,
            no_price=no_price,
            combined_price=combined_price,
            gap_to_parity=gap_to_parity,
            edge=edge,
            signal_threshold=float(self.signal_threshold),
            reason_code=reason_code,
            reasoning=f"{reasoning}; horizon={horizon}; expected_source={expected_stats.get('source')}; n={expected_stats.get('sample_size', 0)}",
            symbol=active_symbol,
            strategy=active_strategy,
        )
        if not inserted:
            return
        self._log(
            f"[SIGNAL_ONLY] id={opportunity_id} {market.get('market_name', 'unknown')} -> {side} "
            f"tf={timeframe} "
            f"trend={signal_snapshot.get('trend', 'neutral')} conf={confidence:.2f} strength={signal_strength} "
            f"edge={edge:.4f} yes={yes_price:.4f} no={no_price:.4f} gap={gap_to_parity:.4f} why={reasoning}"
        )

    def _evaluate_signal(
        self,
        market: dict,
        market_row_id: int,
        signal_snapshot: dict,
        symbol: str | None = None,
    ):
        """
        Signal-enhanced entry: use BTC momentum to pick a direction.

        - Bullish BTC → buy YES tokens when price < signal_threshold (risk-on)
        - Bearish BTC → buy NO tokens when price < signal_threshold  (risk-off)
        - Neutral     → skip (no clear edge)

        The signal_threshold acts as an entry filter — only buy at "cheap" prices.
        """
        market_timeframe = self._detect_market_timeframe(market.get("market_name", "")) or "1d"
        horizon, _ = self._market_horizon(market)
        if horizon == "long" and self.block_long_horizon_markets:
            self._log(
                f"Trade blocked: long_horizon market_id={market['market_id']}",
                level="INFO",
            )
            return
        horizon_multiplier = self._horizon_confidence_multiplier(horizon)

        per_tf_signal = (signal_snapshot.get("timeframes") or {}).get(market_timeframe)
        if per_tf_signal is None:
            return

        trend = per_tf_signal.get("trend", "neutral")
        if trend == "neutral":
            return

        is_fresh, freshness_reason = self._validate_freshness(market, signal_snapshot)
        if not is_fresh:
            self._log(
                f"Trade blocked: {freshness_reason} market_id={market['market_id']}",
                level="WARNING",
            )
            return

        if trend == "bullish":
            reasoning = (
                f"tf={market_timeframe} aligns bullish; move={per_tf_signal.get('move_pct', 0.0):.4f}; "
                f"signal={signal_snapshot.get('signal_strength', 'weak')} conf={signal_snapshot.get('confidence', 0.0):.2f}; "
                f"{signal_snapshot.get('reasoning', 'no-consensus-reason')}"
            )
            self._log(
                f"[SIGNAL] Bullish BTC → YES candidate on '{market['market_name']}'"
                f" @ {market['yes_price']:.4f} why={reasoning}"
            )
            if self.emit_signals_only:
                local_signal_snapshot = {
                    "signal_sequence_id": signal_snapshot.get("signal_sequence_id", 0),
                    "trend": trend,
                    "confidence": float(signal_snapshot.get("confidence", 0.0)) * horizon_multiplier,
                    "signal_strength": signal_snapshot.get("signal_strength", "weak"),
                    "timestamp": signal_snapshot.get("timestamp"),
                    "reasoning": signal_snapshot.get("reasoning", ""),
                    "regime": signal_snapshot.get("regime", "CHOP"),
                    "micro_data": signal_snapshot.get("micro_data") or {},
                    "strategy": signal_snapshot.get("strategy"),
                }
                self._record_signal_opportunity(
                    market,
                    side="YES",
                    signal_snapshot=local_signal_snapshot,
                    reason_code=f"trend_bullish_yes_{market_timeframe}",
                    timeframe=market_timeframe,
                    reasoning=reasoning,
                    symbol=symbol,
                    strategy=self._select_strategy(
                        trend=trend,
                        confidence=float(local_signal_snapshot.get("confidence") or 0.0),
                        regime=str(signal_snapshot.get("regime") or "CHOP"),
                        reason_code=f"trend_bullish_yes_{market_timeframe}",
                        micro_data=local_signal_snapshot.get("micro_data"),
                    ),
                )
            else:
                self._execute_trade(market_row_id, market, "YES", signal_snapshot)
        elif trend == "bearish":
            reasoning = (
                f"tf={market_timeframe} aligns bearish; move={per_tf_signal.get('move_pct', 0.0):.4f}; "
                f"signal={signal_snapshot.get('signal_strength', 'weak')} conf={signal_snapshot.get('confidence', 0.0):.2f}; "
                f"{signal_snapshot.get('reasoning', 'no-consensus-reason')}"
            )
            self._log(
                f"[SIGNAL] Bearish BTC → NO candidate on '{market['market_name']}'"
                f" @ {market['no_price']:.4f} why={reasoning}"
            )
            if self.emit_signals_only:
                local_signal_snapshot = {
                    "signal_sequence_id": signal_snapshot.get("signal_sequence_id", 0),
                    "trend": trend,
                    "confidence": float(signal_snapshot.get("confidence", 0.0)) * horizon_multiplier,
                    "signal_strength": signal_snapshot.get("signal_strength", "weak"),
                    "timestamp": signal_snapshot.get("timestamp"),
                    "reasoning": signal_snapshot.get("reasoning", ""),
                    "regime": signal_snapshot.get("regime", "CHOP"),
                    "micro_data": signal_snapshot.get("micro_data") or {},
                    "strategy": signal_snapshot.get("strategy"),
                }
                self._record_signal_opportunity(
                    market,
                    side="NO",
                    signal_snapshot=local_signal_snapshot,
                    reason_code=f"trend_bearish_no_{market_timeframe}",
                    timeframe=market_timeframe,
                    reasoning=reasoning,
                    symbol=symbol,
                    strategy=self._select_strategy(
                        trend=trend,
                        confidence=float(local_signal_snapshot.get("confidence") or 0.0),
                        regime=str(signal_snapshot.get("regime") or "CHOP"),
                        reason_code=f"trend_bearish_no_{market_timeframe}",
                        micro_data=local_signal_snapshot.get("micro_data"),
                    ),
                )
            else:
                self._execute_trade(market_row_id, market, "NO", signal_snapshot)

    def _execute_trade(
        self,
        market_row_id: int,
        market: dict,
        trade_type: str,
        signal_snapshot: dict,
    ):
        """
        Submit or simulate a trade.

        Quantity is calculated as: trade_size_usdc / price.

        In paper trading mode:
          - Trade is written to the DB for tracking and PnL analysis.
          - No real order is sent.
        In live mode:
          - TODO: integrate Polymarket CLOB API order submission here.
        """
        assert self.execution_mode == "paper", (
            "SAFETY: execution_mode must be 'paper'. Refusing to submit trade."
        )
        strategy = normalize_strategy(str(signal_snapshot.get("strategy") or "ta_confluence"))
        signal_strength = str(signal_snapshot.get("signal_strength") or "weak")
        confidence = float(signal_snapshot.get("confidence") or 0.0)
        micro_data = signal_snapshot.get("micro_data") or {}

        if strategy == "scalping":
            spread_bps = float(micro_data.get("spread_bps") or 0.0)
            volume_spike = bool(micro_data.get("volume_spike"))
            if spread_bps > 15.0:
                self._log(
                    f"Trade blocked: scalping spread_too_high={spread_bps:.2f}bp market_id={market.get('market_id')}",
                    level="INFO",
                )
                return
            if not volume_spike:
                self._log(
                    f"Trade blocked: scalping requires volume_spike market_id={market.get('market_id')}",
                    level="INFO",
                )
                return

        side_market_price = float(market.get("yes_price") if trade_type == "YES" else market.get("no_price") or 0.0)
        regime = str(signal_snapshot.get("regime") or "CHOP")
        timeframe = self._detect_market_timeframe(market.get("market_name", "")) or "1d"
        expected_stats = self._expected_probability(
            symbol=self._symbol_for_market(market.get("market_name", "")),
            timeframe=timeframe,
            strategy=strategy,
            signal_strength=signal_strength,
            regime=regime,
        )
        expected_yes = float(expected_stats.get("win_rate") or 0.5)
        expected_side = expected_yes if trade_type == "YES" else (1.0 - expected_yes)
        edge = self._edge_from_context(expected_side, side_market_price)
        # REMOVED: duplicate scarcity pass
        # confidence = self._apply_signal_scarcity(
        #     confidence,
        #     strategy,
        #     self._symbol_for_market(market.get("market_name", "")),
        # )
        risk_factor = self._risk_factor_for_setup(signal_strength, confidence)
        trade_notional = self._position_size_usdc(strategy, confidence, edge, risk_factor)
        if trade_notional <= 0:
            self._log(
                f"Trade blocked: calibrated_size=0 market_id={market['market_id']} strategy={strategy}",
                level="INFO",
            )
            return
        reference_price = side_market_price
        if reference_price <= 0:
            self._log(
                f"Trade blocked: invalid_reference_price market_id={market['market_id']} side={trade_type}",
                level="WARNING",
            )
            return
        quantity = trade_notional / reference_price
        market_id = market["market_id"]
        market_name = market["market_name"]
        signal_sequence_id = int(signal_snapshot.get("signal_sequence_id", 0))
        time_bucket = int(time.time() // self.trade_bucket_seconds)
        trade_key = f"{market_id}:{trade_type}:{signal_sequence_id}:{time_bucket}"

        execution_market = dict(market)
        execution_market["mark_price"] = reference_price
        execution_market.setdefault("best_ask", reference_price)
        execution_market.setdefault("best_bid", reference_price)

        if self.db.has_recent_trade(market_id, trade_type, self.cooldown_seconds):
            self._log(
                f"Trade blocked: cooldown market_id={market_id} side={trade_type}",
                level="INFO",
            )
            return

        bot_type = str(signal_snapshot.get("bot_type") or strategy_domain(strategy))
        venue = "hyperliquid"
        instrument_type = "perp"

        cluster = self._cluster_for_market(market_name)
        total_exposure = self.db.get_total_open_exposure_usdc()
        market_exposure = self.db.get_market_open_exposure_usdc(market_id)
        cluster_exposure = self.db.get_cluster_open_exposure_usdc(cluster)
        risk_result = self.risk_engine.can_add_to_position(
            total_exposure,
            market_exposure,
            cluster_exposure,
            trade_notional,
            venue=venue,
        )
        if not risk_result.allowed:
            self._log(
                f"Trade blocked: {risk_result.reason_code} market_id={market_id}",
                level="WARNING",
            )
            return

        assert self.config.get("execution_mode") == "paper", (
            "SAFETY: execution_mode must be 'paper'. Refusing to route trade."
        )
        trade_intent = {
            "market_row_id": market_row_id,
            "market_id": market_id,
            "market_name": market_name,
            "side": trade_type,
            "signal_sequence_id": signal_sequence_id,
            "trade_key": trade_key,
            "quantity": quantity,
            "notional_usdc": trade_notional,
            "reason_code": "signal_consensus",
            "strategy": strategy,
            "bot_type": bot_type,
            "venue": venue,
            "instrument_type": instrument_type,
        }

        execution_client = self.hyperliquid_execution_client
        execution = execution_client.submit(
            trade_intent=trade_intent,
            market=execution_market,
        )
        if not execution.accepted:
            level = "INFO" if execution.reason_code == "duplicate_trade_key" else "WARNING"
            self._log(
                f"Trade blocked: {execution.reason_code} market_id={market_id}",
                level=level,
            )
            return
        exec_price = float(execution.execution_price or 0.0)
        self._log(
            f"[PAPER] id={execution.trade_id} {trade_type} | price={exec_price:.4f}"
            f" | qty={quantity:.4f} | value={trade_notional:.2f} USDC"
        )
        self.db.insert_simulated_trade_open(
            symbol=str(market.get("market_id") or market_id),
            strategy=strategy,
            direction=1 if trade_type == "YES" else -1,
            entry_price=exec_price,
            size=trade_notional,
            confidence=confidence,
            edge=edge,
            source="hyperliquid_paper",
            venue=venue,
            status="open",
            instrument_type=instrument_type,
        )

    # ── Polling threads ─────────────────────────────────────────────────────────

    # Ordered lists used by the two dispatch methods below.
    _DIRECTIONAL_STRATEGIES = (
        "trend", "momentum", "ta_confluence", "reversal",
        "breakout", "mean_reversion", "scalping",
    )
    _ARB_STRATEGIES = ("funding_arb", "basis_arb")

    def _dispatch_directional_workers(self, signal_snapshot: dict, symbol: str) -> None:
        """
        Fan out a Binance signal to all 7 directional strategy workers.

        Each worker independently evaluates its own entry criteria and calls
        simulation.on_signal only if its strategy-specific conditions are met.
        """
        for strategy_name in self._DIRECTIONAL_STRATEGIES:
            worker = self._strategy_workers.get(strategy_name)
            if not worker:
                continue
            try:
                should_enter, direction, reason = worker.evaluate_directional(signal_snapshot, symbol)
                if not should_enter:
                    continue
                confidence = float(signal_snapshot.get("confidence") or 0.0)
                signal_strength = str(signal_snapshot.get("signal_strength") or "weak")
                regime = str(signal_snapshot.get("regime") or "CHOP")
                spread_bps = float((signal_snapshot.get("micro_data") or {}).get("spread_bps") or 0.0)
                self.simulation.on_signal(
                    symbol=symbol,
                    strategy=strategy_name,
                    direction=direction,
                    entry_price=float(signal_snapshot.get("value") or 0.0),
                    timestamp=signal_snapshot["timestamp"],
                    signal_strength=signal_strength,
                    regime=regime,
                    timeframe="consensus",
                    confidence=confidence,
                    edge=max(self.min_edge, 0.01),
                    risk_factor=self._risk_factor_for_setup(signal_strength, confidence),
                    max_duration_minutes=15 if strategy_name == "scalping" else None,
                    spread_bps=spread_bps,
                )
                worker.set_cooldown(symbol, float(self.cooldown_seconds))
                self._log(
                    f"[WORKER:{strategy_name}] {symbol} dir={direction:+d} "
                    f"conf={confidence:.2f} | {reason}"
                )
            except Exception as exc:
                self._log(
                    f"Directional worker error ({strategy_name}/{symbol}): {exc}",
                    level="ERROR",
                )

    def _dispatch_arb_workers(self, perp_context: dict, symbol: str) -> None:
        """
        Fan out Hyperliquid perp context to both arb strategy workers.

        funding_arb reacts to funding-rate spreads.
        basis_arb reacts to cross-venue price divergence.
        """
        perp_arb_cfg = self.config.get("perp_arb", {})
        min_funding_spread = float(perp_arb_cfg.get("min_funding_spread", 0.0001))
        min_basis_bp = float(perp_arb_cfg.get("cross_venue_threshold_bp", 5.0))
        exit_bp = float(perp_arb_cfg.get("exit_threshold_bp", 2.0))
        stop_bp = float(perp_arb_cfg.get("stop_loss_bp", 20.0))

        for strategy_name in self._ARB_STRATEGIES:
            worker = self._strategy_workers.get(strategy_name)
            if not worker:
                continue
            try:
                should_enter, direction, reason = worker.evaluate_arb(
                    perp_context, symbol, min_funding_spread, min_basis_bp
                )
                if not should_enter:
                    continue

                fund_spread = float(perp_context.get("funding_spread") or 0.0)
                basis_diff = float(perp_context.get("basis_diff") or 0.0)
                hl_perp = float(perp_context.get("hl_perp_price") or 1.0)
                bin_perp = float(perp_context.get("binance_perp_price") or 0.0)

                edge_bp = (
                    abs(fund_spread) * 10_000
                    if strategy_name == "funding_arb"
                    else abs(basis_diff / max(hl_perp, bin_perp, 1.0)) * 10_000
                )
                confidence = min(0.85, 0.4 + edge_bp / 200.0)
                signal_strength = "medium" if confidence >= 0.5 else "weak"

                self.simulation.on_pair_signal(
                    symbol=symbol,
                    strategy=strategy_name,
                    direction=direction,
                    binance_price=bin_perp,
                    hl_price=hl_perp,
                    funding_spread=fund_spread,
                    timestamp=datetime.utcnow().isoformat(),
                    signal_strength=signal_strength,
                    regime="ARB",
                    confidence=confidence,
                    edge_bp=edge_bp,
                    risk_factor=self._risk_factor_for_setup(signal_strength, confidence),
                    entry_threshold_bp=min_basis_bp,
                    exit_threshold_bp=exit_bp,
                    stop_loss_bp=stop_bp,
                )
                worker.set_cooldown(symbol, float(self.cooldown_seconds))
                self._log(
                    f"[WORKER:{strategy_name}] {symbol} dir={direction:+d} "
                    f"edge_bp={edge_bp:.1f} | {reason}"
                )
            except Exception as exc:
                self._log(
                    f"Arb worker error ({strategy_name}/{symbol}): {exc}",
                    level="ERROR",
                )

    def _poll_binance(self):
        """
        Background thread: sequentially fetch symbol price/trend on a fixed interval.

        Interval: config.json → binance.polling_interval_seconds (default 60 s).
        Stores each reading as a signal row in the DB and updates per-symbol state.
        """
        interval = self.config["binance"]["polling_interval_seconds"]
        self._log(
            "Binance poller started "
            f"(symbols={', '.join(self.symbols)}, interval={interval}s, "
            f"timeframes={', '.join(self.signal_intervals)})"
        )
        while self.running:
            cycle_start = time.time()
            for symbol in self.symbols:
                if not self.running:
                    break
                try:
                    signal_snapshot = self._build_signal_snapshot(symbol)
                    if signal_snapshot is not None:
                        self._persist_signal_snapshot(signal_snapshot, symbol)
                        self._dispatch_directional_workers(signal_snapshot, symbol)
                        with self._lock:
                            self.latest_signals[symbol] = signal_snapshot
                            if symbol == self.binance.symbol:
                                self.latest_signal = signal_snapshot
                        self._log(
                            f"Binance {symbol}={signal_snapshot['value']:,.2f} consensus={signal_snapshot['trend']} "
                            f"confidence={signal_snapshot['confidence']:.2f} strength={signal_snapshot['signal_strength']} why={signal_snapshot['reasoning']} "
                            + " ".join(
                                f"{signal_interval}={signal_snapshot['timeframes'][signal_interval]['trend']}({signal_snapshot['timeframes'][signal_interval]['confidence']:.2f})"
                                for signal_interval in self.signal_intervals
                            )
                        )
                except Exception as exc:
                    self._log(f"Binance polling error ({symbol}): {exc}", level="ERROR")

            elapsed = time.time() - cycle_start
            sleep_for = max(0.0, interval - elapsed)
            time.sleep(sleep_for)

    def _poll_hyperliquid(self):
        """
        Background thread: fetch Hyperliquid + Binance perp data and persist basis snapshots.

        Interval: config.json → hyperliquid.polling_interval_seconds (default 120 s).
        Updates self.latest_perp_context[symbol] with funding/basis data for FVE.
        """
        hl_cfg = self.config.get("hyperliquid", {})
        perp_arb_cfg = self.config.get("perp_arb", {})
        interval = int(hl_cfg.get("polling_interval_seconds", 120))
        cross_venue_threshold_bp = float(perp_arb_cfg.get("cross_venue_threshold_bp", 5.0))
        exit_threshold_bp = float(perp_arb_cfg.get("exit_threshold_bp", 2.0))
        stop_loss_bp = float(perp_arb_cfg.get("stop_loss_bp", 20.0))
        min_funding_spread = float(perp_arb_cfg.get("min_funding_spread", 0.0001))

        self._log(f"Hyperliquid poller started (interval={interval}s)")
        while self.running:
            try:
                hl_snapshots = self.hyperliquid.get_perp_snapshots()
                hl_by_symbol = {s.symbol: s for s in hl_snapshots}

                for symbol in self.symbols:
                    if not self.running:
                        break
                    client = self._binance_clients.get(symbol)
                    if not client:
                        continue

                    # Binance spot + perp
                    with self._lock:
                        sig = self.latest_signals.get(symbol, {})
                    bin_spot = float(sig.get("value") or 0.0)
                    bin_perp = client.get_perp_price()
                    bin_fund = client.get_funding_rate()

                    # Hyperliquid perp
                    hl_snap = hl_by_symbol.get(symbol)
                    hl_perp = hl_snap.mark_price if hl_snap else None
                    hl_fund = hl_snap.funding_rate if hl_snap else None
                    hl_oi = hl_snap.open_interest if hl_snap else None

                    # Derived metrics
                    basis_pct = ((bin_perp - bin_spot) / bin_spot) if (bin_perp and bin_spot) else 0.0
                    basis_diff = ((bin_perp or 0.0) - (hl_perp or 0.0))
                    funding_spread = ((bin_fund or 0.0) - (hl_fund or 0.0))

                    ctx: dict = {
                        "funding_rate":       bin_fund or 0.0,
                        "basis_pct":          basis_pct,
                        "binance_perp_price": bin_perp or 0.0,
                        "binance_spot_price": bin_spot,
                        "hl_perp_price":      hl_perp or 0.0,
                        "hl_funding_rate":    hl_fund or 0.0,
                        "hl_open_interest":   hl_oi or 0.0,
                        "basis_diff":         basis_diff,
                        "funding_spread":     funding_spread,
                    }

                    with self._lock:
                        self.latest_perp_context[symbol] = ctx

                    # Persist to DB for API / dashboard.
                    try:
                        self.db.insert_perp_basis(
                            symbol=symbol,
                            binance_spot_price=bin_spot or None,
                            binance_perp_price=bin_perp,
                            binance_funding_rate=bin_fund,
                            hl_perp_price=hl_perp,
                            hl_funding_rate=hl_fund,
                            hl_open_interest=hl_oi,
                        )
                    except Exception as exc:
                        self._log(f"DB perp_basis insert failed ({symbol}): {exc}", level="WARNING")

                    # Detect cross-venue / funding arb opportunities and dispatch workers.
                    if hl_perp and bin_perp:
                        ref = max(hl_perp, bin_perp, 1.0)
                        bp = abs(basis_diff / ref) * 10_000

                        # Workers (basis_arb + funding_arb) evaluate independently.
                        self._dispatch_arb_workers(ctx, symbol)

                        if bp >= cross_venue_threshold_bp:
                            self._log(
                                f"[PerpArb] {symbol} basis_arb basis={bp:.1f}bp "
                                f"bin={bin_perp:.2f} hl={hl_perp:.2f} "
                                f"fund_spread={funding_spread:.6f}"
                            )
                            try:
                                self.db.insert_arb_opportunity(
                                    market_id=f"perp_arb_{symbol}",
                                    market_name=f"{symbol} cross-venue perp basis",
                                    arb_type="basis_arb",
                                    p_fair=None,
                                    p_mkt=None,
                                    edge_bp=int(round(bp)),
                                    strategy="basis_arb",
                                    venue="hyperliquid",
                                    why=(
                                        f"Binance perp={bin_perp:.2f} HL perp={hl_perp:.2f} "
                                        f"basis={bp:.1f}bp fund_spread={funding_spread:.6f}"
                                    ),
                                    symbol=symbol,
                                    signal_sequence_id=self.last_signal_sequence_id or 0,
                                )
                            except Exception as exc:
                                self._log(f"DB arb_opp insert (perp) failed: {exc}", level="WARNING")
                        elif abs(funding_spread) >= min_funding_spread:
                            self._log(
                                f"[PerpArb] {symbol} funding_arb signal fund_spread={funding_spread:.6f} "
                                f"bin={bin_perp:.2f} hl={hl_perp:.2f}",
                                level="INFO",
                            )

            except Exception as exc:
                self._log(f"Hyperliquid polling error: {exc}", level="ERROR")
            time.sleep(interval)


    def _poll_polymarket(self):
        """Deprecated poller retained for compatibility in Hyperliquid-only mode."""
        self._log("Polymarket poller is disabled in Hyperliquid-only mode.", level="INFO")
        while self.running:
            time.sleep(1)

    # ── Lifecycle ────────────────────────────────────────────────────────────────

    def start(self):
        """Start all polling threads and mark the bot as running."""
        self.running = True
        self.bot_status = "running"
        self._log(
            f"TradingBot starting — mode={self.mode}, "
            f"paper_trading={self.paper_trading}, emit_signals_only={self.emit_signals_only}"
        )
        self._binance_thread = threading.Thread(
            target=self._poll_binance,
            daemon=True,
            name="BinancePoller",
        )
        self._poly_thread = None
        self._hl_thread = threading.Thread(
            target=self._poll_hyperliquid,
            daemon=True,
            name="HyperliquidPoller",
        )
        self._binance_thread.start()
        self._hl_thread.start()
        self._log("Polling threads started (Binance + Hyperliquid).")

    def stop(self):
        """Signal both polling threads to exit and update bot status."""
        self.running = False
        self.bot_status = "stopped"
        self._log("TradingBot stopped.")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = TradingBot()
    bot.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Bot shut down cleanly.")
