#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_FALLBACK:-python3}"
fi

if "$PYTHON_BIN" - <<'PY'
try:
    import celery  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
then
  "$PYTHON_BIN" -m celery -A worker.celery_app.celery_app worker --loglevel=INFO
else
  echo "Celery 未安装；当前只可使用 FastAPI local task stub。"
fi
