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
PYTHON_BIN="$(command -v python3 || true)"

if [ -z "${PYTHON_BIN}" ]; then
  echo "python3 not found. Please install Python 3 first."
  exit 1
fi

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

if [ ! -x "\${PYTHON_BIN}" ]; then
  MESSAGE="python3 not found. Please install Python 3 first."
  echo "\${MESSAGE}"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${MESSAGE}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
  exit 1
fi

if ! "\${PYTHON_BIN}" -c "import webview" >/dev/null 2>&1; then
  MESSAGE="pywebview is not installed. Install it with:\n\${PYTHON_BIN} -m pip install pywebview"
  echo "pywebview is not installed. Install it with:"
  echo "\${PYTHON_BIN} -m pip install pywebview"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"\${MESSAGE}\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null 2>&1 || true
  fi
  exit 1
fi

exec "\${PYTHON_BIN}" desktop_app.py
APP

chmod +x "${EXECUTABLE_PATH}"

echo "Created ${APP_DIR}"
