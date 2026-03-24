# Trading Bot API Documentation

## 1. BASE URL

```
http://0.0.0.0:8000
```

Or when running locally:
```
http://127.0.0.1:8000
```

**Configuration** (`config.json`):
```json
"api": {
  "host": "0.0.0.0",
  "port": 8000
}
```

---

## 2. ALL ENDPOINTS

### Health & Status

**GET /status** → Bot status and health
- Query params: `symbol` (string, default: "BTCUSDT")
- Response: Bot status, uptime, thread health, paper wallets, latest signals, orchestrated decisions

**GET /health/dependencies** → Dependency health status
- Response: Thread alive status, signal age

**GET /ta/status** → Technical scanner status
- Response: Scanner enabled flag, thread status, pair info, exchanges

---

### Paper Wallet Management

**GET /paper-wallets** → Paper wallet balances by bot/strategy
- Request body: none
- Response: Wallet snapshot with per-bot balances, locked amounts, equity

**POST /paper-wallets/reset** → Reset paper wallets (optional history clear)
- Query params:
  - `confirm` (boolean, required): Must be `true` to execute reset
  - `clear_history` (boolean, optional, default: false): Clear simulated trades and rankings
- Request body: none
- Response: Reset status, message, result wallet snapshot

---

### Signal & Market Data

**GET /signals** → Latest BTC trend signals
- Query params: `limit` (1-200, default: 20), `symbol` (default: "BTCUSDT")
- Response: Array of signal records with trend, confidence, timeframe, strategy

**GET /markets** → Latest Polymarket price snapshots
- Query params: `limit` (1-500, default: 50), `symbol` (default: "BTCUSDT")
- Response: Array of market records (market_name, yes_price, no_price, timestamps)

**GET /opportunities** → Signal opportunities
- Query params: `limit` (1-1000, default: 100), `symbol` (default: "BTCUSDT")
- Response: Array of opportunity records (edge, confidence, side, trend, reasoning)

---

### Trade History

**GET /trades** → Trade history
- Query params: `limit` (1-500, default: 50)
- Response: Array of trade records

**GET /simulated-trades** → Simulated trades
- Query params:
  - `limit` (1-2000, default: 200)
  - `symbol` (optional): Filter by symbol
  - `strategy` (optional): Filter by strategy
- Response: Array of simulated trade records

**GET /positions** → Open positions
- Response: Array of open positions + total exposure USDC

---

### Performance & Analytics

**GET /performance/summary** → Performance summary
- Response: Aggregated metrics (win_rate, total_pnl, sharpe_ratio, max_drawdown, as_of timestamp)

**GET /performance/by-strategy** → Performance by strategy
- Response: Array of records (strategy, trade_count, win_rate, avg_pnl, total_pnl)

**GET /performance/by-symbol** → Performance by symbol
- Response: Array of records (symbol, trade_count, win_rate, avg_pnl, total_pnl)

**GET /performance/recent-trades** → Recent simulated trades
- Query params:
  - `limit` (1-1000, default: 50)
  - `symbol` (optional)
  - `strategy` (optional)
- Response: Array of recent trade records

**GET /strategy/rankings** → Strategy rankings
- Query params: `recompute` (boolean, optional): Recalculate rankings on-the-fly
- Response: Array of strategy records (strategy, overall_score, sample_count)

**GET /strategies/rankings** → Strategy rankings (alias for /strategy/rankings)
- Query params: `recompute` (boolean, optional)
- Response: Array of strategy records

---

### History & Logs

**GET /history/signals** → Signal history with filters
- Query params:
  - `limit` (1-2000, default: 200)
  - `symbol` (optional): Filter by symbol (auto-uppercased)
  - `timeframe` (optional): Filter by timeframe
  - `strategy` (optional): Filter by strategy
  - `start_date` (optional): ISO datetime lower bound
  - `end_date` (optional): ISO datetime upper bound
- Response: Array of signal records matching filters

**GET /history/opportunities** → Opportunity history with filters
- Query params:
  - `limit` (1-2000, default: 200)
  - `symbol` (optional)
  - `timeframe` (optional)
  - `strategy` (optional)
  - `start_date` (optional)
  - `end_date` (optional)
- Response: Array of opportunity records

**GET /history/trades** → Simulated trade history with filters
- Query params:
  - `limit` (1-2000, default: 200)
  - `symbol` (optional)
  - `strategy` (optional)
  - `start_date` (optional)
  - `end_date` (optional)
- Response: Array of trade records

