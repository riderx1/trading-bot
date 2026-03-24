#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/dd8318519-dotcom/sentient-trade-compass.git}"
TARGET_DIR="$HOME/trading-bot"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$HOME/trading-bot_pre_git_${TS}"

pkill -f "python .*api.py" || true
pkill -f "vite preview" || true
pkill -f "next start" || true
pkill -f "next dev" || true

if [ -d "$TARGET_DIR" ]; then
  mv "$TARGET_DIR" "$BACKUP_DIR"
fi

git clone "$REPO_URL" "$TARGET_DIR"
cd "$TARGET_DIR"
git checkout master

if [ -d "$BACKUP_DIR" ]; then
  if [ -f "$BACKUP_DIR/backend/config.json" ]; then
    cp "$BACKUP_DIR/backend/config.json" "$TARGET_DIR/backend/config.json"
  fi

  if ls "$BACKUP_DIR/backend/trading_bot.db"* >/dev/null 2>&1; then
    cp -f "$BACKUP_DIR/backend/trading_bot.db"* "$TARGET_DIR/backend/"
  fi
fi

cd "$TARGET_DIR/dashboard"
npm install --silent
npm run build

cd "$TARGET_DIR/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install -r requirements.txt

cd "$TARGET_DIR"
chmod +x ops/restart_backend.sh ops/restart_dashboard.sh
bash "$TARGET_DIR/ops/restart_backend.sh" "$TARGET_DIR"
bash "$TARGET_DIR/ops/restart_dashboard.sh"

echo "MIGRATION_DONE"
echo "BACKUP_DIR=$BACKUP_DIR"
