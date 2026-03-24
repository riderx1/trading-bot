#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/trading-bot/ops/logs"
cd "$HOME/trading-bot/dashboard"

npm install --silent
npm run build

pkill -f next-server || true
pkill -f "next start" || true
pkill -f "next dev" || true

nohup npm run start -- -p 3000 > "$HOME/trading-bot/ops/logs/dashboard.out.log" 2> "$HOME/trading-bot/ops/logs/dashboard.err.log" < /dev/null &
sleep 5

ss -ltnp | grep :3000 || true
ps -ef | grep -E "next-server|next start" | grep -v grep || true
