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
APP_URL="${COMMAND_CENTER_3_APP_URL:-${VITE_URL%/}/#home}"
LAUNCHER_CHECK_ONLY="${COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY:-0}"
LAUNCHER_SKIP_OPEN="${COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN:-0}"

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

command_center_health_ready() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        if response.status < 200 or response.status >= 300:
            sys.exit(1)
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    sys.exit(1)

data = payload.get("data") if isinstance(payload, dict) else {}
if not isinstance(data, dict):
    sys.exit(1)
if data.get("service") != "stock-MING Command Center 3.0":
    sys.exit(1)
if data.get("status") != "ok":
    sys.exit(1)
if data.get("external_calls_on_startup") is not False:
    sys.exit(1)
sys.exit(0)
PY
}

vite_command_center_ready() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        if response.status < 200 or response.status >= 300:
            sys.exit(1)
        body = response.read(20000).decode("utf-8", errors="replace")
except Exception:
    sys.exit(1)

required_markers = [
    "stock-MING Command Center 3.0",
    "/src/main.tsx",
]
sys.exit(0 if all(marker in body for marker in required_markers) else 1)
PY
}

bootstrap_status_ready() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        if response.status < 200 or response.status >= 300:
            sys.exit(1)
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    sys.exit(1)

data = payload.get("data") if isinstance(payload, dict) else {}
if not isinstance(data, dict):
    sys.exit(1)
if data.get("packet_key") != "command_center_3_bootstrap_runtime_mode_packet":
    sys.exit(1)
if data.get("schema_version") != "command_center_bootstrap_runtime_mode.v1":
    sys.exit(1)
sys.exit(0)
PY
}

desktop_preflight_cache_ready() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        if response.status < 200 or response.status >= 300:
            sys.exit(1)
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    sys.exit(1)

data = payload.get("data") if isinstance(payload, dict) else {}
if not isinstance(data, dict):
    sys.exit(1)
if data.get("packet_key") != "command_center_3_desktop_shell_preflight_cache":
    sys.exit(1)
if data.get("schema_version") != "desktop_shell_preflight_cache.v1":
    sys.exit(1)
launcher = data.get("desktop_launcher_contract")
if not isinstance(launcher, dict):
    sys.exit(1)
if launcher.get("status") != "local_one_click_launcher_ready":
    sys.exit(1)
if launcher.get("launcher_path") != "scripts/start_command_center_3.command":
    sys.exit(1)
if data.get("external_calls_triggered") is not False:
    sys.exit(1)
sys.exit(0)
PY
}

wait_for_command_center_health() {
  local url="$2"
  local attempts="${3:-30}"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if command_center_health_ready "$url"; then
      echo "FastAPI Command Center 3.0 health JSON ready: ${url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "FastAPI Command Center 3.0 health JSON still warming up or wrong service on port: ${url}"
  return 1
}

wait_for_vite_command_center() {
  local url="$1"
  local attempts="${2:-30}"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if vite_command_center_ready "$url"; then
      echo "React/Vite Command Center 3.0 app ready: ${url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "React/Vite Command Center 3.0 app still warming up or wrong app on port: ${url}"
  return 1
}

wait_for_bootstrap_status() {
  local url="$1"
  local attempts="${2:-30}"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if bootstrap_status_ready "$url"; then
      echo "FastAPI bootstrap status JSON ready: ${url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "FastAPI bootstrap status JSON still warming up: ${url}"
  return 1
}

wait_for_desktop_preflight_cache() {
  local url="$1"
  local attempts="${2:-30}"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if desktop_preflight_cache_ready "$url"; then
      echo "FastAPI desktop preflight cache JSON ready: ${url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "FastAPI desktop preflight cache JSON still warming up: ${url}"
  return 1
}

