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
echo "Install safety: existing non-symlink target will not be overwritten."

if [ ! -f "$LAUNCHER" ]; then
  echo "Install failed: launcher is missing: ${LAUNCHER}"
  exit 1
fi

if [ -e "$TARGET_PATH" ] && [ ! -L "$TARGET_PATH" ]; then
  echo "Install failed: desktop target already exists and is not a symlink: ${TARGET_PATH}"
  echo "Next step: move that file away, or set STOCK_MING_DESKTOP_SHORTCUT_NAME to a different shortcut name."
  echo "Boundary: installer stopped before changing files; it did not start services or call providers/models."
  exit 1
fi

chmod +x "$LAUNCHER"
mkdir -p "$DESKTOP_DIR"
ln -sfn "$LAUNCHER" "$TARGET_PATH"

if [ ! -L "$TARGET_PATH" ]; then
  echo "Install failed: shortcut was not created as a symlink: ${TARGET_PATH}"
  exit 1
fi

if [ "$(readlink "$TARGET_PATH")" != "$LAUNCHER" ]; then
  echo "Install failed: shortcut points to the wrong launcher: $(readlink "$TARGET_PATH")"
  exit 1
fi

echo "Command Center 3.0 desktop shortcut installed."
echo "Install verification: shortcut symlink points to the local launcher."
echo "Double-click: ${TARGET_PATH}"
echo "Double-click checklist: launcher checks FastAPI /health, bootstrap status, and React/Vite before opening the page."
echo "Boundary: shortcut install does not start FastAPI/Vite, create tasks, enable live_light, or execute trading."
