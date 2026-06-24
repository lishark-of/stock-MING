#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAUNCHER="${PROJECT_ROOT}/scripts/start_command_center_3.command"
APP_URL="${COMMAND_CENTER_3_APP_URL:-http://127.0.0.1:5173/#home}"

echo "stock-MING Command Center 3.0 software entry"
echo "Project: ${PROJECT_ROOT}"
echo "Launcher: ${LAUNCHER}"
echo "Open route: ${APP_URL}"
echo "Default entry: local FastAPI + React/Vite Command Center 3.0."
echo "Boundary: this entry delegates to the local 3.0 launcher; it does not call Tushare, DeepSeek, GitHub, or trading paths."

if [ ! -x "$LAUNCHER" ]; then
  echo "stock-MING Command Center 启动失败：找不到可执行的 3.0 本地启动器：${LAUNCHER}"
  exit 1
fi

cd "$PROJECT_ROOT"

COMMAND_CENTER_BOOTSTRAP_MODE="${COMMAND_CENTER_BOOTSTRAP_MODE:-cache_only}" \
COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="${COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN:-false}" \
COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="${COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN:-false}" \
COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="${COMMAND_CENTER_LIVE_STARTUP_AUTOSTART:-false}" \
COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="${COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART:-false}" \
COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="${COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE:-plan_only}" \
COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE="${COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE:-bootstrap_only}" \
COMMAND_CENTER_3_PROJECT_ROOT="$PROJECT_ROOT" \
COMMAND_CENTER_3_APP_URL="$APP_URL" \
exec "$LAUNCHER"
