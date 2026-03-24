"""
hyperliquid_client.py — Hyperliquid perpetuals data client.

Fetches perp pricing, funding rates, and open interest for configured
symbols from the Hyperliquid public REST API.

Endpoint: POST https://api.hyperliquid.xyz/info
No API key required for public market data.

Usage:
    client = HyperliquidClient(symbols=["BTCUSDT", "ETHUSDT"])
    snapshots = client.get_perp_snapshots()   # list[HLPerpSnapshot]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Mapping from Binance-style trading pairs to Hyperliquid coin names.
HL_SYMBOL_MAP: dict[str, str] = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
    "BNBUSDT": "BNB",
    "ARBUSDT": "ARB",
    "AVAXUSDT": "AVAX",
    "MATICUSDT": "MATIC",
    "DOGEUSDT": "DOGE",
}


def _to_float(value, fallback: float = 0.0) -> float:
    """Safe float coercion."""
    try:
        return float(value or fallback)
    except (TypeError, ValueError):
        return fallback


@dataclass
class HLPerpSnapshot:
    """Per-asset perpetual market data from Hyperliquid."""

    symbol: str           # Binance-style, e.g. "BTCUSDT"
    hl_symbol: str        # Hyperliquid coin name, e.g. "BTC"
    mark_price: float     # HL mark price (USD)
    oracle_price: float   # HL oracle / index price (USD)
    mid_price: float      # HL best-bid/ask mid price (USD)
    funding_rate: float   # Hourly funding rate (fraction, e.g. 0.0001 = 0.01%/hr)
    open_interest: float  # Open interest in USD notional
    prev_day_px: float    # Previous settlement price
    fetched_at: str       # ISO-8601 UTC timestamp


class HyperliquidClient:
    """
    Minimal read-only client for Hyperliquid perpetuals market data.

    Single bulk request (``metaAndAssetCtxs``) retrieves data for every
    configured symbol in one round-trip — no API key required.
    """

    BASE_URL = "https://api.hyperliquid.xyz/info"
    TIMEOUT = 10

    def __init__(self, symbols: list[str] | None = None):
        """
        Args:
            symbols: Binance-style symbols to track.
                     Defaults to all symbols in HL_SYMBOL_MAP.
        """
        self.symbols = symbols or list(HL_SYMBOL_MAP.keys())
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _post(self, payload: dict) -> dict | list | None:
        """POST to the Hyperliquid info endpoint and return parsed JSON."""
        try:
            resp = self._session.post(
                self.BASE_URL,
                json=payload,
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("HyperliquidClient request failed: %s", exc)
            return None

    def get_perp_snapshots(self) -> list[HLPerpSnapshot]:
        """
        Fetch mark price, funding rate, and open interest for all configured symbols.

        Uses the ``metaAndAssetCtxs`` bulk endpoint (one HTTP request).

        Returns:
            List of HLPerpSnapshot; empty on API error or missing coins.
        """
        data = self._post({"type": "metaAndAssetCtxs"})
        if not data or not isinstance(data, list) or len(data) < 2:
            return []

        meta, asset_ctxs = data[0], data[1]
        coin_names: list[str] = [
            asset.get("name", "") for asset in (meta.get("universe") or [])
        ]

        snapshots: list[HLPerpSnapshot] = []
        fetched_at = datetime.utcnow().isoformat()

        for binance_sym in self.symbols:
            hl_sym = HL_SYMBOL_MAP.get(binance_sym)
            if not hl_sym:
                continue

            try:
                idx = coin_names.index(hl_sym)
            except ValueError:
                logger.debug("HyperliquidClient: %s not found in HL universe", hl_sym)
                continue

            if idx >= len(asset_ctxs):
                continue

            ctx: dict = asset_ctxs[idx] if isinstance(asset_ctxs[idx], dict) else {}
            mark_px = _to_float(ctx.get("markPx"))
            mid_px = _to_float(ctx.get("midPx")) or mark_px

            snapshots.append(
                HLPerpSnapshot(
                    symbol=binance_sym,
                    hl_symbol=hl_sym,
                    mark_price=mark_px,
                    oracle_price=_to_float(ctx.get("oraclePx")),
                    mid_price=mid_px,
                    funding_rate=_to_float(ctx.get("funding")),
                    open_interest=_to_float(ctx.get("openInterest")),
                    prev_day_px=_to_float(ctx.get("prevDayPx")),
                    fetched_at=fetched_at,
                )
            )

        return snapshots
