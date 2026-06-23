#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
STOCK_MING_FASTAPI_RELOAD="${STOCK_MING_FASTAPI_RELOAD:-1}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi
if [[ "$STOCK_MING_FASTAPI_RELOAD" == "1" ]]; then
  "$PYTHON_BIN" -m uvicorn server.main:app --reload --host 127.0.0.1 --port 8710
else
  "$PYTHON_BIN" -m uvicorn server.main:app --host 127.0.0.1 --port 8710
fi
