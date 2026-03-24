# Paper Trading Implementation Spec

This file captures the full implementation brief and constraints for this project.

## Core Constraint

Execution must remain 100% simulated. No real exchange order placement is allowed.

## Architecture Context

- Frontend: Vite/React dashboard on mini PC (port 3000)
- Backend: FastAPI (`api.py`, port 8000)
- Core engine: Python bot engine + SQLite (`trading_bot.db`)

## Existing System Summary

### BinanceClient

- Fetches OHLCV for BTC/ETH/SOL across 5m/15m/1h/4h/1d.
- Produces per-timeframe trend direction and confidence.
- Aggregates into multi-timeframe consensus trend.

### TechnicalScanner

- Runs RSI, Bollinger Bands, and other indicators.
- Boosts or penalizes consensus confidence.

### PolymarketClient

- Fetches up to approximately 1000 active crypto markets.
- Filters by:
  - Horizon (blocks long over 30 days, medium capped at 65% confidence).
  - Directional language (up/down style markets only).

### Orchestrator Bots

- TrendBot: follows strong consensus.
- TABot: confirms or boosts trend when TA aligns.
- ReversalBot: fades overextended confidence.
- ArbitrageBot: YES+NO sum mispricing below 0.98.

### RiskEngine

- Portfolio exposure caps.
- Per-market and per-cluster caps.
- Spread and liquidity filters.
- 15-minute per-market cooldown.

### SimulationEngine

- Opens virtual positions per strategy.
- Tracks entries, exits, TP/SL/time/flip exits.

### API Endpoints (already present)

- GET: /status, /signals, /opportunities, /paper-wallets, /performance/summary, /strategy/rankings, /logs
- POST: /paper-wallets/reset

### Dashboard (already present)

- Decision engine
- Multi-timeframe signals
- Portfolio
- Strategy performance
- Logs

## New Requirements

All requirements below must remain paper-trading only.

### 1) Global paper-trading mode and execution abstraction

- Introduce a single execution interface (ExecutionClient).
- Implement only PaperExecutionClient.
- PaperExecutionClient routes all orders to SimulationEngine with realistic fill modeling (bid/ask and basic slippage).
- Do not implement or call real trading endpoints.
- Add global MODE=paper and enforce:
  - FastAPI startup fails if any non-paper client is configured.
  - Any function that could send orders must route through ExecutionClient.
- /status should expose current mode.
- Dashboard should show prominent PAPER TRADING ONLY badge.

### 2) Hyperliquid integration (read-only)

- Add HyperliquidClient for public market data only.
- Fetch:
  - Perp prices for BTC/ETH/SOL
  - Funding rates and funding history
  - Optional order book depth and open interest
- Persist basis and funding spread data in DB.
- No authenticated trading.

### 3) FairValueEngine (probability model)

Build a deterministic, pluggable heuristic module that outputs:

- p_model
- confidence

Inputs per market:

- Binance trend + confidence
- Technical indicators
- Hyperliquid vs Binance basis and funding
- Market metadata (horizon, type, liquidity)

Persist to a fair value table (for example market_fair_values).

### 4) Extended ArbitrageBot and PerpArbBot

#### Extended ArbitrageBot

- Keep YES+NO sum arb as arb_type=yes_no_sum.
- Add model-vs-market mispricing:
  - Compare p_model vs p_mkt.
  - Trigger opportunities when threshold exceeded.
- Store:
  - arb_type
  - p_model
  - p_mkt
  - edge_bp
  - why
- Route via RiskEngine and SimulationEngine only.

#### PerpArbBot

- Simulate Binance vs Hyperliquid perp basis and funding arb.
- Open synthetic long/short matched-notional pair when spread and funding conditions are met.
- Exit on spread mean reversion or funding deterioration.
- Track as synthetic pair positions in SimulationEngine and DB.
- No real exchange orders.

### 5) ScalpBot family (paper-only)

#### PolymarketScalpBot

- Use high-frequency order book/trade data.
- Patterns:
  - Dump-and-hedge micro-arb
  - Spread capture
- Strict constraints:
  - very small notional
  - short max holding time
  - strict per-market and per-window limits

#### HyperliquidScalpBot

- Use 1s-5s microstructure signals.
- Modes:
  - range mean-reversion
  - breakout from consolidation
- Route all execution through PaperExecutionClient.

#### Engine Integration

- Run scalp loop at 1-3 second cadence.
- Track scalp trades via timeframe=scalp or dedicated table.
- Add scalp-specific risk controls (per-minute count, daily loss caps).

### 6) Orchestrator and RiskEngine updates

- Orchestrator adds:
  - model-vs-market path
  - PerpArbBot
  - PolymarketScalpBot
  - HyperliquidScalpBot
- Strategy weighting uses strategy performance and market regime context.
- RiskEngine must enforce MODE=paper safety check before any trade acceptance.

### 7) API and UI additions

- New endpoints:
  - GET /arbitrage/opportunities
  - GET /scalp/performance
- Extend opportunities payload to optionally include:
  - p_model
  - p_mkt
  - p_fair
  - arb_type
- Dashboard additions:
  - Arbitrage panel with model-vs-market, YES+NO, and perp opportunities
  - Scalping panel with open scalp trades and recent performance
  - Visible global mode indicator

## Implementation Style Expectations

When implementing future changes against this spec:

- Propose clear module designs in Python and TypeScript.
- Deliver concrete incremental changes.
- Add TODO placeholders for future live-trading plug points, without implementing live execution.
- Keep all execution paths paper-only.