**GET /logs** → Application log entries
- Query params: `limit` (1-1000, default: 100)
- Response: Array of log entries with message, level, timestamp

---

### Technical Analysis

**GET /ta/alerts** → Technical analysis alerts
- Query params: `limit` (1-300, default: 50)
- Response: Array of TA alert records (alert_type, symbol, timeframe, description)

---

## 3. KEY RESPONSE EXAMPLES

### GET /status

```json
{
  "status": "running",
  "mode": "signal",
  "emit_signals_only": false,
  "paper_trading": true,
  "paper_wallets": {
    "total_equity_usdc": 40.0,
    "total_locked_usdc": 0.0,
    "total_available_usdc": 40.0,
    "bots": {
      "momentum_trend": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      },
      "ta_confluence": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      },
      "reversal_fade": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      },
      "arbitrage": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      }
    }
  },
  "symbol": "BTCUSDT",
  "supported_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "signal_intervals": ["5m", "15m", "1h", "4h", "1d"],
  "market_focus": ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto"],
  "latest_signal": {
    "id": 1254,
    "sequence_id": 98,
    "source": "binance",
    "strategy": "momentum_trend",
    "timeframe": "1h",
    "trend": "bullish",
    "confidence": 0.5505524851387076,
    "signal_strength": "medium",
    "reasoning": "HTF confluence (1d bullish) + higher_timeframe_boost",
    "regime": "uptrend",
    "move_pct": 0.0245,
    "timestamp": "2026-03-24T14:32:10.123456"
  },
  "orchestrated_decision": {
    "symbol": "BTCUSDT",
    "direction": 1,
    "trend": "bullish",
    "confidence": 0.55,
    "reasoning": "consensus from 4 bots",
    "timestamp": "2026-03-24T14:32:10.123456",
    "bots": {
      "TrendBot": {
        "strategy": "momentum_trend",
        "direction": 1,
        "confidence": 0.5505524851387076,
        "reasoning": "consensus=bullish"
      },
      "ReversalBot": {
        "strategy": "reversal_fade",
        "direction": 0,
        "confidence": 0.2,
        "reasoning": "no reversal setup"
      },
      "TABot": {
        "strategy": "ta_confluence",
        "direction": 1,
        "confidence": 0.15,
        "reasoning": "weak TA alignment"
      },
      "ArbitrageBot": {
        "strategy": "arbitrage",
        "direction": 0,
        "confidence": 0.1,
        "reasoning": "no market summary"
      }
    }
  },
  "last_signal_sequence_id": 98,
  "last_processed_market_timestamp": "2026-03-24T14:31:45.987654",
  "uptime_seconds": 3456.2,
  "binance_thread_alive": true,
  "binance_threads_alive": {
    "BTCUSDT": true,
    "ETHUSDT": true,
    "SOLUSDT": true
  },
  "polymarket_thread_alive": true,
  "ta_scanner_thread_alive": true,
  "ta_scanner_last_scan_at": "2026-03-24T14:32:00.000000",
  "ta_scanner_last_error": null
}
```

### GET /signals

```json
{
  "signals": [
    {
      "id": 1254,
      "sequence_id": 98,
      "source": "binance",
      "strategy": "momentum_trend",
      "timeframe": "1h",
      "trend": "bullish",
      "confidence": 0.75,
      "signal_strength": "medium",
      "reasoning": "momentum > 0 with higher_timeframe_boost",
      "regime": "uptrend",
      "move_pct": 0.0245,
      "value": 45123.45,
      "symbol": "BTCUSDT",
      "timestamp": "2026-03-24T14:32:10.123456"
    },
    {
      "id": 1253,
      "sequence_id": 97,
      "source": "binance",
      "strategy": "momentum_trend",
      "timeframe": "4h",
      "trend": "bullish",
      "confidence": 0.75,
      "signal_strength": "medium",
      "reasoning": "higher_timeframe trend support",
      "regime": "uptrend",
      "move_pct": 0.012,
      "value": 45089.20,
      "symbol": "BTCUSDT",
      "timestamp": "2026-03-24T14:15:05.234567"
    }
  ]
}
```

### GET /opportunities

