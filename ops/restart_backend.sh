#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$HOME/trading-bot}"
BACKEND_DIR="$ROOT_DIR/backend"
LOG_FILE="$ROOT_DIR/ops/backend-runtime.log"

mkdir -p "$ROOT_DIR/ops"
pkill -f "python.*api.py" || true

cd "$BACKEND_DIR"
nohup .venv/bin/python api.py > "$LOG_FILE" 2>&1 < /dev/null &

echo "BACKEND_RESTARTED"
