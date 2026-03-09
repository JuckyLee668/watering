#!/usr/bin/env bash
set -Eeuo pipefail

########################################
# 基础配置
########################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

APP_MODULE="${APP_MODULE:-app.main:app}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

########################################
# 日志函数
########################################

log() {
  echo "[`date '+%Y-%m-%d %H:%M:%S'`] $*"
}

error_exit() {
  echo "[ERROR] $*" >&2
  exit 1
}

########################################
# 检查 Python
########################################

command -v "$PYTHON_BIN" >/dev/null 2>&1 || error_exit "Python not found"

########################################
# Python venv 自动创建
########################################

if [ ! -d ".venv" ]; then
  echo "[init] Creating virtualenv..."
  python3 -m venv .venv
fi

# 激活虚拟环境
# shellcheck disable=SC1091
source .venv/bin/activate
########################################
# 依赖安装（可跳过）
########################################

if [ "${INSTALL_DEPS:-0}" = "0" ]; then
  log "[1/4] Installing dependencies..."
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r requirements.txt
else
  log "[1/4] Skip dependency installation"
fi

########################################
# 自检
########################################

if [ "${SKIP_SELF_CHECK:-0}" = "1" ]; then
  log "[2/4] Skipping self-check"
else
  log "[2/4] Running self-check"
  "$PYTHON_BIN" scripts/self_check.py
fi

########################################
# 数据库初始化
########################################

if [ "${RESET_DB:-0}" = "1" ]; then
  log "[3/4] Rebuilding database"
  "$PYTHON_BIN" scripts/init_db.py --drop --sample
else
  log "[3/4] Ensuring database exists"
  "$PYTHON_BIN" scripts/init_db.py
fi

########################################
# 启动服务
########################################

if [ "${RELOAD:-0}" = "1" ]; then

  log "[4/4] Starting FastAPI (dev reload)"
  exec "$PYTHON_BIN" -m uvicorn "$APP_MODULE" \
      --host "$HOST" \
      --port "$PORT" \
      --reload

else

  log "[4/4] Starting FastAPI (production)"

  exec "$PYTHON_BIN" -m uvicorn "$APP_MODULE" \
      --host "$HOST" \
      --port "$PORT" \
      --workers "$WORKERS"

fi
