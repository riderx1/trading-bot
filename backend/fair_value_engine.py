"""
fair_value_engine.py — Probability estimation for Polymarket directional events.

Given Binance multi-timeframe signals and optional TA features, estimates the
probability that a binary event (e.g. "BTC closes higher today") resolves YES.

Architecture:
  FairValueEngine.estimate(signal_snapshot, market, ta_features) → FairValueResult

  Current backend: _logistic_estimate() — a hand-crafted logistic-like function
  over momentum + TA features. Fully replaceable via ModelInterface.

TODO (when sufficient labeled trade outcome data exists):
  - Train sklearn LogisticRegression or XGBoostClassifier on (features → outcome).
  - Wrap in ConcreteModel(ModelInterface) and inject via FairValueEngine(model=...).
  - The feature vectors stored in features_used can be used as training data.
  - Add live funding_rate, basis_pct, iv_percentile from CCXT as extra features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Protocol, runtime_checkable


# ── Data models ────────────────────────────────────────────────────────────────


@dataclass
class FairValueResult:
    """Output of the FairValueEngine for a single market evaluation."""

    market_id: str
    market_name: str
    p_model: float          # model-estimated P(YES) [0, 1]
    p_fair: float           # fair-value estimate (= p_model now; TODO: blend w/ orderbook/funding)
    p_mkt: float            # Polymarket implied P(YES) == YES token price
    confidence: float       # model confidence in this estimate [0, 1]
    edge_bp: int            # (p_fair − p_mkt) × 10_000  (signed basis points)
    arb_type: str           # "model_vs_market" | "yes_no_sum" | "none"
    why: str                # human-readable explanation
    features_used: dict = field(default_factory=dict)  # raw inputs for logging/training

    @property
    def is_opportunity(self) -> bool:
        return self.arb_type != "none"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_opportunity"] = self.is_opportunity
        return d


# ── Model interface (pluggable) ────────────────────────────────────────────────


@runtime_checkable
class ModelInterface(Protocol):
    """
    Interface for a swappable probability model backend.

    TODO: Implement ConcreteModel(ModelInterface) that wraps a trained
          sklearn / xgboost classifier once labeled outcome data is available.

    Example skeleton:
        class SklearnModel:
            def __init__(self, clf):
                self._clf = clf

            def predict_proba(self, features: dict) -> float:
                X = self._vectorize(features)          # feature → numpy array
                return float(self._clf.predict_proba(X)[0, 1])
    """

    def predict_proba(self, features: dict) -> float:
        """Return P(YES) ∈ [0, 1] given a feature dict."""
        ...


# ── Built-in logistic estimator ────────────────────────────────────────────────

# Per-timeframe importance weights (normalized inside the estimator).
_TF_WEIGHTS: dict[str, float] = {
    "5m":  0.10,
    "15m": 0.15,
    "1h":  0.25,
    "4h":  0.30,
    "1d":  0.40,
}

# How strongly each regime lets momentum drive a probability shift.
_REGIME_SCALE: dict[str, float] = {
    "TRENDING":  1.0,      # full momentum → probability shift
    "CHOP":      0.30,     # weak conviction; stay near 0.5
    "REVERSAL": -0.55,     # invert the signal (fade the trend)
}


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _logistic_estimate(features: dict) -> tuple[float, float, str]:
    """
    Compute P(YES) from a feature dict using a logistic-like weighted sum.

    Returns:
        (p_model, confidence, reasoning_string)

    Features consumed:
      tf_signals      — dict[str, dict] with trend / confidence per timeframe
      regime          — "TRENDING" | "CHOP" | "REVERSAL"
      consensus_conf  — overall consensus confidence scalar (float)
      ta_boost        — TA alignment value in [-1, +1] (optional, default 0)

    TODO: Add when data is wired in from CCXT / external feeds:
      funding_rate    — perpetual funding rate (float, annualised %)
      basis_pct       — spot-perp basis (float)
      iv_percentile   — implied-volatility percentile [0, 1]
    """
    tf_signals: dict[str, dict] = features.get("tf_signals") or {}
    regime: str = str(features.get("regime") or "CHOP")
    consensus_conf: float = float(features.get("consensus_conf") or 0.0)
    ta_boost: float = float(features.get("ta_boost") or 0.0)

    # Perp context features (live when HyperliquidClient + BinanceClient provide them).
    # funding_rate > 0  → longs pay → market structurally bullish (slight YES boost).
    # basis_pct   > 0  → perp trades at premium to spot → same signal.
    # basis_diff  != 0 → cross-venue divergence → slight confidence discount.
    # funding_spread    → Binance - HL funding; large values indicate crowded positioning.
    funding_rate: float = float(features.get("funding_rate") or 0.0)
    basis_pct: float = float(features.get("basis_pct") or 0.0)
    basis_diff: float = float(features.get("basis_diff") or 0.0)
    funding_spread: float = float(features.get("funding_spread") or 0.0)

    regime_scale = _REGIME_SCALE.get(regime, 0.30)

    # Weighted directional momentum score across timeframes.
    momentum_score = 0.0
    total_weight = 0.0
    for tf, sig in tf_signals.items():
        w = _TF_WEIGHTS.get(tf, 0.10)
        trend = str(sig.get("trend") or "neutral")
        conf = float(sig.get("confidence") or 0.0)
        direction = 1.0 if trend == "bullish" else -1.0 if trend == "bearish" else 0.0
        momentum_score += direction * w * conf
        total_weight += w

    if total_weight > 0:
        momentum_score /= total_weight

    # Apply regime scale and small TA nudge.
    # Funding/basis nudge: positive funding = longs paying = bull-leaning market.
    # Capped at ±0.06 total nudge to avoid overwhelming the momentum signal.
    funding_nudge = max(-0.06, min(0.06, funding_rate * 5.0 + basis_pct * 2.0))
    # Cross-venue divergence slightly discounts confidence in momentum direction.
    basis_disc = min(0.08, abs(basis_diff) * 0.001)  # small discount
    adjusted = momentum_score * regime_scale * (1.0 - basis_disc) + ta_boost * 0.08 + funding_nudge

    # Map to probability via sigmoid (scale ≈ 4 gives p ≈ 0.73 at full conviction).
    p_raw = _sigmoid(adjusted * 4.0)

    # Shrink toward 0.5 when consensus confidence is low.
    shrink = max(0.0, 1.0 - consensus_conf)
    p_model = 0.5 + (p_raw - 0.5) * (1.0 - shrink * 0.60)
    p_model = max(0.10, min(0.90, p_model))

    # Confidence: distance from 0.5, weighted by consensus confidence.
    # Cross-venue funding spread above 0.1%/hr signals crowded market → slight discount.
    funding_crowd_discount = min(0.15, abs(funding_spread) * 50.0)
    confidence = min(1.0, abs(p_model - 0.5) * 2.0 * (0.5 + consensus_conf * 0.5) * (1.0 - funding_crowd_discount))

    reasoning = (
        f"regime={regime}(scale={regime_scale:.2f}); "
        f"momentum={momentum_score:.3f}; adjusted={adjusted:.3f}; "
        f"p_raw={p_raw:.3f}; shrink={shrink:.2f}; ta_boost={ta_boost:.2f}; "
        f"funding={funding_rate:.5f}; basis={basis_pct:.4f}; spread={funding_spread:.5f}"
    )
    return p_model, confidence, reasoning


# ── Main engine ────────────────────────────────────────────────────────────────


class FairValueEngine:
    """
    Estimates fair-value probability for Polymarket binary events.

    Usage:
        engine = FairValueEngine()
        result = engine.estimate(signal_snapshot, market)

    Inject a trained model when available:
        engine = FairValueEngine(model=MyModel())
    """

    def __init__(
        self,
        model: ModelInterface | None = None,
        model_vs_market_threshold_bp: int = 600,   # ≥6 % edge triggers model_vs_market arb
        yes_no_sum_threshold: float = 0.98,         # YES+NO sum arb threshold
    ):
        self._model = model
        self.model_vs_market_threshold_bp = model_vs_market_threshold_bp
        self.yes_no_sum_threshold = yes_no_sum_threshold

    def estimate(
        self,
        signal_snapshot: dict,
        market: dict,
        ta_features: dict | None = None,
        perp_context: dict | None = None,
    ) -> FairValueResult:
        """
        Estimate fair-value probability for a binary prediction market.

        Args:
            signal_snapshot: Output of TradingBot._build_signal_snapshot().
            market:          Polymarket market dict (yes_price, no_price, ...).
            ta_features:     Optional dict from TechnicalScanner
                             (recognized keys: boost, rsi, bb_pos).
            perp_context:    Optional cross-venue perp data dict with keys:
                             funding_rate, basis_pct, hl_funding_rate,
                             hl_perp_price, basis_diff, funding_spread.

        Returns:
            FairValueResult with p_model, p_mkt, edge_bp, arb_type and why.
        """
        market_id = str(market.get("market_id") or market.get("condition_id") or "")
        market_name = str(market.get("market_name") or "")

        features = self._build_features(signal_snapshot, market, ta_features, perp_context)

        if self._model is not None and isinstance(self._model, ModelInterface):
            # TODO: validated model path — replace logistic estimator
            p_model = float(self._model.predict_proba(features))
            feat_reasoning = "model=external"
        else:
            p_model, _raw_conf, feat_reasoning = _logistic_estimate(features)

        features["_reasoning"] = feat_reasoning

        # p_fair == p_model for now.
        # TODO: blend with order-book mid-price, funding rate, basis when available.
        p_fair = p_model

        yes_price = float(market.get("yes_price") or 0.5)
        no_price = float(market.get("no_price") or 0.5)
        p_mkt = yes_price                              # YES token price ≈ P(YES) implied
        edge_bp = int(round((p_fair - p_mkt) * 10_000))
        combined = yes_price + no_price

        # YES+NO sum arb is risk-free; classify it first.
        if combined < self.yes_no_sum_threshold:
            arb_type = "yes_no_sum"
        elif abs(edge_bp) >= self.model_vs_market_threshold_bp:
            arb_type = "model_vs_market"
        else:
            arb_type = "none"

        regime = str(features.get("regime") or "CHOP")
        consensus_conf = float(features.get("consensus_conf") or 0.0)
        confidence = consensus_conf * (0.5 if regime == "CHOP" else 1.0)
        confidence = min(1.0, confidence)

        why = (
            f"Model: {p_model:.1%} P(YES) vs market {p_mkt:.1%}; "
            f"edge={edge_bp:+d}bp; arb_type={arb_type}; regime={regime}; "
            f"{feat_reasoning}"
        )

        return FairValueResult(
            market_id=market_id,
            market_name=market_name,
            p_model=round(p_model, 4),
            p_fair=round(p_fair, 4),
            p_mkt=round(p_mkt, 4),
            confidence=round(confidence, 4),
            edge_bp=edge_bp,
            arb_type=arb_type,
            why=why,
            features_used={k: v for k, v in features.items() if not k.startswith("_")},
        )

    def _build_features(
        self,
        signal_snapshot: dict,
        market: dict,
        ta_features: dict | None,
        perp_context: dict | None = None,
    ) -> dict:
        """Build the normalized feature dict that drives probability estimation."""
        timeframes: dict[str, dict] = signal_snapshot.get("timeframes") or {}
        regime = str(signal_snapshot.get("regime") or "CHOP")
        consensus_conf = float(signal_snapshot.get("confidence") or 0.0)

        ta_boost = 0.0
        if ta_features:
            ta_boost = max(-1.0, min(1.0, float(ta_features.get("boost") or 0.0)))

        # Perp context (Binance + Hyperliquid cross-venue data).
        funding_rate: float = 0.0
        basis_pct: float = 0.0
        hl_funding_rate: float = 0.0
        hl_perp_price: float = 0.0
        basis_diff: float = 0.0
        funding_spread: float = 0.0
        if perp_context:
            funding_rate = float(perp_context.get("funding_rate") or 0.0)
            basis_pct = float(perp_context.get("basis_pct") or 0.0)
            hl_funding_rate = float(perp_context.get("hl_funding_rate") or 0.0)
            hl_perp_price = float(perp_context.get("hl_perp_price") or 0.0)
            basis_diff = float(perp_context.get("basis_diff") or 0.0)
            funding_spread = float(perp_context.get("funding_spread") or 0.0)

        return {
            "tf_signals":      timeframes,
            "regime":          regime,
            "consensus_conf":  consensus_conf,
            "ta_boost":        ta_boost,
            "yes_price":       float(market.get("yes_price") or 0.5),
            "no_price":        float(market.get("no_price") or 0.5),
            "spread_bps":      float(market.get("spread_bps") or 0.0),
            "liquidity":       float(market.get("liquidity") or 0.0),
            # Perp features
            "funding_rate":    funding_rate,
            "basis_pct":       basis_pct,
            "hl_funding_rate": hl_funding_rate,
            "hl_perp_price":   hl_perp_price,
            "basis_diff":      basis_diff,
            "funding_spread":  funding_spread,
        }
