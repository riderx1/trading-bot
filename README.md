# Hybrid Trading Bot

## Current Docs (Updated)

- [Current Functionality](docs/CURRENT_FUNCTIONALITY.md)
- [Mini PC Deploy Sequence](docs/MINIPC_DEPLOY_SEQUENCE.md)
- [UI Preservation Rules](docs/UI_PRESERVATION_RULES.md)
- [Paper Trading Implementation Spec](docs/PAPER_TRADING_IMPLEMENTATION_SPEC.md)

A Python-based hybrid trading bot that combines **Polymarket prediction markets** with **Binance BTC momentum signals**, backed by a FastAPI server and a Next.js dashboard.

Current default mode is **signal-only**: the bot analyzes gaps and trends, stores opportunities, and does not execute trades.

---

## Project Structure

```
trading-bot/
├── backend/
│   ├── bot.py            ← Core bot logic (polling, strategies, trades)
│   ├── api.py            ← FastAPI server (REST endpoints for the dashboard)
│   ├── db.py             ← SQLite database layer
│   ├── config.json       ← Configuration (API keys, thresholds, modes)
│   └── requirements.txt
├── dashboard/
│   ├── pages/
│   │   ├── index.js      ← Main dashboard UI
│   │   └── api/
│   │       └── health.js ← Dashboard health check endpoint
│   ├── next.config.js
│   ├── package.json
│   └── .env.local.example
├── .gitignore
└── README.md
```

---

## Quick Start

### 1 — Backend (Ubuntu Mini PC)

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure the bot
cp config.json config.json.bak   # backup the template
nano config.json                 # fill in API keys, wallet address, thresholds

# Start the API + bot together
python api.py
```

The API will be listening on `http://0.0.0.0:8000`.  
Interactive docs: `http://localhost:8000/docs`

> **Signal-only is ON by default** (`"emit_signals_only": true`).
> The bot stores opportunities and never places orders while this flag is enabled.

---

### 2 — Dashboard (Local or Vercel)

```bash
cd dashboard

npm install

# Configure the backend URL
cp .env.local.example .env.local
nano .env.local    # set NEXT_PUBLIC_API_URL to your mini PC's IP

# Run the dev server
npm run dev
```

Open `http://localhost:3000`.

### 3 — Same-Network Setup (Remote PC + Laptop)

1. Run backend on remote PC: `cd backend && python api.py`
2. Run dashboard on remote PC: `cd dashboard && npm run dev -- --hostname 0.0.0.0 --port 3000`
3. On your laptop (same LAN), open `http://REMOTE_PC_IP:3000`
4. Ensure Windows Firewall allows inbound TCP ports `8000` and `3000` on the remote PC.

### 4 — Always-On Local Deployment (Windows Mini PC, 24/7)

Use the included watchdog scripts to keep both services running and auto-restart them if they crash.

1. One-time setup:

```powershell
cd C:\Users\teckt\Desktop\trading-bot\dashboard
npm install
npm run build
```

2. Start both services now:

```powershell
cd C:\Users\teckt\Desktop\trading-bot
powershell -ExecutionPolicy Bypass -File .\ops\start-stack.ps1
```

3. Install startup task so it launches after every reboot:

```powershell
cd C:\Users\teckt\Desktop\trading-bot
powershell -ExecutionPolicy Bypass -File .\ops\install-startup-task.ps1
```

4. Confirm access from another laptop on same LAN:

- Dashboard: `http://MINI_PC_IP:3000`
- API: `http://MINI_PC_IP:8000/status`

5. Open Windows Firewall (once, as Administrator):

```powershell
New-NetFirewallRule -DisplayName "TradingBot API 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000
New-NetFirewallRule -DisplayName "TradingBot Dashboard 3000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000
```

Runtime logs are written to:

- `ops/logs/backend.out.log`
- `ops/logs/backend.err.log`
- `ops/logs/dashboard.out.log`
- `ops/logs/dashboard.err.log`

### 5 — No-Git Sync (Laptop -> Mini PC)

If your source of truth is your laptop and you are not using Git, use the sync helper script.

From your Windows laptop:

```powershell
cd C:\Users\teckt\Desktop\trading-bot
powershell -ExecutionPolicy Bypass -File .\ops\sync-to-minipc.ps1 -MiniPcHost 192.168.1.68 -MiniPcUser openclaw -InstallAndBuild
```

What it does:

1. Creates a project archive on your laptop.
2. Copies it to your mini PC via `scp`.
3. Replaces `/home/openclaw/trading-bot` on the mini PC.
4. Optionally runs `npm install`, `npm run build`, and backend Python dependency setup when `-InstallAndBuild` is provided.

