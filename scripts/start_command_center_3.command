#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${COMMAND_CENTER_3_PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
DESKTOP_ROOT="${PROJECT_ROOT}/desktop"
LOG_DIR="${PROJECT_ROOT}/.stock_ming_3/logs"
FASTAPI_LOG="${LOG_DIR}/command_center_3_fastapi.log"
VITE_LOG="${LOG_DIR}/command_center_3_vite.log"
API_BASE="${VITE_API_BASE_URL:-http://127.0.0.1:8710}"
VITE_URL="${COMMAND_CENTER_3_VITE_URL:-http://127.0.0.1:5173}"
APP_URL="${COMMAND_CENTER_3_APP_URL:-${VITE_URL%/}/#home}"
LAUNCHER_CHECK_ONLY="${COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY:-0}"
LAUNCHER_SKIP_OPEN="${COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN:-0}"
P0_STABILITY_DWELL_SECONDS="${COMMAND_CENTER_3_P0_STABILITY_DWELL_SECONDS:-2}"

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

safe_display_url() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit

raw = sys.argv[1]
fallback = raw.split("?", 1)[0].split("#", 1)[0]
try:
    parsed = urlsplit(raw)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if parsed.scheme and host:
        safe_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        netloc = f"{safe_host}:{port}" if port else safe_host
        safe = urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    else:
        safe = fallback
except Exception:
    safe = fallback
print(safe[:180])
PY
}

safe_display_open_url() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY'
import re
import sys
from urllib.parse import urlsplit, urlunsplit

raw = sys.argv[1]
fallback = raw.split("?", 1)[0]
try:
    parsed = urlsplit(raw)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if parsed.scheme and host:
        safe_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        netloc = f"{safe_host}:{port}" if port else safe_host
        fragment = parsed.fragment if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,40}", parsed.fragment or "") else ""
        safe = urlunsplit((parsed.scheme, netloc, parsed.path, "", fragment))
    else:
        safe = fallback
except Exception:
    safe = fallback
print(safe[:180])
PY
}

url_is_local() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import sys
from urllib.parse import urlsplit

try:
    parsed = urlsplit(sys.argv[1])
except Exception:
    sys.exit(1)
host = (parsed.hostname or "").lower()
sys.exit(0 if host in {"127.0.0.1", "localhost", "::1"} else 1)
PY
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
  local display_url
  display_url="$(safe_display_url "$url")"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if command_center_health_ready "$url"; then
      echo "FastAPI Command Center 3.0 health JSON ready: ${display_url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "FastAPI Command Center 3.0 health JSON still warming up or wrong service on port: ${display_url}"
  return 1
}

wait_for_vite_command_center() {
  local url="$1"
  local attempts="${2:-30}"
  local display_url
  display_url="$(safe_display_url "$url")"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if vite_command_center_ready "$url"; then
      echo "React/Vite Command Center 3.0 app ready: ${display_url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "React/Vite Command Center 3.0 app still warming up or wrong app on port: ${display_url}"
  return 1
}

wait_for_bootstrap_status() {
  local url="$1"
  local attempts="${2:-30}"
  local display_url
  display_url="$(safe_display_url "$url")"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if bootstrap_status_ready "$url"; then
      echo "FastAPI bootstrap status JSON ready: ${display_url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "FastAPI bootstrap status JSON still warming up: ${display_url}"
  return 1
}

wait_for_desktop_preflight_cache() {
  local url="$1"
  local attempts="${2:-30}"
  local display_url
  display_url="$(safe_display_url "$url")"
  local index=1
  while [ "$index" -le "$attempts" ]; do
    if desktop_preflight_cache_ready "$url"; then
      echo "FastAPI desktop preflight cache JSON ready: ${display_url}"
      return 0
    fi
    sleep 1
    index=$((index + 1))
  done
  echo "FastAPI desktop preflight cache JSON still warming up: ${display_url}"
  return 1
}

