"""Multi-bot orchestration layer with directional and arbitrage domains."""

from __future__ import annotations

from dataclasses import dataclass

from strategy_taxonomy import STRATEGIES, normalize_strategy


@dataclass
class BotSignal:
    bot: str
    strategy: str
    bot_type: str
    time_horizon: str
    direction: int  # -1 short, 0 neutral, +1 long
    confidence: float
    reasoning: str
    edge: float = 0.0


class TrendBot:
    strategy = "momentum"
    type = "directional"
    time_horizon = "medium"

    def generate_signal(self, symbol: str, snapshot: dict) -> BotSignal:
        trend = str(snapshot.get("trend") or "neutral")
        direction = 1 if trend == "bullish" else -1 if trend == "bearish" else 0
        confidence = float(snapshot.get("confidence") or 0.0)
        return BotSignal(
            "TrendBot",
            self.strategy,
            self.type,
            self.time_horizon,
            direction,
            confidence,
            f"consensus={trend}",
        )


class ReversalBot:
    strategy = "reversal"
    type = "directional"
    time_horizon = "short"

    def generate_signal(self, symbol: str, snapshot: dict) -> BotSignal:
        trend = str(snapshot.get("trend") or "neutral")
        confidence = float(snapshot.get("confidence") or 0.0)
        if confidence > 0.85 and trend in ("bullish", "bearish"):
            direction = -1 if trend == "bullish" else 1
            return BotSignal(
                "ReversalBot",
                self.strategy,
                self.type,
                self.time_horizon,
                direction,
                min(0.8, confidence * 0.7),
                "high-confidence fade",
            )
        return BotSignal(
            "ReversalBot",
            self.strategy,
            self.type,
            self.time_horizon,
            0,
            0.2,
            "no reversal setup",
        )


class ArbitrageBot:
    strategy = "yes_no"
    type = "arbitrage"
    time_horizon = "short"

    def generate_signal(self, symbol: str, snapshot: dict, market_summary: dict | None = None) -> BotSignal:
        if not market_summary:
            return BotSignal(
                "ArbitrageBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.1,
                "no market summary",
            )

        edge = float(market_summary.get("best_edge") or 0.0)
        side = str(market_summary.get("best_side") or "")
        arb_type = str(market_summary.get("arb_type") or "unknown")
        if edge > 0.015:
            direction = 1 if side == "YES" else -1 if side == "NO" else 0
            return BotSignal(
                "ArbitrageBot",
                self.strategy,
                self.type,
                self.time_horizon,
                direction,
                min(0.9, 0.45 + edge * 10),
                f"arb_type={arb_type} best_edge={edge:.4f}",
                edge=edge,
            )
        return BotSignal(
            "ArbitrageBot",
            self.strategy,
            self.type,
            self.time_horizon,
            0,
            0.2,
            "edge below threshold",
            edge=edge,
        )


class TABot:
    strategy = "ta_confluence"
    type = "directional"
    time_horizon = "short"

    def generate_signal(self, symbol: str, snapshot: dict, ta_alignment: float = 0.0) -> BotSignal:
        confidence = float(snapshot.get("confidence") or 0.0)
        if ta_alignment > 0:
            return BotSignal(
                "TABot",
                self.strategy,
                self.type,
                self.time_horizon,
                1,
                min(0.9, confidence + 0.1),
                "ta bullish alignment",
            )
        if ta_alignment < 0:
            return BotSignal(
                "TABot",
                self.strategy,
                self.type,
                self.time_horizon,
                -1,
                min(0.9, confidence + 0.1),
                "ta bearish alignment",
            )
        return BotSignal(
            "TABot",
            self.strategy,
            self.type,
            self.time_horizon,
            0,
            max(0.15, confidence * 0.3),
            "ta neutral",
        )


