#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAUNCHER="${PROJECT_ROOT}/scripts/start_command_center_3.command"
DESKTOP_DIR="${STOCK_MING_DESKTOP_DIR:-${HOME}/Desktop}"
TARGET_NAME="${STOCK_MING_DESKTOP_SHORTCUT_NAME:-stock-MING Command Center 3.command}"
TARGET_PATH="${DESKTOP_DIR}/${TARGET_NAME}"

echo "Command Center 3.0 desktop shortcut installer"
echo "Project: ${PROJECT_ROOT}"
echo "Launcher: ${LAUNCHER}"
echo "Desktop target: ${TARGET_PATH}"
echo "Safety: creates only a local symlink; no Tushare, DeepSeek, GitHub, or trading call is made by this script."

if [ ! -f "$LAUNCHER" ]; then
  echo "Install failed: launcher is missing: ${LAUNCHER}"
  exit 1
fi

chmod +x "$LAUNCHER"
mkdir -p "$DESKTOP_DIR"
ln -sfn "$LAUNCHER" "$TARGET_PATH"

echo "Command Center 3.0 desktop shortcut installed."
echo "Double-click: ${TARGET_PATH}"