```json
{
  "opportunities": [
    {
      "id": 42,
      "opportunity_key": "BTCUSDT_polling-for-btc-2026-03-25_bullish_15m_YES_1254",
      "market_id": "0x8f12345678abcdef",
      "market_name": "Polling for BTC > $50K on 2026-03-25",
      "signal_sequence_id": 98,
      "symbol": "BTCUSDT",
      "strategy": "momentum_trend",
      "timeframe": "15m",
      "trend": "bullish",
      "confidence": 0.55,
      "signal_strength": "medium",
      "side": "YES",
      "yes_price": 0.67,
      "no_price": 0.33,
      "combined_price": 1.0,
      "gap_to_parity": 0.34,
      "edge": 0.015,
      "signal_threshold": 0.55,
      "reason_code": "edge_meets_signal_threshold",
      "reasoning": "edge=0.015 meets min_edge=0.005; confidence=0.55 meets signal_threshold=0.55",
      "timestamp": "2026-03-24T14:32:15.678901"
    }
  ]
}
```

### GET /paper-wallets

```json
{
  "total_equity_usdc": 40.0,
  "total_locked_usdc": 0.0,
  "total_available_usdc": 40.0,
  "bots": {
    "momentum_trend": {
      "equity_usdc": 10.0,
      "locked_usdc": 0.0,
      "available_usdc": 10.0
    },
    "ta_confluence": {
      "equity_usdc": 10.0,
      "locked_usdc": 0.0,
      "available_usdc": 10.0
    },
    "reversal_fade": {
      "equity_usdc": 10.0,
      "locked_usdc": 0.0,
      "available_usdc": 10.0
    },
    "arbitrage": {
      "equity_usdc": 10.0,
      "locked_usdc": 0.0,
      "available_usdc": 10.0
    }
  }
}
```

### GET /performance/summary

```json
{
  "trade_count": 0,
  "win_rate": 0.0,
  "avg_pnl": 0.0,
  "total_pnl": 0.0,
  "max_drawdown": 0.0,
  "sharpe_ratio": 0.0,
  "edge_per_setup": {},
  "as_of": "2026-03-24T14:32:30.000000"
}
```

### GET /strategy/rankings

```json
{
  "strategies": [
    {
      "strategy": "momentum_trend",
      "trade_count": 0,
      "wins": 0,
      "win_rate": 0.0,
      "avg_pnl": 0.0,
      "total_pnl": 0.0,
      "sharpe_ratio": 0.0,
      "max_drawdown": 0.0,
      "overall_score": 0.5,
      "sample_count": 0
    },
    {
      "strategy": "ta_confluence",
      "trade_count": 0,
      "wins": 0,
      "win_rate": 0.0,
      "avg_pnl": 0.0,
      "total_pnl": 0.0,
      "sharpe_ratio": 0.0,
      "max_drawdown": 0.0,
      "overall_score": 0.5,
      "sample_count": 0
    }
  ]
}
```

### POST /paper-wallets/reset

```json
{
  "status": "ok",
  "message": "paper wallets reset",
  "result": {
    "total_equity_usdc": 40.0,
    "total_locked_usdc": 0.0,
    "total_available_usdc": 40.0,
    "bots": {
      "momentum_trend": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      },
      "ta_confluence": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      },
      "reversal_fade": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      },
      "arbitrage": {
        "equity_usdc": 10.0,
        "locked_usdc": 0.0,
        "available_usdc": 10.0
      }
    }
  }
}
```

### GET /logs

```json
{
  "logs": [
    {
      "id": 5432,
      "timestamp": "2026-03-24T14:32:30.123456",
      "level": "INFO",
      "module": "bot",
      "message": "[SIGNAL] TrendBot momentum_trend BULLISH confidence=0.55 signal_strength=medium regime=uptrend",
      "context": null
    },
    {
      "id": 5431,
      "timestamp": "2026-03-24T14:32:25.098765",
      "level": "INFO",
      "module": "api",
      "message": "GET /status?symbol=BTCUSDT responded with 3245 bytes",
      "context": null
    }
  ]
}
```

---

## 4. DATA MODELS

### Signal Record
```
{
  id: integer
  sequence_id: integer or null
  source: string (e.g., "binance")
  strategy: string or null (e.g., "momentum_trend", "ta_confluence", "reversal_fade", "arbitrage")
  timeframe: string or null (e.g., "5m", "15m", "1h", "4h", "1d")
  trend: string ("bullish", "bearish", "neutral")
  confidence: float (0.0-1.0, typically capped at 0.75)
  signal_strength: string ("weak", "medium", "strong") or null
  reasoning: string or null
  regime: string or null (e.g., "uptrend", "downtrend", "ranging")
  move_pct: float or null (next candle move percentage)
  value: float or null (underlying price)
  symbol: string or null (e.g., "BTCUSDT")
  timestamp: ISO 8601 datetime string
}
```