class ModelVsMarketBot:
    strategy = "model_vs_market"
    type = "directional"
    time_horizon = "medium"

    def generate_signal(
        self,
        symbol: str,
        snapshot: dict,
        fv_result=None,
    ) -> BotSignal:
        if fv_result is None or fv_result.arb_type not in ("model_vs_market", "yes_no_sum"):
            return BotSignal(
                "ModelVsMarketBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.1,
                "no fv_result or arb_type not actionable",
            )

        edge_bp = int(fv_result.edge_bp)
        confidence = float(fv_result.confidence)
        edge = abs(edge_bp) / 10_000.0

        if edge_bp > 0:
            direction = 1
            reason = (
                f"model_above_mkt edge={edge_bp:+d}bp "
                f"p_model={fv_result.p_model:.2%} p_mkt={fv_result.p_mkt:.2%}"
            )
        elif edge_bp < 0:
            direction = -1
            reason = (
                f"model_below_mkt edge={edge_bp:+d}bp "
                f"p_model={fv_result.p_model:.2%} p_mkt={fv_result.p_mkt:.2%}"
            )
        else:
            return BotSignal(
                "ModelVsMarketBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.1,
                "edge=0 no trade",
            )

        return BotSignal(
            "ModelVsMarketBot",
            self.strategy,
            self.type,
            self.time_horizon,
            direction,
            confidence,
            reason,
            edge=edge,
        )


class PerpArbBot:
    strategy = "cross_venue"
    type = "arbitrage"
    time_horizon = "short"
    MIN_BASIS_BP: float = 5.0
    MIN_FUNDING_SPREAD: float = 0.0001

    def generate_signal(
        self,
        symbol: str,
        snapshot: dict,
        perp_context: dict | None = None,
    ) -> BotSignal:
        if not perp_context:
            return BotSignal(
                "PerpArbBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.1,
                "no perp context",
            )

        hl_perp = float(perp_context.get("hl_perp_price") or 0.0)
        bin_perp = float(perp_context.get("binance_perp_price") or 0.0)
        basis_diff = float(perp_context.get("basis_diff") or 0.0)
        funding_spread = float(perp_context.get("funding_spread") or 0.0)

        ref_price = max(hl_perp, bin_perp, 1.0)
        basis_bp = abs(basis_diff / ref_price) * 10_000
        has_basis_edge = basis_bp >= self.MIN_BASIS_BP
        has_funding_edge = abs(funding_spread) >= self.MIN_FUNDING_SPREAD
        edge = max(basis_bp / 10_000.0, abs(funding_spread))

        if not has_basis_edge and not has_funding_edge:
            return BotSignal(
                "PerpArbBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.15,
                f"spread below threshold (basis={basis_bp:.1f}bp fund_spread={funding_spread:.5f})",
                edge=edge,
            )

        direction = -1 if basis_diff > 0 else 1
        confidence = min(0.85, 0.40 + basis_bp / 200.0 + abs(funding_spread) * 10.0)
        reason = (
            f"cross_venue: bin_perp={bin_perp:.2f} hl_perp={hl_perp:.2f} "
            f"basis={basis_bp:.1f}bp fund_spread={funding_spread:.5f}"
        )
        return BotSignal(
            "PerpArbBot",
            self.strategy,
            self.type,
            self.time_horizon,
            direction,
            confidence,
            reason,
            edge=edge,
        )


class ScalperBot:
    strategy = "scalping"
    type = "directional"
    time_horizon = "scalp"

    def generate_signal(self, symbol: str, snapshot: dict, micro_data: dict | None = None) -> BotSignal:
        if not micro_data:
            return BotSignal(
                "ScalperBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.0,
                "no micro data",
            )

        move = float(micro_data.get("move_pct_short") or 0.0)
        volume_spike = bool(micro_data.get("volume_spike"))
        spread_bps = float(micro_data.get("spread_bps") or 0.0)

        if spread_bps > 20.0:
            return BotSignal(
                "ScalperBot",
                self.strategy,
                self.type,
                self.time_horizon,
                0,
                0.0,
                f"spread too wide ({spread_bps:.1f}bp)",
            )

        if move > 0.001 and volume_spike:
            return BotSignal(
                "ScalperBot",
                self.strategy,
                self.type,
                self.time_horizon,
                1,
                0.6,
                f"micro breakout move={move:.4f} volume_spike=1 spread={spread_bps:.1f}bp",
                edge=abs(move),
            )

        if move < -0.001 and volume_spike:
            return BotSignal(
                "ScalperBot",
                self.strategy,
                self.type,
                self.time_horizon,
                -1,
                0.6,
                f"micro breakdown move={move:.4f} volume_spike=1 spread={spread_bps:.1f}bp",
                edge=abs(move),
            )

        return BotSignal(
            "ScalperBot",
            self.strategy,
            self.type,
            self.time_horizon,
            0,
            0.0,
            "micro setup not ready",
            edge=abs(move),
        )


