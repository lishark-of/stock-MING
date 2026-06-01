#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/Users/shark-li/Documents/GitHub/stock-MING"
APP_NAME="stock-MING"
APP_DIR="${PROJECT_ROOT}/dist/${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
EXECUTABLE_PATH="${MACOS_DIR}/${APP_NAME}"
ICON_SOURCE="${PROJECT_ROOT}/assets/stock_ming_icon.svg"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

if [ -f "${ICON_SOURCE}" ]; then
  cp "${ICON_SOURCE}" "${RESOURCES_DIR}/stock_ming_icon.svg"
fi

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
PROJECT_ROOT="/Users/shark-li/Documents/GitHub/stock-MING"
PYTHON_BIN="${PYTHON_BIN}"

cd "${PROJECT_ROOT}" || exit 1

if [ ! -d "\${PROJECT_ROOT}/.venv" ]; then
  MESSAGE="stock-MING 启动失败：未找到虚拟环境目录：\${PROJECT_ROOT}/.venv
请先在项目目录创建虚拟环境，并安装 requirements.txt。"
  echo "\${MESSAGE}"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${MESSAGE}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
  exit 1
fi

if [ ! -e "\${PYTHON_BIN}" ]; then
  MESSAGE="stock-MING 启动失败：未找到 Python 解释器：\${PYTHON_BIN}
请检查 .venv 是否完整，或重新创建虚拟环境。"
  echo "\${MESSAGE}"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${MESSAGE}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
  exit 1
fi

if [ ! -x "\${PYTHON_BIN}" ]; then
  MESSAGE="stock-MING 启动失败：Python 解释器不可执行：\${PYTHON_BIN}
请修复权限，或重新创建虚拟环境。"
  echo "\${MESSAGE}"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${MESSAGE}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
  exit 1
fi

"\${PYTHON_BIN}" -c "import webview" 2>/tmp/stock-ming-pywebview-error.log
if [ \$? -ne 0 ]; then
  MESSAGE="stock-MING 启动失败：pywebview 未安装或无法导入。
请运行：
\${PYTHON_BIN} -m pip install pywebview"
  echo "\${MESSAGE}"
  cat /tmp/stock-ming-pywebview-error.log
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${MESSAGE}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
  exit 1
fi

exec "\${PYTHON_BIN}" "\${PROJECT_ROOT}/desktop_app.py"
APP

chmod +x "${EXECUTABLE_PATH}"

echo "Created ${APP_DIR}"
