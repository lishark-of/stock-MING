#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DESKTOP_ROOT="${PROJECT_ROOT}/desktop"
LOG_DIR="${PROJECT_ROOT}/.stock_ming_3/logs"
FASTAPI_LOG="${LOG_DIR}/command_center_3_fastapi.log"
VITE_LOG="${LOG_DIR}/command_center_3_vite.log"
API_BASE="${VITE_API_BASE_URL:-http://127.0.0.1:8710}"
VITE_URL="${COMMAND_CENTER_3_VITE_URL:-http://127.0.0.1:5173}"

resolve_python() {
  if [ -n "${STOCK_MING_PYTHON:-}" ]; then
    printf "%s\n" "${STOCK_MING_PYTHON}"
    return 0
  fi
  if [ -x "${PROJECT_ROOT}/.venv/bin/python" ]; then
    printf "%s\n" "${PROJECT_ROOT}/.venv/bin/python"
    return 0
  fi
  if [ "${STOCK_MING_ALLOW_SYSTEM_PYTHON:-0}" = "1" ] && command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys; print(sys.executable)'
    return 0
  fi
  return 1
}

url_ready() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        sys.exit(0 if response.status < 500 else 1)
except Exception:
    sys.exit(1)
PY
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if url_ready "$url"; then
      echo "${name} ready: ${url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "${name} still warming up: ${url}"
  return 1
}

PYTHON_BIN="$(resolve_python)" || {
  echo "Command Center 3.0 启动失败：未找到项目 .venv Python。"
  echo "请先创建 .venv，或显式设置 STOCK_MING_PYTHON=/path/to/python。"
  echo "如确需临时使用系统 python3，可设置 STOCK_MING_ALLOW_SYSTEM_PYTHON=1。"
  exit 1
}

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Command Center 3.0 启动失败：Python 不可执行：${PYTHON_BIN}"
  exit 1
fi

if [ ! -d "${DESKTOP_ROOT}/node_modules" ]; then
  echo "Command Center 3.0 启动失败：desktop/node_modules 不存在。"
  echo "请先运行：cd \"${DESKTOP_ROOT}\" && npm install"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Command Center 3.0 启动失败：未找到 npm。"
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

echo "Command Center 3.0 local launcher"
echo "Project: ${PROJECT_ROOT}"
echo "Python: ${PYTHON_BIN}"
echo "FastAPI: ${API_BASE}"
echo "React/Vite: ${VITE_URL}"
echo "Logs: ${LOG_DIR}"
echo "P0: local one-click launcher starts/checks FastAPI and React/Vite before opening the page."
echo "Mode: server config controls runtime mode; cache_only remains the safe default unless explicitly configured."
echo "Link check: launcher verifies ${API_BASE%/}/health and ${API_BASE%/}/api/bootstrap/status before opening the page."
echo "Boundary: one-click startup only links local frontend/backend; it does not enable live_light/provider/model execution."
echo "Safety: this launcher does not set live_light defaults and makes no Tushare, DeepSeek, GitHub, or trading call."
echo "Acceptance: runtime_mode_config_current_acceptance_* markers are status/checkpoint drift guards, not launcher config or live_light enablement."

if url_ready "${API_BASE%/}/health"; then
  echo "FastAPI already running."
else
  echo "Starting FastAPI..."
  PYTHON_BIN="$PYTHON_BIN" nohup "${PROJECT_ROOT}/scripts/dev_server.sh" >"$FASTAPI_LOG" 2>&1 &
fi

if url_ready "$VITE_URL"; then
  echo "Vite already running."
else
  echo "Starting React/Vite..."
  (cd "$DESKTOP_ROOT" && VITE_API_BASE_URL="$API_BASE" nohup npm run dev >"$VITE_LOG" 2>&1 &)
fi

FASTAPI_READY=0
API_STATUS_READY=0
VITE_READY=0

if wait_for_url "FastAPI" "${API_BASE%/}/health" 40; then
  FASTAPI_READY=1
fi

if wait_for_url "FastAPI status API" "${API_BASE%/}/api/bootstrap/status" 40; then
  API_STATUS_READY=1
fi

if wait_for_url "React/Vite" "$VITE_URL" 40; then
  VITE_READY=1
fi

if [ "$FASTAPI_READY" != "1" ] || [ "$API_STATUS_READY" != "1" ] || [ "$VITE_READY" != "1" ]; then
  echo "Command Center 3.0 启动未完成：FastAPI ready=${FASTAPI_READY}, API status ready=${API_STATUS_READY}, React/Vite ready=${VITE_READY}"
  echo "请查看日志："
  echo "  FastAPI log: ${FASTAPI_LOG}"
  echo "  React/Vite log: ${VITE_LOG}"
  echo "本地入口不会在前后端未联通时自动打开页面。"
  exit 1
fi

if command -v open >/dev/null 2>&1; then
  open "$VITE_URL"
else
  echo "请在浏览器打开：${VITE_URL}"
fi

echo "Command Center 3.0 入口已启动。关闭本窗口不会停止已在后台运行的本地 dev server。"
