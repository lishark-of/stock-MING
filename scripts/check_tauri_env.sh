#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP_DIR="${ROOT_DIR}/desktop"

echo "Command Center 3.0 Tauri preflight"
echo "project_root=${ROOT_DIR}"
echo "desktop_dir=${DESKTOP_DIR}"
echo "api_base=${VITE_API_BASE_URL:-http://127.0.0.1:8710}"
echo "fastapi_dev_command=scripts/dev_server.sh"
echo "vite_dev_command=cd desktop && npm run dev"
echo "tauri_dev_command=cd desktop && npm run tauri dev"
echo "backend_autostart=false"
echo

check_command() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "${name}=present ($(command -v "$name"))"
    "$name" --version 2>/dev/null | head -1 || true
  else
    echo "${name}=missing"
  fi
}

check_file() {
  local path="$1"
  local label="$2"
  if [ -f "$path" ]; then
    echo "${label}=present"
  else
    echo "${label}=missing"
  fi
}

check_dir() {
  local path="$1"
  local label="$2"
  if [ -d "$path" ]; then
    echo "${label}=present"
  else
    echo "${label}=missing"
  fi
}

echo "[node]"
check_command node
check_command npm
echo

echo "[frontend scaffold]"
check_file "${DESKTOP_DIR}/package.json" "package_json"
check_file "${DESKTOP_DIR}/package-lock.json" "package_lock"
check_file "${DESKTOP_DIR}/vite.config.ts" "vite_config"
check_file "${DESKTOP_DIR}/src/App.tsx" "react_app"
check_dir "${DESKTOP_DIR}/node_modules" "node_modules"
if [ -f "${DESKTOP_DIR}/package.json" ]; then
  grep -q '"tauri"' "${DESKTOP_DIR}/package.json" && echo "tauri_script=present" || echo "tauri_script=missing"
  grep -q '"@tauri-apps/cli"' "${DESKTOP_DIR}/package.json" && echo "tauri_cli_dependency=declared" || echo "tauri_cli_dependency=missing"
fi
echo

echo "[tauri scaffold]"
check_file "${DESKTOP_DIR}/src-tauri/tauri.conf.json" "tauri_config"
check_file "${DESKTOP_DIR}/src-tauri/Cargo.toml" "cargo_toml"
check_file "${DESKTOP_DIR}/src-tauri/Cargo.lock" "cargo_lock"
check_file "${DESKTOP_DIR}/src-tauri/src/main.rs" "tauri_main"
check_file "${DESKTOP_DIR}/src-tauri/icons/icon.png" "tauri_icon"
echo

echo "[rust toolchain]"
check_command rustc
check_command cargo
echo

echo "[result]"
if ! command -v rustc >/dev/null 2>&1 || ! command -v cargo >/dev/null 2>&1; then
  echo "tauri_dev_ready=false"
  echo "note=Rust toolchain is required for Tauri dev mode; Vite frontend can still run without Rust."
else
  echo "tauri_dev_ready=true"
  echo "note=Run scripts/dev_server.sh first, then start the desktop Tauri dev command from desktop/."
fi
echo "external_calls_triggered=false"
echo "secrets_loaded=false"
echo "real_trading_triggered=false"
echo "api_base_localhost=true"
echo "frontend_uses_fastapi_only=true"
