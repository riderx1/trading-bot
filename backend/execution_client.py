"""Execution abstraction layer.

Paper mode is the only supported execution path in this project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution_model import evaluate_execution


@dataclass
class ExecutionRequest:
    market_row_id: int
    market_id: str
    market_name: str
    side: str
    signal_sequence_id: int
    trade_key: str
    quantity: float
    notional_usdc: float
    reason_code: str


@dataclass
class ExecutionResult:
    accepted: bool
    reason_code: str
    execution_price: float | None = None
    trade_id: int | None = None


class ExecutionClient:
    mode = "paper"

    def execute_binary_market_order(self, request: ExecutionRequest, market: dict) -> ExecutionResult:
        raise NotImplementedError()

    def submit(self, trade_intent: dict[str, Any], market: dict) -> ExecutionResult:
        raise NotImplementedError()


class PaperExecutionClient(ExecutionClient):
    mode = "paper"
    venue = "paper"
    instrument = "unknown"

    def __init__(self, db, trading_cfg: dict):
        self.db = db
        self.trading_cfg = trading_cfg

    def _request_from_trade_intent(self, trade_intent: dict[str, Any]) -> ExecutionRequest:
        return ExecutionRequest(
            market_row_id=int(trade_intent.get("market_row_id") or 0),
            market_id=str(trade_intent.get("market_id") or ""),
            market_name=str(trade_intent.get("market_name") or ""),
            side=str(trade_intent.get("side") or "YES"),
            signal_sequence_id=int(trade_intent.get("signal_sequence_id") or 0),
            trade_key=str(trade_intent.get("trade_key") or ""),
            quantity=float(trade_intent.get("quantity") or 0.0),
            notional_usdc=float(trade_intent.get("notional_usdc") or 0.0),
            reason_code=str(trade_intent.get("reason_code") or "signal_consensus"),
        )

    def execute_binary_market_order(self, request: ExecutionRequest, market: dict) -> ExecutionResult:
        assert str(self.trading_cfg.get("execution_mode", "paper")).strip().lower() == "paper", (
            "SAFETY: execution_mode must be 'paper'. Refusing to submit trade."
        )
        model = evaluate_execution(
            request.side,
            market,
            self.trading_cfg,
            order_notional_usdc=float(request.notional_usdc),
        )
        if not model["allowed"]:
            return ExecutionResult(accepted=False, reason_code=str(model["reason_code"]))

        execution_price = float(model["execution_price"])
        inserted, trade_id = self.db.insert_trade_if_not_exists(
            trade_key=request.trade_key,
            market_row_id=request.market_row_id,
            market_id=request.market_id,
            market_name=request.market_name,
            trade_type=request.side,
            venue=self.venue,
            price=execution_price,
            quantity=float(request.quantity),
            signal_sequence_id=int(request.signal_sequence_id),
            reason_code=str(request.reason_code),
        )
        if not inserted:
            return ExecutionResult(
                accepted=False,
                reason_code="duplicate_trade_key",
                execution_price=execution_price,
            )
        return ExecutionResult(
            accepted=True,
            reason_code="ok",
            execution_price=execution_price,
            trade_id=trade_id,
        )

    def submit(self, trade_intent: dict[str, Any], market: dict) -> ExecutionResult:
        assert str(self.trading_cfg.get("execution_mode", "paper")).strip().lower() == "paper", (
            "SAFETY: execution_mode must be 'paper'. Refusing to submit trade."
        )
        request = self._request_from_trade_intent(trade_intent)
        return self.execute_binary_market_order(request=request, market=market)


class PolymarketPaperClient(PaperExecutionClient):
    venue = "polymarket"
    instrument = "prediction_market"

    def submit(self, trade_intent: dict[str, Any], market: dict) -> ExecutionResult:
        # Polymarket execution is intentionally disabled in Hyperliquid-only mode.
        return ExecutionResult(accepted=False, reason_code="venue_disabled_polymarket")

    def execute_binary_market_order(self, request: ExecutionRequest, market: dict) -> ExecutionResult:
        # Keep this explicit to block any direct calls that bypass submit().
        return ExecutionResult(accepted=False, reason_code="venue_disabled_polymarket")


class HyperliquidPaperClient(PaperExecutionClient):
    venue = "hyperliquid"
    instrument = "perp"

    def submit(self, trade_intent: dict[str, Any], market: dict) -> ExecutionResult:
        assert str(self.trading_cfg.get("execution_mode", "paper")).strip().lower() == "paper", (
            "SAFETY: execution_mode must be 'paper'. Refusing to submit trade."
        )
        assert trade_intent.get("venue") == "hyperliquid"
        return super().submit(trade_intent=trade_intent, market=market)


def build_execution_client(mode: str, db, trading_cfg: dict) -> ExecutionClient:
    normalized = (mode or "paper").strip().lower()
    if normalized != "paper":
        raise ValueError(
            f"Unsupported execution mode '{mode}'. Only 'paper' mode is allowed."
        )
    return HyperliquidPaperClient(db=db, trading_cfg=trading_cfg)


def build_paper_execution_clients(mode: str, db, trading_cfg: dict) -> tuple[PolymarketPaperClient, HyperliquidPaperClient]:
    normalized = (mode or "paper").strip().lower()
    if normalized != "paper":
        raise ValueError(
            f"Unsupported execution mode '{mode}'. Only 'paper' mode is allowed."
        )
    cfg = dict(trading_cfg)
    cfg["execution_mode"] = "paper"
    return (
        PolymarketPaperClient(db=db, trading_cfg=cfg),
        HyperliquidPaperClient(db=db, trading_cfg=cfg),
    )