### Opportunity Record
```
{
  id: integer
  opportunity_key: string (unique composite identifier)
  market_id: string (Polymarket ID)
  market_name: string
  signal_sequence_id: integer
  symbol: string (e.g., "BTCUSDT")
  strategy: string (e.g., "momentum_trend")
  timeframe: string (e.g., "15m")
  trend: string ("bullish", "bearish", "neutral")
  confidence: float (0.0-1.0)
  signal_strength: string ("weak", "medium", "strong")
  side: string ("YES" or "NO")
  yes_price: float (0.0-1.0)
  no_price: float (0.0-1.0)
  combined_price: float (should be ~1.0)
  gap_to_parity: float (deviation from 0.5)
  edge: float (expected value advantage, 0.0-0.10)
  signal_threshold: float (config.trading.signal_threshold)
  reason_code: string (e.g., "edge_meets_signal_threshold")
  reasoning: string (detailed explanation)
  timestamp: ISO 8601 datetime string
}
```

### Simulated Trade Record
```
{
  id: integer
  symbol: string (e.g., "BTCUSDT")
  strategy: string (e.g., "momentum_trend")
  entry_price: float
  exit_price: float
  direction: integer (-1 for short, 1 for long)
  pnl: float (profit/loss in USDC)
  duration_seconds: integer
  duration: integer (duplicate of duration_seconds)
  signal_strength: string ("weak", "medium", "strong")
  regime: string (e.g., "uptrend")
  timeframe: string or null (e.g., "15m")
  entry_timestamp: ISO 8601 datetime string
  exit_timestamp: ISO 8601 datetime string
  timestamp: ISO 8601 datetime string
}
```

### Wallet Snapshot
```
{
  total_equity_usdc: float (sum of all bot equities)
  total_locked_usdc: float (funds locked in open positions)
  total_available_usdc: float (total_equity - total_locked)
  bots: {
    [strategy_name]: {
      equity_usdc: float (current balance for this strategy)
      locked_usdc: float (amount in open positions)
      available_usdc: float (equity - locked)
    },
    ...
  }
}
```

### Performance Summary
```
{
  trade_count: integer
  win_rate: float (0.0-1.0, percentage of winning trades)
  avg_pnl: float (average PnL per trade)
  total_pnl: float (cumulative PnL)
  max_drawdown: float (maximum peak-to-trough decline)
  sharpe_ratio: float (return-to-volatility ratio)
  edge_per_setup: {
    [signal_strength]: float (avg PnL by signal strength)
  }
  as_of: ISO 8601 datetime string
}
```

### Strategy Ranking
```
{
  strategy: string
  trade_count: integer
  wins: integer
  win_rate: float
  avg_pnl: float
  total_pnl: float
  sharpe_ratio: float
  max_drawdown: float
  overall_score: float (composite ranking 0.0-1.0)
  sample_count: integer (trades used for ranking)
}
```

### Orchestrated Decision
```
{
  symbol: string (e.g., "BTCUSDT")
  direction: integer (-1, 0, or 1)
  trend: string ("bullish", "bearish", "neutral")
  confidence: float (weighted consensus 0.0-1.0)
  reasoning: string (e.g., "consensus from 4 bots")
  timestamp: ISO 8601 datetime string
  bots: {
    [bot_name]: {
      strategy: string
      direction: integer
      confidence: float
      reasoning: string
    },
    ...
  }
}
```

### BotSignal (Internal Dataclass)
```python
@dataclass
class BotSignal:
    bot: str (e.g., "TrendBot")
    strategy: str (e.g., "momentum_trend")
    direction: int (-1, 0, or 1)
    confidence: float
    reasoning: str
```

### SimPosition (Internal Dataclass)
```python
@dataclass
class SimPosition:
    symbol: str
    strategy: str
    timeframe: str
    direction: int
    entry_price: float
    entry_ts: str (ISO datetime)
    quantity: float
    stake_usdc: float
    signal_strength: str
    regime: str
```

### RiskResult (Internal Dataclass)
```python
@dataclass
class RiskResult:
    allowed: bool
    reason_code: str
```

---

## 5. WEBSOCKET ENDPOINTS

**None implemented.** The API is REST-only (HTTP GET/POST). Real-time updates require polling.

Recommended polling intervals:
- `/status` → 5-10 seconds
- `/signals` → 10-30 seconds
- `/opportunities` → 10-30 seconds
- `/paper-wallets` → 5-10 seconds
- `/logs` → 30 seconds

