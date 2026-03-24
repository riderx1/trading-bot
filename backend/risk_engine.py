"""Risk checks for position and exposure controls."""

from dataclasses import dataclass


@dataclass
class RiskResult:
    allowed: bool
    reason_code: str


class RiskEngine:
    def __init__(self, cfg: dict):
        self.execution_mode = str(cfg.get("execution_mode", "paper")).strip().lower()
        self.max_total_exposure = float(cfg["max_total_exposure_usdc"])
        self.max_per_market_exposure = float(cfg["max_per_market_exposure_usdc"])
        self.max_cluster_exposure = float(cfg["max_cluster_exposure_usdc"])
        # Per-arb-type position size caps.
        # model_vs_market is tighter (unproven model) until win-rate data is collected.
        # yes_no_sum is full-sized (risk-free in theory).
        # cross_venue is most conservative (execution risk).
        self._arb_type_max_usdc: dict[str, float] = {
            "model_vs_market": float(cfg.get("arb_model_vs_market_max_usdc", self.max_per_market_exposure * 0.30)),
            "yes_no_sum": float(cfg.get("arb_yes_no_sum_max_usdc", self.max_per_market_exposure)),
            "cross_venue": float(cfg.get("arb_cross_venue_max_usdc", self.max_per_market_exposure * 0.20)),
        }

    def can_open_position(
        self,
        total_exposure_usdc: float,
        market_exposure_usdc: float,
        cluster_exposure_usdc: float,
        order_notional_usdc: float,
    ) -> RiskResult:
        if self.execution_mode != "paper":
            return RiskResult(False, "risk_mode_not_paper")
        if total_exposure_usdc + order_notional_usdc > self.max_total_exposure:
            return RiskResult(False, "risk_limit_total_exposure")
        if market_exposure_usdc + order_notional_usdc > self.max_per_market_exposure:
            return RiskResult(False, "risk_limit_market_exposure")
        if cluster_exposure_usdc + order_notional_usdc > self.max_cluster_exposure:
            return RiskResult(False, "risk_limit_cluster_exposure")
        return RiskResult(True, "ok")

    def can_add_to_position(
        self,
        total_exposure_usdc: float,
        market_exposure_usdc: float,
        cluster_exposure_usdc: float,
        order_notional_usdc: float,
    ) -> RiskResult:
        return self.can_open_position(
            total_exposure_usdc,
            market_exposure_usdc,
            cluster_exposure_usdc,
            order_notional_usdc,
        )

    def get_arb_type_max_usdc(self, arb_type: str) -> float:
        """Return the max notional (USDC) allowed for the given arb type."""
        return self._arb_type_max_usdc.get(arb_type, self.max_per_market_exposure)

    def can_open_arb_position(
        self,
        arb_type: str,
        total_exposure_usdc: float,
        market_exposure_usdc: float,
        cluster_exposure_usdc: float,
        order_notional_usdc: float,
    ) -> RiskResult:
        """
        Check whether an arbitrage position can be opened.

        Applies all standard exposure checks PLUS an arb-type-specific
        notional cap that is tighter for unproven strategies.
        """
        arb_cap = self.get_arb_type_max_usdc(arb_type)
        if market_exposure_usdc + order_notional_usdc > arb_cap:
            return RiskResult(False, f"risk_limit_arb_type_{arb_type}")
        return self.can_open_position(
            total_exposure_usdc,
            market_exposure_usdc,
            cluster_exposure_usdc,
            order_notional_usdc,
        )
