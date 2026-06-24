#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_NAME="stock-MING"
APP_DIR="${PROJECT_ROOT}/dist/${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
EXECUTABLE_PATH="${MACOS_DIR}/${APP_NAME}"
ICON_SOURCE="${PROJECT_ROOT}/assets/stock_ming_icon.svg"
LAUNCHER="${PROJECT_ROOT}/scripts/start_command_center_3.command"

echo "Command Center 3.0 macOS app wrapper generator"
echo "Project: ${PROJECT_ROOT}"
echo "Launcher: ${LAUNCHER}"
echo "Output: ${APP_DIR}"
echo "Boundary: generated app only delegates to the local Command Center 3.0 launcher; it does not call Tushare, DeepSeek, GitHub, or trading paths."

if [ ! -x "${LAUNCHER}" ]; then
  echo "stock-MING wrapper 生成失败：找不到可执行的 3.0 本地启动器：${LAUNCHER}" >&2
  exit 1
fi

mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

if [ -f "${ICON_SOURCE}" ]; then
  cp "${ICON_SOURCE}" "${RESOURCES_DIR}/stock_ming_icon.svg"
fi
cp "${LAUNCHER}" "${RESOURCES_DIR}/start_command_center_3.command"
chmod +x "${RESOURCES_DIR}/start_command_center_3.command"

cat > "${CONTENTS_DIR}/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>stock-MING</string>
  <key>CFBundleDisplayName</key>
  <string>stock-MING</string>
  <key>CFBundleIdentifier</key>
  <string>com.stockming.desktop</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleVersion</key>
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleExecutable</key>
  <string>stock-MING</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.15</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

printf "APPL????" > "${CONTENTS_DIR}/PkgInfo"

cat > "${EXECUTABLE_PATH}" <<APP
#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT}"
LAUNCHER="\${PROJECT_ROOT}/scripts/start_command_center_3.command"
BUNDLED_LAUNCHER="\$(cd "\$(dirname "\$0")/../Resources" && pwd)/start_command_center_3.command"
APP_URL="\${COMMAND_CENTER_3_APP_URL:-http://127.0.0.1:5173/#home}"
LOG_DIR="\${PROJECT_ROOT}/.stock_ming_3/logs"
WRAPPER_LOG="\${LOG_DIR}/command_center_3_app_wrapper.log"

show_message() {
  local message="\$1"
  echo "\$message"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${message}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
}

url_contains() {
  local url="\$1"
  local marker="\$2"
  /usr/bin/curl -fsS --max-time 2 "\$url" 2>/dev/null | /usr/bin/grep -q "\$marker"
}

local_stack_ready() {
  url_contains "http://127.0.0.1:8710/health" '"service":"stock-MING Command Center 3.0"' \\
    && url_contains "http://127.0.0.1:8710/health" '"external_calls_on_startup":false' \\
    && url_contains "http://127.0.0.1:8710/api/bootstrap/status" "command_center_3_bootstrap_runtime_mode_packet" \\
    && url_contains "http://127.0.0.1:8710/api/desktop/preflight-cache" "command_center_3_desktop_shell_preflight_cache" \\
    && url_contains "http://127.0.0.1:5173" "stock-MING Command Center 3.0"
}

open_ready_page() {
  if /usr/bin/open "\$APP_URL"; then
    echo "stock-MING app wrapper opened ready local page: \$APP_URL"
  else
    echo "stock-MING app wrapper local page is ready; please open manually: \$APP_URL"
  fi
}

if [ ! -d "\$PROJECT_ROOT" ]; then
  show_message "stock-MING Command Center 启动失败：找不到项目目录：\${PROJECT_ROOT}"
  exit 1
fi

if [ ! -x "\$LAUNCHER" ]; then
  show_message "stock-MING Command Center 启动失败：找不到本地 3.0 一键启动器：\${LAUNCHER}"
  exit 1
fi

if [ ! -x "\$BUNDLED_LAUNCHER" ]; then
  show_message "stock-MING Command Center 启动失败：找不到 app 内置启动器：\${BUNDLED_LAUNCHER}"
  exit 1
fi

cd "\$PROJECT_ROOT"
mkdir -p "\$LOG_DIR" >/dev/null 2>&1 || true

if local_stack_ready; then
  {
    echo "stock-MING app wrapper online fast path ready."
    echo "FastAPI/Vite already online; wrapper opened page without reading project .venv or external launcher."
    open_ready_page
  } >"\$WRAPPER_LOG" 2>&1
  exit 0
fi

if ! COMMAND_CENTER_BOOTSTRAP_MODE="\${COMMAND_CENTER_BOOTSTRAP_MODE:-cache_only}" \\
  COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="\${COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN:-false}" \\
  COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="\${COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN:-false}" \\
  COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="\${COMMAND_CENTER_LIVE_STARTUP_AUTOSTART:-false}" \\
  COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="\${COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART:-false}" \\
  COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="\${COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE:-plan_only}" \\
  COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE="\${COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE:-bootstrap_only}" \\
  COMMAND_CENTER_3_PROJECT_ROOT="\$PROJECT_ROOT" \\
  COMMAND_CENTER_3_APP_URL="\$APP_URL" \\
  /bin/bash "\$BUNDLED_LAUNCHER" >"\$WRAPPER_LOG" 2>&1; then
  if local_stack_ready; then
    {
      echo "stock-MING app wrapper launcher returned nonzero, but local stack is ready after fallback readback."
      open_ready_page
    } >>"\$WRAPPER_LOG" 2>&1
    exit 0
  fi
  if [ -s "\$WRAPPER_LOG" ]; then
    tail -n 30 "\$WRAPPER_LOG" || true
  fi
  show_message "stock-MING Command Center 启动未完成：本地 FastAPI / React 联通检查失败。请查看项目 .stock_ming_3/logs 下的 app wrapper / fastapi / vite 日志。"
  exit 1
fi
APP

chmod +x "${EXECUTABLE_PATH}"

echo "Command Center 3.0 .app wrapper created."
echo "Created ${APP_DIR}"
echo "Double-click behavior: waits for local FastAPI health, bootstrap status, desktop preflight cache, and React/Vite before opening #home."
echo "Safety: default mode is cache_only; live_light/provider/model execution remains disabled unless explicitly configured elsewhere."
