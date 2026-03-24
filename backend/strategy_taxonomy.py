"""Canonical strategy taxonomy and compatibility helpers."""

from __future__ import annotations

STRATEGIES = {
    "directional": [
        "trend",
        "momentum",
        "reversal",
        "breakout",
        "mean_reversion",
        "volatility",
        "scalping",
    ],
    "confirmation": [
        "ta_confluence",
    ],
    "arbitrage": [
        "funding_arb",
        "basis_arb",
    ],
}

LEGACY_TO_CANONICAL = {
    "trend_following": "trend",
    "momentum_trend": "momentum",
    "reversal_fade": "reversal",
    "arbitrage": "funding_arb",
    "yes_no": "funding_arb",
    "model_vs_market": "volatility",
    "cross_venue": "basis_arb",
    "perp_arb": "basis_arb",
    "polymarket_scalp": "scalping",
}

CANONICAL_TO_LEGACY = {
    "trend": "trend_following",
    "momentum": "momentum_trend",
    "reversal": "reversal_fade",
    "funding_arb": "arbitrage",
    "basis_arb": "perp_arb",
}


def normalize_strategy(name: str | None) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "ta_confluence"
    return LEGACY_TO_CANONICAL.get(raw, raw)


def strategy_aliases(name: str | None) -> list[str]:
    canonical = normalize_strategy(name)
    aliases = {canonical}

    legacy = CANONICAL_TO_LEGACY.get(canonical)
    if legacy:
        aliases.add(legacy)

    for old_name, new_name in LEGACY_TO_CANONICAL.items():
        if new_name == canonical:
            aliases.add(old_name)

    return sorted(aliases)


def strategy_domain(name: str | None) -> str:
    canonical = normalize_strategy(name)
    if canonical in STRATEGIES["directional"]:
        return "directional"
    if canonical in STRATEGIES["confirmation"]:
        return "confirmation"
    if canonical in STRATEGIES["arbitrage"]:
        return "arbitrage"
    return "directional"
