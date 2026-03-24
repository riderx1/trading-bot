"""Execution price and market microstructure guards."""

from datetime import datetime, timezone


def _parse_iso_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_execution(
    side: str,
    market: dict,
    cfg: dict,
    order_notional_usdc: float | None = None,
) -> dict:
    spread_bps = _to_float(market.get("spread_bps"), 0.0)
    liquidity = _to_float(market.get("liquidity"), 0.0)
    max_spread_bps = float(cfg["max_spread_bps"])
    min_liquidity = float(cfg["min_liquidity"])

    if spread_bps > max_spread_bps:
        return {"allowed": False, "reason_code": "spread_too_high"}
    if liquidity < min_liquidity:
        return {"allowed": False, "reason_code": "low_liquidity"}

    end_dt = _parse_iso_ts(market.get("end_date"))
    min_hours_to_resolution = float(cfg["min_hours_to_resolution"])
    if end_dt is not None:
        hours_left = (end_dt - datetime.now(timezone.utc)).total_seconds() / 3600.0
        if hours_left < min_hours_to_resolution:
            return {"allowed": False, "reason_code": "too_close_to_resolution"}

    slippage_bps = float(cfg["slippage_bps"])

    best_ask = _to_float(market.get("best_ask"), 0.0)
    fallback_ask = _to_float(market["yes_ask"] if side == "YES" else market["no_ask"], 0.0)
    base_price = best_ask if best_ask > 0 else fallback_ask
    if base_price <= 0:
        return {"allowed": False, "reason_code": "invalid_price"}

    notional = max(0.0, float(order_notional_usdc or 0.0))
    # Simple liquidity impact: larger orders versus thinner markets pay more slippage.
    impact_factor = float(cfg.get("paper_liquidity_impact_factor", 0.25))
    max_impact_bps = float(cfg.get("paper_max_impact_bps", 35.0))
    impact_bps = 0.0
    if liquidity > 0 and notional > 0:
        impact_bps = min(max_impact_bps, (notional / liquidity) * 10000.0 * impact_factor)

    effective_slippage_bps = slippage_bps + impact_bps
    exec_price = base_price * (1.0 + (effective_slippage_bps / 10000.0))

    return {
        "allowed": True,
        "reason_code": "ok",
        "execution_price": exec_price,
        "base_price": base_price,
        "effective_slippage_bps": effective_slippage_bps,
        "impact_bps": impact_bps,
        "spread_bps": spread_bps,
        "liquidity": liquidity,
    }
