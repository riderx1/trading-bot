#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/trading-bot/ops/logs"
cd "$HOME/trading-bot/dashboard"

pkill -f next-server || true
pkill -f "next start" || true
pkill -f "next dev" || true
pkill -f "vite preview" || true
pkill -f "^vite$" || true

nohup npm run preview -- --host 0.0.0.0 --port 3000 > "$HOME/trading-bot/ops/logs/dashboard.out.log" 2> "$HOME/trading-bot/ops/logs/dashboard.err.log" < /dev/null &

sleep 5
ss -ltnp | grep :3000 || true
ps -ef | grep -E "next-server|next start|vite preview" | grep -v grep || true
