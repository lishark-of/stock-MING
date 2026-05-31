#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$PROJECT_ROOT" || {
  echo "Failed to enter project directory: $PROJECT_ROOT"
  exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3 first."
  exit 1
fi

if ! python3 -c "import webview" >/dev/null 2>&1; then
  echo "pywebview is not installed. Install it with:"
  echo "python3 -m pip install pywebview"
  exit 1
fi

python3 desktop_app.py