Notes:

- Requires `ssh` and `scp` available on your Windows laptop.
- Excludes large/runtime folders such as `backend/.venv`, `dashboard/node_modules`, `dashboard/.next`, `ops/logs`, and SQLite files.

### 6 — Preferred Updates (Git Push/Pull)

Use this as the standard update path from now on.

On laptop:

```powershell
cd C:\Users\teckt\Desktop\trading-bot
git add .
git commit -m "describe update"
git push origin master
```

On mini PC:

```bash
cd ~/trading-bot
git pull origin master
bash ~/trading-bot/ops/restart_backend.sh ~/trading-bot
bash ~/trading-bot/ops/restart_dashboard.sh
```

Verify:

```bash
curl -s http://127.0.0.1:8000/status
curl -I -s http://127.0.0.1:3000/ | head -n 1
```

#### Deploy to Vercel

1. Push the repo to GitHub.
2. Import it at [vercel.com](https://vercel.com) → New Project.
3. Set **Root Directory** to `dashboard/`.
4. Add environment variable: `NEXT_PUBLIC_API_URL` = `http://YOUR_MINI_PC_IP:8000`
5. Deploy.

---

## Configuration (`backend/config.json`)

| Key | Default | Description |
|-----|---------|-------------|
| `polymarket.api_key` | `""` | Polymarket API key |
| `polymarket.wallet_address` | `""` | Your wallet address (0x…) |
| `polymarket.polling_interval_seconds` | `3600` | Market prices fetch interval |
| `binance.api_key` | `""` | Binance API key (optional for price data) |
| `binance.api_secret` | `""` | Binance API secret |
| `binance.symbol` | `BTCUSDT` | Spot pair to track |
| `binance.polling_interval_seconds` | `60` | BTC price fetch interval |
| `trading.paper_trading` | `true` | `true` = simulate trades, no real funds |
| `trading.mode` | `"arbitrage"` | `"arbitrage"`, `"signal"`, or `"both"` |
| `trading.emit_signals_only` | `true` | `true` = emit opportunities only, do not execute trades |
| `trading.arb_threshold` | `0.98` | YES+NO combined price must be below this |
| `trading.signal_threshold` | `0.55` | Max token price for signal-based entries |
| `trading.trade_size_usdc` | `10.0` | USDC value per trade leg |
| `database.path` | `trading_bot.db` | SQLite file path (relative to `backend/`) |
| `api.host` | `0.0.0.0` | FastAPI bind host |
| `api.port` | `8000` | FastAPI bind port |

---

## Trading Modes

### `arbitrage`
Buys **both YES and NO** tokens when their combined price is below `arb_threshold` (e.g. 0.98).  
At settlement exactly one side pays 1.00 USDC, locking in a guaranteed profit equal to `1 − combined_price`.

### `signal`
Uses short-term BTC momentum (last few 1-minute candles on Binance) to pick a direction:
- **Bullish BTC** → buy YES tokens when `yes_price < signal_threshold`
- **Bearish BTC** → buy NO tokens when `no_price < signal_threshold`
- **Neutral** → skip

### `both`
Runs arbitrage first; if no arb opportunity exists, applies the signal strategy.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/status` | Bot status, mode, paper_trading flag, uptime, thread health |
| `GET` | `/markets?limit=50` | Latest Polymarket YES/NO price snapshots |
| `GET` | `/signals?limit=20` | Latest Binance BTC signals |
| `GET` | `/opportunities?limit=100` | Latest signal opportunities (no execution required) |
| `GET` | `/trades?limit=50` | Trade history |
| `GET` | `/logs?limit=100` | Application log entries |

---

## Database Schema (SQLite)

```sql
markets  (id, market_name, yes_price, no_price, timestamp)
trades   (id, market_id, type, price, quantity, timestamp)
signals  (id, source, trend, value, timestamp)
log      (id, message, level, timestamp)
```

---

## Pulling Updates on the Mini PC

```bash
git pull origin main
cd backend
source .venv/bin/activate
pip install -r requirements.txt   # pick up any new dependencies
python api.py
```

---

## Roadmap

- [ ] Real order submission via Polymarket CLOB API
- [ ] EMA / RSI-based momentum indicators (replace simple candle comparison)
- [ ] PnL tracking and position management
- [ ] Alert notifications (Telegram / email)
- [ ] Dockerise the backend for one-command deployment
- [ ] WebSocket streaming to the dashboard (eliminate polling)