print_startup_diagnostics() {
  echo "可操作诊断："
  if [ "$FASTAPI_READY" != "1" ]; then
    echo "  - FastAPI：${API_BASE%/}/health 未返回 Command Center 3.0 健康 JSON；可能后端未启动、8710 被占用，或 Python 依赖缺失。"
  fi
  if [ "$API_STATUS_READY" != "1" ]; then
    echo "  - Bootstrap status：${API_BASE%/}/api/bootstrap/status 未返回 runtime-mode packet；可能后端不是 3.0，或启动时加载失败。"
  fi
  if [ "$DESKTOP_PREFLIGHT_READY" != "1" ]; then
    echo "  - Desktop preflight cache：${API_BASE%/}/api/desktop/preflight-cache 未返回一键启动 packet；可能后端预检 cache 尚未就绪。"
  fi
  if [ "$VITE_READY" != "1" ]; then
    echo "  - React/Vite：${VITE_URL} 未返回 Command Center 3.0 前端 HTML；可能 5173 被占用，或 npm run dev 启动失败。"
  fi
  echo "下一步：先关闭占用 8710/5173 的本地进程，或查看上面的 FastAPI / React/Vite 日志。"
}

print_post_startup_readback_checklist() {
  echo "启动后复核清单："
  echo "  1. FastAPI health：${API_BASE%/}/health 已返回 Command Center 3.0 JSON，且 external_calls_on_startup=false。"
  echo "  2. Bootstrap status：${API_BASE%/}/api/bootstrap/status 已返回 runtime-mode packet，只读显示 cache_only/manual/live_light/live_full。"
  echo "  3. Desktop preflight cache：${API_BASE%/}/api/desktop/preflight-cache 已返回一键启动 packet，普通首页和健康页可回读同一条 P0 本地证据。"
  if [ "${LAUNCHER_SKIP_OPEN:-0}" = "1" ]; then
    echo "  4. React/Vite 前端：${VITE_URL} 已返回 Command Center 3.0 HTML；skip-open 已启用，请手动打开普通首页 ${APP_URL}。"
  else
    echo "  4. React/Vite 前端：${VITE_URL} 已返回 Command Center 3.0 HTML；页面会打开普通首页 ${APP_URL}，先看今日作战台的一键启动预检。"
  fi
  echo "  5. 联通后下一步：打开 ${VITE_URL%/}/#candidates，输入股票代码；只有确认按钮会创建 Tushare-first POST task，DeepSeek 仍保持 governed/pending。"
  echo "  6. P0 success handoff: after readiness, open #candidates; typing stays silent; confirm button creates Tushare-first POST task; DeepSeek remains governed/skipped."
  echo "边界：启动后复核只读本地 GET 结果；不创建 task、不调用 Tushare/DeepSeek/GitHub、不执行真实交易。"
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
echo "Open route: ${APP_URL}"
echo "Logs: ${LOG_DIR}"
echo "Check only: ${LAUNCHER_CHECK_ONLY}"
echo "Browser open: $([ "$LAUNCHER_SKIP_OPEN" = "1" ] && printf "skipped" || printf "enabled")"
echo "P0: local one-click launcher starts/checks FastAPI, bootstrap status, desktop preflight cache, and React/Vite before opening the page."
echo "Mode: server config controls runtime mode; cache_only remains the safe default unless explicitly configured."
echo "Link check: launcher verifies ${API_BASE%/}/health, ${API_BASE%/}/api/bootstrap/status, and ${API_BASE%/}/api/desktop/preflight-cache before opening the page."
echo "Health check: /health must return stock-MING Command Center 3.0 JSON with external_calls_on_startup=false."
echo "Bootstrap check: /api/bootstrap/status must return command_center_3_bootstrap_runtime_mode_packet JSON before the page opens."
echo "Desktop preflight check: /api/desktop/preflight-cache must return command_center_3_desktop_shell_preflight_cache JSON before the page opens."
echo "Frontend check: Vite must serve stock-MING Command Center 3.0 index HTML before the page opens."
echo "Open target: ordinary Command Center home route (#home), so startup does not land on developer/audit details from localStorage."
echo "P0 success handoff: after readiness, open #candidates; typing stays silent; confirm button creates Tushare-first POST task; DeepSeek remains governed/skipped."
echo "Boundary: one-click startup only links local frontend/backend; it does not enable live_light/provider/model execution."
echo "Safety: this launcher does not set live_light defaults and makes no Tushare, DeepSeek, GitHub, or trading call."
echo "Acceptance: runtime_mode_config_current_acceptance_* markers are status/checkpoint drift guards, not launcher config or live_light enablement."

if [ "$LAUNCHER_CHECK_ONLY" = "1" ]; then
  echo "Check-only mode: resolved launcher configuration without starting FastAPI, starting React/Vite, probing URLs, writing logs, opening a browser, creating tasks, calling providers/models, or touching trading paths."
  echo "Check-only endpoints: health=${API_BASE%/}/health; bootstrap=${API_BASE%/}/api/bootstrap/status; desktop_preflight=${API_BASE%/}/api/desktop/preflight-cache; frontend=${VITE_URL}; open_route=${APP_URL}"
  echo "Check-only next action: unset COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY and rerun this launcher to start or reuse local FastAPI/Vite, wait for all four readiness checks, then open ${APP_URL}."
  exit 0
fi

if command_center_health_ready "${API_BASE%/}/health"; then
  echo "FastAPI already running."
else
  if url_ready "${API_BASE%/}/health"; then
    echo "FastAPI port has a response, but it is not Command Center 3.0 health JSON."
  fi
  echo "Starting FastAPI..."
  STOCK_MING_FASTAPI_RELOAD=0 PYTHON_BIN="$PYTHON_BIN" nohup "${PROJECT_ROOT}/scripts/dev_server.sh" >"$FASTAPI_LOG" 2>&1 &
fi

if vite_command_center_ready "$VITE_URL"; then
  echo "Vite already running."
else
  if url_ready "$VITE_URL"; then
    echo "React/Vite port has a response, but it is not the Command Center 3.0 frontend."
  fi
  echo "Starting React/Vite..."
  (cd "$DESKTOP_ROOT" && VITE_API_BASE_URL="$API_BASE" nohup npm run dev >"$VITE_LOG" 2>&1 &)
fi

FASTAPI_READY=0
API_STATUS_READY=0
DESKTOP_PREFLIGHT_READY=0
VITE_READY=0

if wait_for_command_center_health "FastAPI" "${API_BASE%/}/health" 40; then
  FASTAPI_READY=1
fi

if wait_for_bootstrap_status "${API_BASE%/}/api/bootstrap/status" 40; then
  API_STATUS_READY=1
fi

if wait_for_desktop_preflight_cache "${API_BASE%/}/api/desktop/preflight-cache" 40; then
  DESKTOP_PREFLIGHT_READY=1
fi

if wait_for_vite_command_center "$VITE_URL" 40; then
  VITE_READY=1
fi

if [ "$FASTAPI_READY" != "1" ] || [ "$API_STATUS_READY" != "1" ] || [ "$DESKTOP_PREFLIGHT_READY" != "1" ] || [ "$VITE_READY" != "1" ]; then
  echo "Command Center 3.0 启动未完成：FastAPI ready=${FASTAPI_READY}, API status ready=${API_STATUS_READY}, desktop preflight ready=${DESKTOP_PREFLIGHT_READY}, React/Vite ready=${VITE_READY}"
  echo "请查看日志："
  echo "  FastAPI log: ${FASTAPI_LOG}"
  echo "  React/Vite log: ${VITE_LOG}"
  print_startup_diagnostics
  echo "本地入口不会在前后端未联通或 Vite 端口不是 Command Center 3.0 页面时自动打开页面。"
  exit 1
fi

if [ "$LAUNCHER_SKIP_OPEN" = "1" ]; then
  echo "Skip-open mode: FastAPI, bootstrap status, desktop preflight cache, and React/Vite are ready; browser was not opened automatically."
  echo "请在浏览器打开：${APP_URL}"
elif command -v open >/dev/null 2>&1; then
  open "$APP_URL"
else
  echo "请在浏览器打开：${APP_URL}"
fi

print_post_startup_readback_checklist
echo "Command Center 3.0 入口已启动。关闭本窗口不会停止已在后台运行的本地 dev server。"
