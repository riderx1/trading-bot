"""Multi-bot orchestration layer for adaptive decision weighting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BotSignal:
    bot: str
    strategy: str
    direction: int  # -1 short, 0 neutral, +1 long
    confidence: float
    reasoning: str


class TrendBot:
    strategy = "momentum_trend"

    def generate_signal(self, symbol: str, snapshot: dict) -> BotSignal:
        trend = str(snapshot.get("trend") or "neutral")
        direction = 1 if trend == "bullish" else -1 if trend == "bearish" else 0
        confidence = float(snapshot.get("confidence") or 0.0)
        return BotSignal("TrendBot", self.strategy, direction, confidence, f"consensus={trend}")


class ReversalBot:
    strategy = "reversal_fade"

    def generate_signal(self, symbol: str, snapshot: dict) -> BotSignal:
        trend = str(snapshot.get("trend") or "neutral")
        confidence = float(snapshot.get("confidence") or 0.0)
        if confidence > 0.85 and trend in ("bullish", "bearish"):
            direction = -1 if trend == "bullish" else 1
            return BotSignal("ReversalBot", self.strategy, direction, min(0.8, confidence * 0.7), "high-confidence fade")
        return BotSignal("ReversalBot", self.strategy, 0, 0.2, "no reversal setup")


class ArbitrageBot:
    strategy = "arbitrage"

    def generate_signal(self, symbol: str, snapshot: dict, market_summary: dict | None = None) -> BotSignal:
        if not market_summary:
            return BotSignal("ArbitrageBot", self.strategy, 0, 0.1, "no market summary")

        edge = float(market_summary.get("best_edge") or 0.0)
        side = str(market_summary.get("best_side") or "")
        arb_type = str(market_summary.get("arb_type") or "unknown")
        if edge > 0.015:
            direction = 1 if side == "YES" else -1 if side == "NO" else 0
            return BotSignal(
                "ArbitrageBot",
                self.strategy,
                direction,
                min(0.9, 0.45 + edge * 10),
                f"arb_type={arb_type} best_edge={edge:.4f}",
            )
        return BotSignal("ArbitrageBot", self.strategy, 0, 0.2, "edge below threshold")


class TABot:
    strategy = "ta_confluence"

    def generate_signal(self, symbol: str, snapshot: dict, ta_alignment: float = 0.0) -> BotSignal:
        confidence = float(snapshot.get("confidence") or 0.0)
        if ta_alignment > 0:
            return BotSignal("TABot", self.strategy, 1, min(0.9, confidence + 0.1), "ta bullish alignment")
        if ta_alignment < 0:
            return BotSignal("TABot", self.strategy, -1, min(0.9, confidence + 0.1), "ta bearish alignment")
        return BotSignal("TABot", self.strategy, 0, max(0.15, confidence * 0.3), "ta neutral")


class ModelVsMarketBot:
    """
    Strategy 1 — Model vs. Polymarket odds.

    Generates a directional signal when the FairValueEngine probability
    estimate diverges sufficiently from the market-implied probability.
    Long YES when p_model > p_mkt + delta; long NO when p_model < p_mkt - delta.
    """

    strategy = "model_vs_market"

    def generate_signal(
        self,
        symbol: str,
        snapshot: dict,
        fv_result=None,  # FairValueResult | None
    ) -> BotSignal:
        if fv_result is None or fv_result.arb_type not in (
            "model_vs_market",
            "yes_no_sum",
        ):
            return BotSignal(
                "ModelVsMarketBot", self.strategy, 0, 0.1,
                "no fv_result or arb_type not actionable",
            )

        edge_bp = int(fv_result.edge_bp)
        confidence = float(fv_result.confidence)

        if edge_bp > 0:
            direction = 1  # YES underpriced relative to model
            reason = (
                f"model_above_mkt edge={edge_bp:+d}bp "
                f"p_model={fv_result.p_model:.2%} p_mkt={fv_result.p_mkt:.2%}"
            )
        elif edge_bp < 0:
            direction = -1  # NO underpriced relative to model
            reason = (
                f"model_below_mkt edge={edge_bp:+d}bp "
                f"p_model={fv_result.p_model:.2%} p_mkt={fv_result.p_mkt:.2%}"
            )
        else:
            return BotSignal(
                "ModelVsMarketBot", self.strategy, 0, 0.1, "edge=0 no trade"
            )

        return BotSignal(
            "ModelVsMarketBot", self.strategy, direction, confidence, reason
        )


class PerpArbBot:
    """
    Strategy 2 — Binance / Hyperliquid perp-perp relative value.

    Detects a pricing or funding-rate divergence between the two venues.
    In live mode this would drive a delta-neutral pair trade; in paper mode
    the signal feeds the Orchestrator blend and is tagged arb_type=cross_venue.
    """

    strategy = "perp_arb"

    # Minimum basis spread (bp) or funding spread (fraction) to generate a signal.
    MIN_BASIS_BP: float = 5.0
    MIN_FUNDING_SPREAD: float = 0.0001  # 0.01 %/hr

    def generate_signal(
        self,
        symbol: str,
        snapshot: dict,
        perp_context: dict | None = None,
    ) -> BotSignal:
        if not perp_context:
            return BotSignal(
                "PerpArbBot", self.strategy, 0, 0.1, "no perp context"
            )

        hl_perp = float(perp_context.get("hl_perp_price") or 0.0)
        bin_perp = float(perp_context.get("binance_perp_price") or 0.0)
        basis_diff = float(perp_context.get("basis_diff") or 0.0)
        funding_spread = float(perp_context.get("funding_spread") or 0.0)

        ref_price = max(hl_perp, bin_perp, 1.0)
        basis_bp = abs(basis_diff / ref_price) * 10_000

        has_basis_edge = basis_bp >= self.MIN_BASIS_BP
        has_funding_edge = abs(funding_spread) >= self.MIN_FUNDING_SPREAD

        if not has_basis_edge and not has_funding_edge:
            return BotSignal(
                "PerpArbBot", self.strategy, 0, 0.15,
                f"spread below threshold (basis={basis_bp:.1f}bp "
                f"fund_spread={funding_spread:.5f})",
            )

        # basis_diff = bin_perp - hl_perp
        # If positive: Binance perp trades higher → short Binance / long HL
        # If negative: HL perp trades higher → long Binance / short HL
        direction = -1 if basis_diff > 0 else 1
        confidence = min(
            0.85,
            0.40 + basis_bp / 200.0 + abs(funding_spread) * 10.0,
        )
        reason = (
            f"cross_venue: bin_perp={bin_perp:.2f} hl_perp={hl_perp:.2f} "
            f"basis={basis_bp:.1f}bp fund_spread={funding_spread:.5f}"
        )
        return BotSignal("PerpArbBot", self.strategy, direction, confidence, reason)


class Orchestrator:
    def __init__(self, db, config: dict | None = None):
        self.db = db
        self.bots = [TrendBot(), ReversalBot(), ArbitrageBot(), TABot(), ModelVsMarketBot(), PerpArbBot()]
        self.config = config or {}

    def _strategy_weight_overrides(self) -> dict[str, float]:
        cfg = self.config.get("orchestrator", {}) if isinstance(self.config, dict) else {}
        overrides = cfg.get("strategy_weight_overrides", {})
        if not isinstance(overrides, dict):
            return {}

        cleaned: dict[str, float] = {}
        for key, value in overrides.items():
            strategy = str(key)
            if strategy not in {
                "momentum_trend", "ta_confluence", "reversal_fade",
                "arbitrage", "model_vs_market", "perp_arb",
            }:
                continue
            try:
                weight = float(value)
            except (TypeError, ValueError):
                continue
            if weight > 0:
                cleaned[strategy] = weight
        return cleaned

    def _strategy_weights(self) -> dict[str, float]:
        rankings = self.db.get_strategy_rankings()
        base = {
            "momentum_trend": 1.0,
            "ta_confluence":  1.0,
            "reversal_fade":  1.0,
            "arbitrage":      1.0,
            "model_vs_market": 1.0,
            "perp_arb":        0.8,  # slightly lower initial weight; scales with edge data
        }
        if not rankings:
            return base

        for row in rankings:
            strategy = str(row.get("strategy") or "")
            score = float(row.get("score") or 0.0)
            if strategy in base:
                base[strategy] = max(0.25, 1.0 + score)

        for strategy, override_weight in self._strategy_weight_overrides().items():
            base[strategy] = max(0.05, override_weight)

        total = sum(base.values())
        if total <= 0:
            return {key: 1.0 / len(base) for key in base}
        return {key: value / total for key, value in base.items()}

    def collect_signals(
        self,
        symbol: str,
        snapshot: dict,
        ta_alignment: float = 0.0,
        market_summary: dict | None = None,
        fv_result=None,           # FairValueResult | None
        perp_context: dict | None = None,
    ) -> list[BotSignal]:
        signals: list[BotSignal] = []
        for bot in self.bots:
            if isinstance(bot, ArbitrageBot):
                signals.append(bot.generate_signal(symbol, snapshot, market_summary))
            elif isinstance(bot, TABot):
                signals.append(bot.generate_signal(symbol, snapshot, ta_alignment))
            elif isinstance(bot, ModelVsMarketBot):
                signals.append(bot.generate_signal(symbol, snapshot, fv_result))
            elif isinstance(bot, PerpArbBot):
                signals.append(bot.generate_signal(symbol, snapshot, perp_context))
            else:
                signals.append(bot.generate_signal(symbol, snapshot))
        return signals

    def output_decision(
        self,
        symbol: str,
        snapshot: dict,
        ta_alignment: float = 0.0,
        market_summary: dict | None = None,
        fv_result=None,
        perp_context: dict | None = None,
    ) -> dict:
        signals = self.collect_signals(
            symbol, snapshot,
            ta_alignment=ta_alignment,
            market_summary=market_summary,
            fv_result=fv_result,
            perp_context=perp_context,
        )
        return self.combine(symbol, signals)

    def combine(self, symbol: str, signals: list[BotSignal]) -> dict:
        weights = self._strategy_weights()

        weighted_bias = 0.0
        weighted_confidence = 0.0
        total_weight = 0.0
        contributions = []

        for signal in signals:
            weight = float(weights.get(signal.strategy, 0.25))
            weighted_bias += signal.direction * weight
            weighted_confidence += signal.confidence * weight
            total_weight += weight
            signal_label = "LONG" if signal.direction > 0 else "SHORT" if signal.direction < 0 else "FLAT"
            contributions.append(
                {
                    "bot": signal.bot,
                    "strategy": signal.strategy,
                    "direction": signal.direction,
                    "signal": signal_label,
                    "confidence": signal.confidence,
                    "weight": weight,
                    "reasoning": signal.reasoning,
                }
            )

        if total_weight <= 0:
            final_bias = 0.0
            final_confidence = 0.0
        else:
            final_bias = weighted_bias / total_weight
            final_confidence = max(0.0, min(0.95, weighted_confidence / total_weight))

        bias_label = "neutral"
        if final_bias > 0.2:
            bias_label = "bullish"
        elif final_bias < -0.2:
            bias_label = "bearish"

        return {
            "symbol": symbol,
            "final_bias": final_bias,
            "final_confidence": final_confidence,
            "confidence": final_confidence,
            "bias_label": bias_label,
            "contributing_bots": contributions,
            "contributions": contributions,
            "reasoning": f"weighted_bias={final_bias:.3f} confidence={final_confidence:.3f}",
        }