verify_p0_startup_stability() {
  echo "P0 stability check: waiting ${P0_STABILITY_DWELL_SECONDS}s, then re-reading health, bootstrap status, desktop preflight cache, and React/Vite before success handoff."
  sleep "$P0_STABILITY_DWELL_SECONDS"
  local failed=0
  if ! command_center_health_ready "${API_BASE%/}/health"; then
    FASTAPI_READY=0
    failed=1
  fi
  if ! bootstrap_status_ready "${API_BASE%/}/api/bootstrap/status"; then
    API_STATUS_READY=0
    failed=1
  fi
  if ! desktop_preflight_cache_ready "${API_BASE%/}/api/desktop/preflight-cache"; then
    DESKTOP_PREFLIGHT_READY=0
    failed=1
  fi
  if ! vite_command_center_ready "$VITE_URL"; then
    VITE_READY=0
    failed=1
  fi
  if [ "$failed" = "0" ]; then
    echo "P0 stability check passed: local backend/frontend stayed ready after the dwell; browser handoff remains safe."
  else
    echo "P0 stability check failed: a local readiness endpoint stopped responding before handoff; browser will not open."
  fi
  return "$failed"
}

print_startup_diagnostics() {
  echo "可操作诊断："
  if [ "$FASTAPI_READY" != "1" ]; then
    echo "  - FastAPI：${API_HEALTH_DISPLAY} 未返回 Command Center 3.0 健康 JSON；可能后端未启动、8710 被占用，或 Python 依赖缺失。"
  fi
  if [ "$API_STATUS_READY" != "1" ]; then
    echo "  - Bootstrap status：${BOOTSTRAP_STATUS_DISPLAY} 未返回 runtime-mode packet；可能后端不是 3.0，或启动时加载失败。"
  fi
  if [ "$DESKTOP_PREFLIGHT_READY" != "1" ]; then
    echo "  - Desktop preflight cache：${DESKTOP_PREFLIGHT_DISPLAY} 未返回一键启动 packet；可能后端预检 cache 尚未就绪。"
  fi
  if [ "$VITE_READY" != "1" ]; then
    echo "  - React/Vite：${VITE_URL_DISPLAY} 未返回 Command Center 3.0 前端 HTML；可能 5173 被占用，或 npm run dev 启动失败。"
  fi
  echo "下一步：先关闭占用 8710/5173 的本地进程，或查看上面的 FastAPI / React/Vite 日志。"
  echo "安全自检命令：scripts/check_command_center_3.command（check-only；不启动 FastAPI/Vite、不探测 URL、不打开浏览器）。"
  echo "普通恢复动作：打开今日作战台或桌面壳预检查看 P0 四段联通；P0 未 ready 时不要进入 P1 确认按钮。"
  echo "日志定位：FastAPI=${FASTAPI_LOG}；React/Vite=${VITE_LOG}。"
  echo "安全边界：失败诊断不会自动重试、不会创建 POST task、不会调用 Tushare/DeepSeek/GitHub，也不会读取 token/key。"
}