---

## 6. ENV CONFIG

### Configuration File: `backend/config.json`

#### Polymarket Settings
```json
"polymarket": {
  "api_key": "YOUR_POLYMARKET_API_KEY",
  "wallet_address": "YOUR_WALLET_ADDRESS_0x",
  "focus_keywords": ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", ...],
  "polling_interval_seconds": 60
}
```

#### Binance Settings
```json
"binance": {
  "api_key": "YOUR_BINANCE_API_KEY",
  "api_secret": "YOUR_BINANCE_API_SECRET",
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "signal_intervals": ["5m", "15m", "1h", "4h", "1d"],
  "base_urls": ["https://data-api.binance.vision", ...],
  "polling_interval_seconds": 60
}
```

#### Trading Settings (Calibration Knobs)
```json
"trading": {
  "paper_trading": true,
  "mode": "signal",
  "emit_signals_only": false,
  "min_edge": 0.005,
  "signal_threshold": 0.55,
  "arb_threshold": 0.98,
  "trade_size_usdc": 10.0,
  
  "confidence_cap": 0.75,
  "low_sample_threshold": 25,
  "low_sample_penalty": 0.12,
  "medium_horizon_conf_multiplier": 0.65,
  "long_horizon_conf_multiplier": 0.15,
  "block_long_horizon_markets": true,
  "max_position_per_trade_usdc": 3.0,
  
  "max_signal_age_seconds": 180,
  "max_market_age_seconds": 360,
  "cooldown_seconds": 900,
  "max_total_exposure_usdc": 200.0,
  "max_per_market_exposure_usdc": 30.0,
  "max_cluster_exposure_usdc": 100.0,
  "min_liquidity": 1000.0
}
```

#### Technical Scanner Settings
```json
"technical_scan": {
  "enabled": true,
  "scan_interval_seconds": 300,
  "min_candles": 260,
  "low_vol_atr_ratio": 0.0035,
  "watchlist": []
}
```

#### Simulation (Paper Wallet) Settings
```json
"simulation": {
  "enabled": true,
  "paper_wallet": {
    "enabled": true,
    "balance_per_bot_usdc": 10.0,
    "min_notional_usdc": 1.0,
    "max_position_per_trade_usdc": 3.0,
    "min_edge_for_position": 0.001,
    "strategies": ["momentum_trend", "ta_confluence", "reversal_fade", "arbitrage"]
  },
  "exit_rules": {
    "time_windows_seconds": [3600, 14400, 86400],
    "take_profit_pct": 0.02,
    "stop_loss_pct": 0.01,
    "opposite_signal_exit": true
  }
}
```

#### Database Settings
```json
"database": {
  "path": "trading_bot.db"
}
```

#### API Server Settings
```json
"api": {
  "host": "0.0.0.0",
  "port": 8000
}
```

### Environment Variables (Optional)

Supported via `.env` file (loaded with `python-dotenv`):
- `POLYMARKET_API_KEY` — Polymarket API credentials
- `BINANCE_API_KEY` — Binance API key
- `BINANCE_API_SECRET` — Binance API secret

### Startup Requirements

**Python Packages** (`requirements.txt`):
```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
requests>=2.31.0
python-dotenv>=1.0.0
ccxt>=4.4.0
pandas>=2.2.0
pandas-ta>=0.3.14b0
numpy>=1.26.0
```

**Database Initialization**:
- SQLite database auto-creates on first run at path specified in `config.json` (`trading_bot.db`)
- Schema includes tables: `markets`, `signals`, `signal_sequences`, `opportunities`, `trades_simulated`, `strategy_performance`, `positions`, `trades`, `bot_state`, `log`
- Migrations run automatically on startup to backfill columns (regime, timeframe, etc.)

**Run Commands**:
```bash
# Option 1: Direct
python api.py

# Option 2: Uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000
```

---

## 7. SUMMARY

- **Architecture**: FastAPI (async), SQLite backend, multi-threaded polling (Binance, Polymarket, Technical Scanner)
- **Auth**: None (assumes protected network; CORS enables frontend dashboard at localhost:3000 or Vercel)
- **Content-Type**: JSON (all responses)
- **Error Handling**: HTTPException with 400/500 status codes
- **Core Features**: Paper wallet trading ($10 per strategy), probabilistic signal calibration, multi-bot orchestration, historical performance tracking, technical analysis alerts
