"""Simulation engine for signal-based paper trade outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime

from strategy_taxonomy import normalize_strategy


@dataclass
class SimPosition:
    symbol: str
    strategy: str
    timeframe: str
    direction: int
    entry_price: float
    entry_ts: str
    quantity: float
    stake_usdc: float
    signal_strength: str
    regime: str


@dataclass
class SimPairPosition:
    symbol: str
    strategy: str
    direction: int            # +1 long Binance / short HL, -1 short Binance / long HL
    entry_spread: float       # normalized spread = (bin_perp - hl_perp) / ref_price
    entry_binance_price: float
    entry_hl_price: float
    entry_funding_spread: float
    entry_ts: str
    stake_usdc: float
    signal_strength: str
    regime: str


class SimulationEngine:
    """Config-driven simulated trade lifecycle for signal performance tracking."""

    STATE_KEY = "sim_open_positions"
    PAIR_STATE_KEY = "sim_open_pair_positions"
    WALLET_STATE_KEY = "sim_wallets"

    def __init__(self, db, config: dict):
        self.db = db
        sim_cfg = config.get("simulation", {})
        self.enabled = bool(sim_cfg.get("enabled", True))
        self.exit_cfg = sim_cfg.get("exit_rules", {})
        self.time_windows_sec = [int(value) for value in self.exit_cfg.get("time_windows_seconds", [3600, 14400, 86400])]
        self.tp_pct = float(self.exit_cfg.get("take_profit_pct", 0.02))
        self.sl_pct = float(self.exit_cfg.get("stop_loss_pct", 0.01))
        self.opposite_signal_exit = bool(self.exit_cfg.get("opposite_signal_exit", True))

        wallet_cfg = sim_cfg.get("paper_wallet", {})
        self.wallet_enabled = bool(wallet_cfg.get("enabled", True))
        self.wallet_default_balance = float(wallet_cfg.get("balance_per_bot_usdc", 10.0))
        self.wallet_min_notional = float(wallet_cfg.get("min_notional_usdc", 1.0))
        self.wallet_max_position = float(wallet_cfg.get("max_position_per_trade_usdc", self.wallet_default_balance))
        self.wallet_min_edge = float(wallet_cfg.get("min_edge_for_position", 0.001))
        self.wallet_strategies = [
            normalize_strategy(str(name))
            for name in wallet_cfg.get(
                "strategies",
                [
                    "momentum",
                    "ta_confluence",
                    "reversal",
                    "yes_no",
                    "cross_venue",
                    "model_vs_market",
                    "scalping",
                ],
            )
            if str(name).strip()
        ]
        self.default_slippage_bps = float(wallet_cfg.get("slippage_bps", 8.0))

        self.positions: list[SimPosition] = []
        self.pair_positions: list[SimPairPosition] = []
        self.wallets: dict[str, float] = {}
        self._load_wallets()
        self._load_positions()
        self._load_pair_positions()

    def _ensure_strategy_wallet(self, strategy: str):
        key = normalize_strategy(str(strategy or "ta_confluence"))
        if key not in self.wallets:
            self.wallets[key] = self.wallet_default_balance

    def _load_wallets(self):
        state = self.db.get_bot_state(self.WALLET_STATE_KEY, "")
        if state:
            try:
                payload = json.loads(state)
                if isinstance(payload, dict):
                    self.wallets = {normalize_strategy(str(k)): float(v) for k, v in payload.items()}
                else:
                    self.wallets = {}
            except (json.JSONDecodeError, TypeError, ValueError):
                self.wallets = {}
        else:
            self.wallets = {}

        for strategy in self.wallet_strategies:
            self._ensure_strategy_wallet(strategy)

    def _save_wallets(self):
        self.db.set_bot_state(self.WALLET_STATE_KEY, json.dumps(self.wallets))

    def reset_wallets(self, clear_history: bool = False) -> dict:
        self.wallets = {strategy: float(self.wallet_default_balance) for strategy in self.wallet_strategies}
        self.positions = []
        self.pair_positions = []
        self._save_wallets()
        self._save_positions()
        self._save_pair_positions()

        if clear_history:
            self.db.clear_simulated_trades()
            self.db.clear_strategy_performance()
        else:
            self.db.recompute_strategy_performance()

        snapshot = self.get_wallet_snapshot()
        snapshot["history_cleared"] = bool(clear_history)
        return snapshot

    def _load_positions(self):
        state = self.db.get_bot_state(self.STATE_KEY, "[]")
        try:
            payload = json.loads(state) if state else []
        except json.JSONDecodeError:
            payload = []
        self.positions = []
        for item in payload:
            try:
                item.setdefault("timeframe", "consensus")
                item.setdefault("quantity", 0.0)
                item.setdefault("stake_usdc", 0.0)
                self.positions.append(SimPosition(**item))
            except TypeError:
                continue

    def _save_positions(self):
        self.db.set_bot_state(
            self.STATE_KEY,
            json.dumps([asdict(position) for position in self.positions]),
        )

    def _load_pair_positions(self):
        state = self.db.get_bot_state(self.PAIR_STATE_KEY, "[]")
        try:
            payload = json.loads(state) if state else []
        except json.JSONDecodeError:
            payload = []
        self.pair_positions = []
        for item in payload:
            try:
                self.pair_positions.append(SimPairPosition(**item))
            except TypeError:
                continue

    def _save_pair_positions(self):
        self.db.set_bot_state(
            self.PAIR_STATE_KEY,
            json.dumps([asdict(position) for position in self.pair_positions]),
        )

    def get_wallet_snapshot(self) -> dict:
        locked_by_strategy: dict[str, float] = {}
        for position in self.positions:
            locked_by_strategy[position.strategy] = (
                locked_by_strategy.get(position.strategy, 0.0) + float(position.stake_usdc)
            )
        for position in self.pair_positions:
            locked_by_strategy[position.strategy] = (
                locked_by_strategy.get(position.strategy, 0.0) + float(position.stake_usdc)
            )

        details = {}
        for strategy, available in self.wallets.items():
            locked = float(locked_by_strategy.get(strategy, 0.0))
            details[strategy] = {
                "available_usdc": round(float(available), 6),
                "locked_usdc": round(locked, 6),
                "equity_usdc": round(float(available) + locked, 6),
            }

        total_available = sum(item["available_usdc"] for item in details.values())
        total_locked = sum(item["locked_usdc"] for item in details.values())
        return {
            "bots": details,
            "total_available_usdc": round(total_available, 6),
            "total_locked_usdc": round(total_locked, 6),
            "total_equity_usdc": round(total_available + total_locked, 6),
        }

    def get_active_trades_snapshot(
        self,
        latest_spot_prices: dict[str, float] | None = None,
        latest_perp_context: dict[str, dict] | None = None,
    ) -> list[dict]:
        latest_spot_prices = latest_spot_prices or {}
        latest_perp_context = latest_perp_context or {}
        now = datetime.utcnow()
        rows: list[dict] = []

        for position in self.positions:
            current_price = latest_spot_prices.get(position.symbol)
            unrealized_pnl = None
            if current_price is not None:
                unrealized_pnl = (
                    (float(current_price) - float(position.entry_price))
                    * float(position.quantity)
                    * int(position.direction)
                )

            opened_at = datetime.fromisoformat(position.entry_ts)
            duration_seconds = max(0, int((now - opened_at).total_seconds()))

            rows.append(
                {
                    "trade_type": "single",
                    "symbol": position.symbol,
                    "strategy": position.strategy,
                    "direction": int(position.direction),
                    "side": "LONG" if int(position.direction) > 0 else "SHORT",
                    "entry_price": float(position.entry_price),
                    "current_price": (float(current_price) if current_price is not None else None),
                    "quantity": float(position.quantity),
                    "stake_usdc": float(position.stake_usdc),
                    "unrealized_pnl": unrealized_pnl,
                    "opened_at": position.entry_ts,
                    "duration_seconds": duration_seconds,
                    "signal_strength": position.signal_strength,
                    "regime": position.regime,
                    "timeframe": position.timeframe,
                }
            )

        for position in self.pair_positions:
            context = latest_perp_context.get(position.symbol, {}) or {}
            current_binance_price = context.get("binance_perp_price")
            current_hl_price = context.get("hl_perp_price")
            current_funding_spread = context.get("funding_spread")

            spread_now = None
            unrealized_pnl = None
            if current_binance_price is not None and current_hl_price is not None:
                ref_price = max(float(current_binance_price), float(current_hl_price), 1e-9)
                spread_now = (float(current_binance_price) - float(current_hl_price)) / ref_price

                spread_pnl = (
                    (spread_now - float(position.entry_spread))
                    * float(position.stake_usdc)
                    * int(position.direction)
                )
                funding_spread_now = float(current_funding_spread or 0.0)
                avg_funding_spread = (
                    float(position.entry_funding_spread) + funding_spread_now
                ) / 2.0
                opened_at = datetime.fromisoformat(position.entry_ts)
                elapsed_hours = max(0.0, (now - opened_at).total_seconds() / 3600.0)
                funding_carry = -int(position.direction) * avg_funding_spread * elapsed_hours * float(position.stake_usdc)
                unrealized_pnl = spread_pnl + funding_carry

            opened_at = datetime.fromisoformat(position.entry_ts)
            duration_seconds = max(0, int((now - opened_at).total_seconds()))

            rows.append(
                {
                    "trade_type": "pair",
                    "symbol": position.symbol,
                    "strategy": position.strategy,
                    "direction": int(position.direction),
                    "side": "LONG_BINANCE_SHORT_HL" if int(position.direction) > 0 else "SHORT_BINANCE_LONG_HL",
                    "entry_price": float(position.entry_binance_price),
                    "current_price": (float(current_binance_price) if current_binance_price is not None else None),
                    "quantity": None,
                    "stake_usdc": float(position.stake_usdc),
                    "unrealized_pnl": unrealized_pnl,
                    "opened_at": position.entry_ts,
                    "duration_seconds": duration_seconds,
                    "signal_strength": position.signal_strength,
                    "regime": position.regime,
                    "timeframe": "pair_spread",
                    "entry_spread": float(position.entry_spread),
                    "current_spread": spread_now,
                    "entry_binance_price": float(position.entry_binance_price),
                    "entry_hl_price": float(position.entry_hl_price),
                    "current_binance_price": (
                        float(current_binance_price)
                        if current_binance_price is not None
                        else None
                    ),
                    "current_hl_price": (
                        float(current_hl_price)
                        if current_hl_price is not None
                        else None
                    ),
                }
            )

        rows.sort(key=lambda row: row.get("opened_at") or "", reverse=True)
        return rows

    def _allocate_stake(
        self,
        strategy: str,
        entry_price: float,
        confidence: float,
        edge: float,
        risk_factor: float,
    ) -> tuple[float, float]:
        strategy = normalize_strategy(strategy)
        self._ensure_strategy_wallet(strategy)
        if not self.wallet_enabled:
            notional = max(self.wallet_default_balance, self.wallet_min_notional)
            return notional, notional / max(entry_price, 1e-9)

        available = float(self.wallets.get(strategy, 0.0))
        calibrated_confidence = max(0.0, min(0.75, float(confidence)))
        calibrated_edge = max(0.0, min(0.10, float(edge)))
        calibrated_risk = max(0.05, min(1.0, float(risk_factor)))

        if calibrated_edge < self.wallet_min_edge:
            return 0.0, 0.0

        stake = available * calibrated_confidence * calibrated_edge * calibrated_risk
        stake = min(stake, self.wallet_max_position, available)
        if stake < self.wallet_min_notional:
            return 0.0, 0.0
        quantity = stake / max(entry_price, 1e-9)
        self.wallets[strategy] = max(0.0, available - stake)
        return stake, quantity

    def apply_slippage(self, price: float, spread_bps: float, side: str) -> float:
        slip = float(price) * (max(0.0, float(spread_bps)) / 10000.0)
        if str(side).upper() == "BUY":
            return float(price) + slip
        return float(price) - slip

    def _close_position(self, position: SimPosition, exit_price: float, exit_ts: str, spread_bps: float = 0.0):
        entry_dt = datetime.fromisoformat(position.entry_ts)
        exit_dt = datetime.fromisoformat(exit_ts)
        duration_seconds = max(1, int((exit_dt - entry_dt).total_seconds()))
        close_side = "SELL" if int(position.direction) > 0 else "BUY"
        exit_exec_price = self.apply_slippage(float(exit_price), spread_bps, close_side)
        pnl = (float(exit_exec_price) - float(position.entry_price)) * float(position.quantity) * int(position.direction)
        strategy = str(position.strategy or "ta_confluence")
        self._ensure_strategy_wallet(strategy)
        self.wallets[strategy] = max(0.0, float(self.wallets.get(strategy, 0.0)) + float(position.stake_usdc) + float(pnl))
        self.db.insert_simulated_trade(
            symbol=position.symbol,
            strategy=position.strategy,
            entry_price=position.entry_price,
            exit_price=exit_exec_price,
            direction=position.direction,
            pnl=pnl,
            duration_seconds=duration_seconds,
            signal_strength=position.signal_strength,
            regime=position.regime,
            timeframe=position.timeframe,
            entry_timestamp=position.entry_ts,
            exit_timestamp=exit_ts,
            timestamp=exit_ts,
        )

    def _close_pair_position(
        self,
        position: SimPairPosition,
        current_spread: float,
        current_binance_price: float,
        current_hl_price: float,
        current_funding_spread: float,
        exit_ts: str,
    ):
        entry_dt = datetime.fromisoformat(position.entry_ts)
        exit_dt = datetime.fromisoformat(exit_ts)
        duration_seconds = max(1, int((exit_dt - entry_dt).total_seconds()))
        elapsed_hours = duration_seconds / 3600.0

        # Spread mean-reversion PnL + simple funding carry approximation.
        spread_pnl = (
            (current_spread - float(position.entry_spread))
            * float(position.stake_usdc)
            * int(position.direction)
        )
        avg_funding_spread = (
            float(position.entry_funding_spread) + float(current_funding_spread)
        ) / 2.0
        funding_carry = -int(position.direction) * avg_funding_spread * elapsed_hours * float(position.stake_usdc)
        pnl = spread_pnl + funding_carry

        strategy = str(position.strategy or "cross_venue")
        self._ensure_strategy_wallet(strategy)
        self.wallets[strategy] = max(
            0.0,
            float(self.wallets.get(strategy, 0.0)) + float(position.stake_usdc) + float(pnl),
        )
        self.db.insert_simulated_trade(
            symbol=position.symbol,
            strategy=position.strategy,
            entry_price=float(position.entry_binance_price),
            exit_price=float(current_binance_price),
            direction=int(position.direction),
            pnl=pnl,
            duration_seconds=duration_seconds,
            signal_strength=position.signal_strength,
            regime=position.regime,
            timeframe="pair_spread",
            entry_timestamp=position.entry_ts,
            exit_timestamp=exit_ts,
            timestamp=exit_ts,
        )

    def on_signal(
        self,
        symbol: str,
        strategy: str,
        direction: int,
        entry_price: float,
        timestamp: str,
        signal_strength: str,
        regime: str,
        timeframe: str | None = None,
        confidence: float = 0.5,
        edge: float = 0.01,
        risk_factor: float = 0.5,
        max_duration_minutes: int | None = None,
        spread_bps: float = 0.0,
    ):
        if not self.enabled:
            return
        strategy = normalize_strategy(strategy)

        now_ts = timestamp
        remaining_positions: list[SimPosition] = []

        for position in self.positions:
            if position.symbol != symbol or position.strategy != strategy:
                remaining_positions.append(position)
                continue

            should_close = False
            close_reason = ""
            current_pnl_pct = ((entry_price - position.entry_price) / max(position.entry_price, 1e-9)) * position.direction
            elapsed_sec = int((datetime.fromisoformat(now_ts) - datetime.fromisoformat(position.entry_ts)).total_seconds())

            if self.opposite_signal_exit and position.direction != direction:
                should_close = True
                close_reason = "opposite_signal"
            elif current_pnl_pct >= self.tp_pct:
                should_close = True
                close_reason = "take_profit"
            elif current_pnl_pct <= -self.sl_pct:
                should_close = True
                close_reason = "stop_loss"
            elif max_duration_minutes is not None and elapsed_sec >= int(max_duration_minutes) * 60:
                should_close = True
                close_reason = "max_duration"
            elif self.time_windows_sec and elapsed_sec >= min(self.time_windows_sec):
                should_close = True
                close_reason = "time_window"

            if should_close:
                self._close_position(position, exit_price=entry_price, exit_ts=now_ts, spread_bps=spread_bps)
            else:
                remaining_positions.append(position)

        self.positions = remaining_positions

        existing_open = any(
            position.symbol == symbol and position.strategy == strategy
            for position in self.positions
        )

        if direction in (-1, 1) and not existing_open:
            open_side = "BUY" if int(direction) > 0 else "SELL"
            entry_exec_price = self.apply_slippage(float(entry_price), spread_bps, open_side)
            stake_usdc, quantity = self._allocate_stake(
                strategy,
                float(entry_exec_price),
                confidence=confidence,
                edge=edge,
                risk_factor=risk_factor,
            )
            if stake_usdc < self.wallet_min_notional or quantity <= 0:
                self._save_wallets()
                self._save_positions()
                self.db.recompute_strategy_performance()
                return
            self.positions.append(
                SimPosition(
                    symbol=symbol,
                    strategy=strategy,
                    timeframe=str(timeframe or "consensus"),
                    direction=direction,
                    entry_price=float(entry_exec_price),
                    entry_ts=now_ts,
                    quantity=float(quantity),
                    stake_usdc=float(stake_usdc),
                    signal_strength=signal_strength,
                    regime=regime,
                )
            )

        self._save_wallets()
        self._save_positions()
        self.db.recompute_strategy_performance()

    def on_pair_signal(
        self,
        symbol: str,
        strategy: str,
        direction: int,
        binance_price: float,
        hl_price: float,
        funding_spread: float,
        timestamp: str,
        signal_strength: str,
        regime: str,
        confidence: float = 0.5,
        edge_bp: float = 0.0,
        risk_factor: float = 0.5,
        entry_threshold_bp: float = 5.0,
        exit_threshold_bp: float = 2.0,
        stop_loss_bp: float = 20.0,
    ):
        """
        Simulate a perp pair trade between Binance and Hyperliquid.

        direction:
          +1 → long Binance / short HL
          -1 → short Binance / long HL
        """
        if not self.enabled:
            return
        strategy = normalize_strategy(strategy)
        if not binance_price or not hl_price:
            return

        ref_price = max(float(binance_price), float(hl_price), 1e-9)
        current_spread = (float(binance_price) - float(hl_price)) / ref_price
        current_bp = current_spread * 10_000.0

        remaining_positions: list[SimPairPosition] = []
        for position in self.pair_positions:
            if position.symbol != symbol or position.strategy != strategy:
                remaining_positions.append(position)
                continue

            should_close = False
            if abs(current_bp) <= exit_threshold_bp:
                should_close = True
            elif position.direction != direction and abs(current_bp) >= entry_threshold_bp:
                should_close = True
            else:
                adverse_bp = (current_spread - float(position.entry_spread)) * 10_000.0 * int(position.direction)
                if adverse_bp <= -abs(stop_loss_bp):
                    should_close = True

            if should_close:
                self._close_pair_position(
                    position,
                    current_spread=current_spread,
                    current_binance_price=float(binance_price),
                    current_hl_price=float(hl_price),
                    current_funding_spread=float(funding_spread),
                    exit_ts=timestamp,
                )
            else:
                remaining_positions.append(position)

        self.pair_positions = remaining_positions

        existing_open = any(
            position.symbol == symbol and position.strategy == strategy
            for position in self.pair_positions
        )
        if (
            direction in (-1, 1)
            and not existing_open
            and abs(edge_bp) >= abs(entry_threshold_bp)
        ):
            edge = max(0.0, min(0.10, abs(edge_bp) / 10_000.0))
            stake_usdc, _ = self._allocate_stake(
                strategy,
                float(binance_price),
                confidence=confidence,
                edge=edge,
                risk_factor=risk_factor,
            )
            if stake_usdc >= self.wallet_min_notional:
                self.pair_positions.append(
                    SimPairPosition(
                        symbol=symbol,
                        strategy=strategy,
                        direction=int(direction),
                        entry_spread=current_spread,
                        entry_binance_price=float(binance_price),
                        entry_hl_price=float(hl_price),
                        entry_funding_spread=float(funding_spread),
                        entry_ts=timestamp,
                        stake_usdc=float(stake_usdc),
                        signal_strength=signal_strength,
                        regime=regime,
                    )
                )

        self._save_wallets()
        self._save_pair_positions()
        self.db.recompute_strategy_performance()