class Orchestrator:
    def __init__(self, db, config: dict | None = None):
        self.db = db
        self.bots = [
            TrendBot(),
            ReversalBot(),
            ArbitrageBot(),
            TABot(),
            ModelVsMarketBot(),
            PerpArbBot(),
            ScalperBot(),
        ]
        self.config = config or {}

    def _strategy_weight_overrides(self) -> dict[str, float]:
        cfg = self.config.get("orchestrator", {}) if isinstance(self.config, dict) else {}
        overrides = cfg.get("strategy_weight_overrides", {})
        if not isinstance(overrides, dict):
            return {}

        cleaned: dict[str, float] = {}
        for key, value in overrides.items():
            strategy = normalize_strategy(str(key))
            if strategy not in {
                "momentum",
                "ta_confluence",
                "reversal",
                "yes_no",
                "model_vs_market",
                "cross_venue",
                "scalping",
            }:
                continue
            try:
                weight = float(value)
            except (TypeError, ValueError):
                continue
            if weight > 0:
                cleaned[strategy] = weight
        return cleaned

    def _base_strategy_weights(self) -> dict[str, float]:
        rankings = self.db.get_strategy_rankings()
        base = {
            "momentum": 1.0,
            "ta_confluence": 1.0,
            "reversal": 1.0,
            "yes_no": 1.0,
            "model_vs_market": 1.0,
            "cross_venue": 0.8,
            "scalping": 0.7,
        }
        if not rankings:
            return base

        for row in rankings:
            strategy = normalize_strategy(str(row.get("strategy") or ""))
            score = float(row.get("score") or 0.0)
            if strategy in base:
                base[strategy] = max(0.25, 1.0 + score)

        for strategy, override_weight in self._strategy_weight_overrides().items():
            base[strategy] = max(0.05, override_weight)

        return base

    def _stream_weights(self, stream: str, regime: str | None = None) -> dict[str, float]:
        base = self._base_strategy_weights()
        regime_name = str(regime or "CHOP").upper()

        if stream == "directional":
            names = set(STRATEGIES["directional"] + STRATEGIES["confirmation"])
        else:
            names = set(STRATEGIES["arbitrage"])

        scoped = {name: float(base.get(name, 1.0)) for name in names}

        if stream == "directional":
            if regime_name == "CHOP":
                scoped["momentum"] = scoped.get("momentum", 1.0) * 0.5
                scoped["reversal"] = scoped.get("reversal", 1.0) * 1.5
            elif regime_name == "TRENDING":
                scoped["momentum"] = scoped.get("momentum", 1.0) * 1.5
                scoped["reversal"] = scoped.get("reversal", 1.0) * 0.5

        total = sum(scoped.values())
        if total <= 0:
            size = max(1, len(scoped))
            return {key: 1.0 / size for key in scoped}
        return {key: value / total for key, value in scoped.items()}

    def _serialize_signal(self, signal: BotSignal, weight: float) -> dict:
        signal_label = "LONG" if signal.direction > 0 else "SHORT" if signal.direction < 0 else "FLAT"
        impact = float(signal.direction) * float(weight) * float(signal.confidence)
        return {
            "bot": signal.bot,
            "strategy": normalize_strategy(signal.strategy),
            "type": signal.bot_type,
            "time_horizon": signal.time_horizon,
            "direction": signal.direction,
            "signal": signal_label,
            "confidence": signal.confidence,
            "weight": weight,
            "impact": impact,
            "edge": signal.edge,
            "reasoning": signal.reasoning,
        }

    def _conviction_label(self, confidence: float) -> str:
        if confidence >= 0.65:
            return "HIGH"
        if confidence >= 0.45:
            return "MEDIUM"
        return "LOW"

    def _setup_quality(self, confidence: float) -> str:
        if confidence >= 0.6:
            return "READY"
        if confidence >= 0.35:
            return "DEVELOPING"
        return "POOR"

    def _entry_timing(self, confidence: float, weighted_bias: float) -> str:
        if confidence < 0.35:
            return "EARLY"
        if abs(weighted_bias) >= 0.5:
            return "LATE"
        return "CONFIRMED"

    def _directional_decision(self, symbol: str, signals: list[BotSignal], weights: dict[str, float]) -> dict:
        weighted_bias = 0.0
        weighted_confidence = 0.0
        total_weight = 0.0
        contributions: list[dict] = []

        for signal in signals:
            strategy_name = normalize_strategy(signal.strategy)
            weight = float(weights.get(strategy_name, 0.25))
            weighted_bias += signal.direction * weight
            weighted_confidence += signal.confidence * weight
            total_weight += weight
            contributions.append(self._serialize_signal(signal, weight))

        if total_weight <= 0:
            final_bias = 0.0
            final_confidence = 0.0
        else:
            final_bias = weighted_bias / total_weight
            final_confidence = max(0.0, min(0.75, weighted_confidence / total_weight))

        bias = "NO TRADE"
        bias_label = "neutral"
        if final_bias > 0.2:
            bias = "LONG"
            bias_label = "bullish"
        elif final_bias < -0.2:
            bias = "SHORT"
            bias_label = "bearish"

        top_contribution = max(
            contributions,
            key=lambda row: abs(float(row.get("direction") or 0)) * float(row.get("weight") or 0) * max(0.05, float(row.get("confidence") or 0)),
            default=None,
        )
        top_strategy = str(top_contribution.get("strategy") or "ta_confluence") if top_contribution else "ta_confluence"
        top_bot = str(top_contribution.get("bot") or "") if top_contribution else ""
        top_horizon = str(top_contribution.get("time_horizon") or "short") if top_contribution else "short"

        return {
            "bias": bias,
            "confidence": final_confidence,
            "conviction": self._conviction_label(final_confidence),
            "setup_quality": self._setup_quality(final_confidence),
            "entry_timing": self._entry_timing(final_confidence, final_bias),
            "top_strategy": top_strategy,
            "top_bot": top_bot,
            "time_horizon": top_horizon,
            "weighted_bias": final_bias,
            "bots": contributions,
            "reasoning": f"weighted_bias={final_bias:.3f} confidence={final_confidence:.3f}",
            "legacy_bias_label": bias_label,
        }

    def _arb_execution_note(self, arb_type: str, direction: int) -> str:
        normalized = str(arb_type or "unknown").lower()
        if normalized in {"yes_no_sum", "yes_no_parity", "parity"}:
            return "Buy YES + NO (locked profit)"
        if normalized == "model_vs_market":
            return "YES underpriced vs model" if direction > 0 else "NO underpriced vs model"
        if normalized == "cross_venue":
            return "Binance overpriced vs Hyperliquid" if direction < 0 else "Hyperliquid overpriced vs Binance"
        return "Monitor dislocation and simulate paper execution"

    def _arbitrage_decision(self, symbol: str, signals: list[BotSignal], weights: dict[str, float]) -> dict:
        contributions = [self._serialize_signal(signal, float(weights.get(normalize_strategy(signal.strategy), 0.25))) for signal in signals]
        actionable = [row for row in contributions if abs(float(row.get("direction") or 0)) > 0 and float(row.get("edge") or 0.0) > 0.0]
        best = max(actionable, key=lambda row: (float(row.get("edge") or 0.0), float(row.get("confidence") or 0.0)), default=None)
        arb_type = "none"
        market = symbol
        confidence = 0.0
        edge = 0.0
        note = "No active arbitrage edge"
        if best is not None:
            reasoning = str(best.get("reasoning") or "")
            if "arb_type=" in reasoning:
                arb_type = reasoning.split("arb_type=", 1)[1].split()[0]
            elif str(best.get("strategy")) == "cross_venue":
                arb_type = "cross_venue"
            else:
                arb_type = str(best.get("strategy") or "unknown")
            confidence = float(best.get("confidence") or 0.0)
            edge = float(best.get("edge") or 0.0)
            market = symbol if arb_type == "cross_venue" else str(best.get("bot") or symbol)
            note = self._arb_execution_note(arb_type, int(best.get("direction") or 0))

        return {
            "active": best is not None,
            "type": arb_type,
            "edge": edge,
            "market": market,
            "confidence": confidence,
            "execution_note": note,
            "bots": contributions,
        }

    def _build_explainability(self, directional: dict) -> dict:
        contributions = list(directional.get("bots") or [])
        positive = sorted(
            [row for row in contributions if float(row.get("impact") or 0.0) > 0],
            key=lambda row: float(row.get("impact") or 0.0),
            reverse=True,
        )
        negatives = sorted(
            [row for row in contributions if float(row.get("impact") or 0.0) < 0],
            key=lambda row: float(row.get("impact") or 0.0),
        )

        why_long = [
            f"{row.get('bot')} {float(row.get('impact') or 0.0):+0.2f}"
            for row in positive[:3]
        ]
        why_not_stronger = [
            f"{row.get('bot')} conflict {float(row.get('impact') or 0.0):+0.2f}"
            for row in negatives[:3]
        ]

        confidence = float(directional.get("confidence") or 0.0)
        if confidence < 0.45:
            why_not_stronger.append("low edge")

        return {
            "why_long": why_long,
            "why_not_stronger": why_not_stronger,
        }

    def collect_signals(
        self,
        symbol: str,
        snapshot: dict,
        ta_alignment: float = 0.0,
        market_summary: dict | None = None,
        fv_result=None,
        perp_context: dict | None = None,
        micro_data: dict | None = None,
    ) -> dict[str, list[BotSignal]]:
        grouped: dict[str, list[BotSignal]] = {
            "directional": [],
            "arbitrage": [],
        }
        for bot in self.bots:
            if isinstance(bot, ArbitrageBot):
                signal = bot.generate_signal(symbol, snapshot, market_summary)
            elif isinstance(bot, TABot):
                signal = bot.generate_signal(symbol, snapshot, ta_alignment)
            elif isinstance(bot, ModelVsMarketBot):
                signal = bot.generate_signal(symbol, snapshot, fv_result)
            elif isinstance(bot, PerpArbBot):
                signal = bot.generate_signal(symbol, snapshot, perp_context)
            elif isinstance(bot, ScalperBot):
                signal = bot.generate_signal(symbol, snapshot, micro_data)
            else:
                signal = bot.generate_signal(symbol, snapshot)
            grouped.setdefault(signal.bot_type, []).append(signal)
        return grouped

    def output_decision(
        self,
        symbol: str,
        snapshot: dict,
        ta_alignment: float = 0.0,
        market_summary: dict | None = None,
        fv_result=None,
        perp_context: dict | None = None,
        micro_data: dict | None = None,
    ) -> dict:
        grouped = self.collect_signals(
            symbol,
            snapshot,
            ta_alignment=ta_alignment,
            market_summary=market_summary,
            fv_result=fv_result,
            perp_context=perp_context,
            micro_data=micro_data,
        )
        return self.combine(symbol, grouped, regime=str(snapshot.get("regime") or "CHOP"))

    def combine(self, symbol: str, grouped_signals: dict[str, list[BotSignal]], regime: str | None = None) -> dict:
        directional_weights = self._stream_weights("directional", regime=regime)
        arbitrage_weights = self._stream_weights("arbitrage", regime=regime)
        directional = self._directional_decision(symbol, grouped_signals.get("directional", []), directional_weights)
        arbitrage = self._arbitrage_decision(symbol, grouped_signals.get("arbitrage", []), arbitrage_weights)
        explainability = self._build_explainability(directional)

        contributions = directional.get("bots", [])
        final_bias = float(directional.get("weighted_bias") or 0.0)
        final_confidence = float(directional.get("confidence") or 0.0)
        bias_label = str(directional.get("legacy_bias_label") or "neutral")
        top_bot = str(directional.get("top_bot") or "")
        latest_scalping_signal = next((row for row in contributions if row.get("strategy") == "scalping"), None)

        return {
            "symbol": symbol,
            "final_bias": final_bias,
            "final_confidence": final_confidence,
            "confidence": final_confidence,
            "bias_label": bias_label,
            "contributing_bots": contributions,
            "contributions": contributions,
            "reasoning": str(directional.get("reasoning") or ""),
            "top_bot": top_bot,
            "top_strategy": directional.get("top_strategy"),
            "time_horizon": directional.get("time_horizon"),
            "signals_by_type": {
                key: [
                    self._serialize_signal(
                        signal,
                        float(
                            (directional_weights if key == "directional" else arbitrage_weights).get(
                                normalize_strategy(signal.strategy),
                                0.25,
                            )
                        ),
                    )
                    for signal in value
                ]
                for key, value in grouped_signals.items()
            },
            "directional_decision": directional,
            "arbitrage_decision": arbitrage,
            "decision_explainability": explainability,
            "latest_scalping_signal": latest_scalping_signal,
        }
