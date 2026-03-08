#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

echo "[1/3] Installing dependencies..."
"$PYTHON_BIN" -m pip install -r requirements.txt

if [ "${SKIP_SELF_CHECK:-0}" = "1" ]; then
  echo "[2/4] Skipping self-check..."
else
  echo "[2/4] Running self-check..."
  "$PYTHON_BIN" scripts/self_check.py
fi

if [ "${RESET_DB:-0}" = "1" ]; then
  echo "[3/4] Rebuilding SQLite database (drop + sample)..."
  "$PYTHON_BIN" scripts/init_db.py --drop --sample
else
  echo "[3/4] Ensuring database tables exist (keep existing data)..."
  "$PYTHON_BIN" scripts/init_db.py
fi

if [ "${RELOAD:-0}" = "1" ]; then
  echo "[4/4] Starting app on http://0.0.0.0:8000 (reload mode)..."
  exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  echo "[4/4] Starting app on http://0.0.0.0:8000 (stable mode)..."
  exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
