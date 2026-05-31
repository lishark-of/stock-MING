#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

cd "$PROJECT_ROOT" || {
  echo "Failed to enter project directory: $PROJECT_ROOT"
  exit 1
}

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python virtual environment not found: $PYTHON_BIN"
  exit 1
fi

"$PYTHON_BIN" -c "import webview" 2>/tmp/stock-ming-pywebview-error.log
if [ $? -ne 0 ]; then
  echo "pywebview import failed. The package name is pywebview, but the import name is webview."
  echo "Run:"
  echo "$PYTHON_BIN -m pip install pywebview"
  cat /tmp/stock-ming-pywebview-error.log
  exit 1
fi

"$PYTHON_BIN" "$PROJECT_ROOT/desktop_app.py"
