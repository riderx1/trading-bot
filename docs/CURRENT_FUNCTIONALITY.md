# Current Functionality

This document reflects the current production behavior of the trading bot and dashboard.

## System Overview

- Backend: FastAPI + Python bot workers + SQLite storage.
- Frontend: Vite/React dashboard (restored "nice" UI).
- Runtime mode: paper trading only.

## Trading and Simulation

- Paper trading is enforced in bot runtime.
- Strategy simulation supports:
  - Single-leg paper positions.
  - Cross-venue pair paper positions (Binance vs Hyperliquid perp spread).
- Wallet model per strategy (available, locked, equity).
- Reset endpoint can optionally clear all simulated trade history and rankings.

## Strategy Coverage

- momentum_trend
- ta_confluence
- reversal_fade
- arbitrage
- model_vs_market
- perp_arb

## Key Backend Endpoints

### Health and status

- `GET /status`
- `GET /health/dependencies`

### Wallets and paper trading

- `GET /paper-wallets`
- `POST /paper-wallets/reset?confirm=true&clear_history=true|false`
- `GET /paper-trades/active`

### Performance and trades

- `GET /performance/summary`
- `GET /performance/recent-trades`
- `GET /simulated-trades`
- `GET /strategy/rankings`

### Opportunity and basis data

- `GET /opportunities`
- `GET /arbitrage/opportunities`
- `GET /perp-basis/latest`
- `GET /perp-basis/history`

## Dashboard Features (Current UI)

- Decision hero and orchestra breakdown.
- Wallet panel with reset button.
- Signals panel and opportunities panel.
- Arbitrage panel and perp basis panel.
- Performance card:
  - Trades
  - Win Rate
  - Total PnL
  - Drawdown (currency display)
- Active Trades card:
  - Open trade count
  - Side (long/short or pair side)
  - Unrealized PnL
  - Stake and duration
  - Recent closed trades table with win/loss and PnL

## Notes

- After a reset with `clear_history=true`, trade counts and performance start from zero.
- Trade counters and performance represent simulated trades only.
- Deployment cadence is Git-based: push from laptop repo, pull on mini PC, then restart backend/dashboard scripts.