print_post_startup_readback_checklist() {
  echo "启动后复核清单："
  echo "  1. FastAPI health：${API_HEALTH_DISPLAY} 已返回 Command Center 3.0 JSON，且 external_calls_on_startup=false。"
  echo "  2. Bootstrap status：${BOOTSTRAP_STATUS_DISPLAY} 已返回 runtime-mode packet，只读显示 cache_only/manual/live_light/live_full。"
  echo "  3. Desktop preflight cache：${DESKTOP_PREFLIGHT_DISPLAY} 已返回一键启动 packet，普通首页和健康页可回读同一条 P0 本地证据。"
  if [ "${LAUNCHER_SKIP_OPEN:-0}" = "1" ]; then
    echo "  4. React/Vite 前端：${VITE_URL_DISPLAY} 已返回 Command Center 3.0 HTML；skip-open 已启用，请手动打开普通首页 ${APP_URL_DISPLAY}。"
  else
    echo "  4. React/Vite 前端：${VITE_URL_DISPLAY} 已返回 Command Center 3.0 HTML；页面会打开普通首页 ${APP_URL_DISPLAY}，先看今日作战台的一键启动预检。"
  fi
  echo "  5. P0 stability check：短暂 dwell 后复读 health、bootstrap status、desktop preflight cache 和 React/Vite 仍 ready，P0_STABILITY_READY=1。"
  echo "  6. 联通后下一步：打开下一票雷达（#candidates），输入股票代码；只有确认按钮会创建 Tushare-first POST task，DeepSeek 仍保持 governed/pending。"
  echo "  7. P0 success handoff: after readiness, launcher opens #home by default; user can open #candidates next; typing stays silent; confirm button creates Tushare-first POST task; DeepSeek remains governed/skipped."
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

API_BASE_DISPLAY="$(safe_display_url "$API_BASE")"
VITE_URL_DISPLAY="$(safe_display_url "$VITE_URL")"
APP_OPEN_URL="$(safe_display_open_url "$APP_URL")"
APP_URL_DISPLAY="$APP_OPEN_URL"
API_HEALTH_DISPLAY="$(safe_display_url "${API_BASE%/}/health")"
BOOTSTRAP_STATUS_DISPLAY="$(safe_display_url "${API_BASE%/}/api/bootstrap/status")"
DESKTOP_PREFLIGHT_DISPLAY="$(safe_display_url "${API_BASE%/}/api/desktop/preflight-cache")"

if ! url_is_local "$API_BASE"; then
  echo "Command Center 3.0 启动失败：FastAPI API base 必须是本机地址：${API_BASE_DISPLAY}"
  echo "边界：一键启动器不会探测非本机 API base，不打印 query/hash/username/password，不调用外部服务。"
  exit 1
fi

if ! url_is_local "$VITE_URL"; then
  echo "Command Center 3.0 启动失败：React/Vite URL 必须是本机地址：${VITE_URL_DISPLAY}"
  echo "边界：一键启动器不会打开非本机前端 URL，不打印 query/hash/username/password，不调用外部服务。"
  exit 1
fi

if ! url_is_local "$APP_URL"; then
  echo "Command Center 3.0 启动失败：打开页面 URL 必须是本机地址：${APP_URL_DISPLAY}"
  echo "边界：一键启动器不会打开非本机页面 URL，不打印 query/hash/username/password，不调用外部服务。"
  exit 1
fi

cd "$PROJECT_ROOT"

echo "Command Center 3.0 local launcher"
echo "Project: ${PROJECT_ROOT}"
echo "Python: ${PYTHON_BIN}"
echo "FastAPI: ${API_BASE_DISPLAY}"
echo "React/Vite: ${VITE_URL_DISPLAY}"
echo "Open route: ${APP_URL_DISPLAY}"
echo "Logs: ${LOG_DIR}"
echo "Check only: ${LAUNCHER_CHECK_ONLY}"
echo "Browser open: $([ "$LAUNCHER_SKIP_OPEN" = "1" ] && printf "skipped" || printf "enabled")"
echo "P0: local one-click launcher starts/checks FastAPI, bootstrap status, desktop preflight cache, and React/Vite before opening the page."
echo "Mode: server config controls runtime mode; cache_only remains the safe default unless explicitly configured."
echo "Link check: launcher verifies ${API_HEALTH_DISPLAY}, ${BOOTSTRAP_STATUS_DISPLAY}, and ${DESKTOP_PREFLIGHT_DISPLAY} before opening the page."
echo "Health check: /health must return stock-MING Command Center 3.0 JSON with external_calls_on_startup=false."
echo "Bootstrap check: /api/bootstrap/status must return command_center_3_bootstrap_runtime_mode_packet JSON before the page opens."
echo "Desktop preflight check: /api/desktop/preflight-cache must return command_center_3_desktop_shell_preflight_cache JSON before the page opens."
echo "Frontend check: Vite must serve stock-MING Command Center 3.0 index HTML before the page opens."
echo "Open target: ordinary Command Center home route (#home), so startup does not land on developer/audit details from localStorage."
echo "P0 success handoff: after readiness, launcher opens #home by default; user can open #candidates next; typing stays silent; confirm button creates Tushare-first POST task; DeepSeek remains governed/skipped."
echo "Boundary: one-click startup only links local frontend/backend; it does not enable live_light/provider/model execution."
echo "Safety: this launcher does not set live_light defaults and makes no Tushare, DeepSeek, GitHub, or trading call."
echo "URL safety: displayed and opened launcher URLs are sanitized; simple local open routes like #home may be shown, while query/userinfo are stripped and non-local API/frontend/open URLs are blocked before any probe."
echo "Acceptance: runtime_mode_config_current_acceptance_* markers are status/checkpoint drift guards, not launcher config or live_light enablement."

if [ "$LAUNCHER_CHECK_ONLY" = "1" ]; then
  echo "Check-only mode: resolved launcher configuration without starting FastAPI, starting React/Vite, probing URLs, writing logs, opening a browser, creating tasks, calling providers/models, or touching trading paths."
  echo "Check-only wrapper command: scripts/check_command_center_3.command"
  echo "Check-only dependency boundary: does not require desktop/node_modules or npm because it only prints sanitized local launcher configuration."
  echo "Check-only endpoints: health=${API_HEALTH_DISPLAY}; bootstrap=${BOOTSTRAP_STATUS_DISPLAY}; desktop_preflight=${DESKTOP_PREFLIGHT_DISPLAY}; frontend=${VITE_URL_DISPLAY}; open_route=${APP_URL_DISPLAY}"
  echo "Check-only next action: unset COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY and rerun this launcher to start or reuse local FastAPI/Vite, wait for all four readiness checks plus P0 stability dwell, then open ${APP_URL_DISPLAY}."
  exit 0
fi

mkdir -p "$LOG_DIR"

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
  echo "Vite already running; npm is only required when React/Vite must be started."
else
  if [ ! -d "${DESKTOP_ROOT}/node_modules" ]; then
    echo "Command Center 3.0 启动失败：desktop/node_modules 不存在，且 React/Vite 尚未运行。"
    echo "请先运行：cd \"${DESKTOP_ROOT}\" && npm install"
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "Command Center 3.0 启动失败：未找到 npm，且 React/Vite 尚未运行。"
    echo "如果是从 .app 双击进入，已运行的 React/Vite 会被复用；否则请先从终端运行 scripts/start_command_center_3.command 或把 npm 加入 PATH。"
    exit 1
  fi
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

P0_STABILITY_READY=0
if [ "$FASTAPI_READY" = "1" ] && [ "$API_STATUS_READY" = "1" ] && [ "$DESKTOP_PREFLIGHT_READY" = "1" ] && [ "$VITE_READY" = "1" ]; then
  if verify_p0_startup_stability; then
    P0_STABILITY_READY=1
  fi
fi

if [ "$FASTAPI_READY" != "1" ] || [ "$API_STATUS_READY" != "1" ] || [ "$DESKTOP_PREFLIGHT_READY" != "1" ] || [ "$VITE_READY" != "1" ] || [ "$P0_STABILITY_READY" != "1" ]; then
  echo "Command Center 3.0 启动未完成：FastAPI ready=${FASTAPI_READY}, API status ready=${API_STATUS_READY}, desktop preflight ready=${DESKTOP_PREFLIGHT_READY}, React/Vite ready=${VITE_READY}, P0 stability ready=${P0_STABILITY_READY}"
  echo "请查看日志："
  echo "  FastAPI log: ${FASTAPI_LOG}"
  echo "  React/Vite log: ${VITE_LOG}"
  print_startup_diagnostics
  echo "本地入口不会在前后端未联通、Vite 端口不是 Command Center 3.0 页面或 P0 稳定性复核失败时自动打开页面。"
  exit 1
fi

if [ "$LAUNCHER_SKIP_OPEN" = "1" ]; then
  echo "Skip-open mode: FastAPI, bootstrap status, desktop preflight cache, and React/Vite are ready; browser was not opened automatically."
  echo "请在浏览器打开：${APP_URL_DISPLAY}"
elif command -v open >/dev/null 2>&1; then
  if open "$APP_OPEN_URL"; then
    echo "Browser handoff opened: ${APP_URL_DISPLAY}"
  else
    echo "Browser handoff could not open automatically after local readiness passed; please open manually: ${APP_URL_DISPLAY}"
  fi
else
  echo "请在浏览器打开：${APP_URL_DISPLAY}"
fi

print_post_startup_readback_checklist
echo "Command Center 3.0 入口已启动。关闭本窗口不会停止已在后台运行的本地 dev server。"
