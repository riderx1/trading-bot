"""Execution abstraction layer.

Paper mode is the only supported execution path in this project.
"""

from __future__ import annotations

from dataclasses import dataclass

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


class PaperExecutionClient(ExecutionClient):
    mode = "paper"

    def __init__(self, db, trading_cfg: dict):
        self.db = db
        self.trading_cfg = trading_cfg

    def execute_binary_market_order(self, request: ExecutionRequest, market: dict) -> ExecutionResult:
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


def build_execution_client(mode: str, db, trading_cfg: dict) -> ExecutionClient:
    normalized = (mode or "paper").strip().lower()
    if normalized != "paper":
        raise ValueError(
            f"Unsupported execution mode '{mode}'. Only 'paper' mode is allowed."
        )
    return PaperExecutionClient(db=db, trading_cfg=trading_cfg)
