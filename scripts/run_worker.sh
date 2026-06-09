#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if python3 - <<'PY'
try:
    import celery  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
then
  python3 -m celery -A worker.celery_app.celery_app worker --loglevel=INFO
else
  echo "Celery 未安装；当前只可使用 FastAPI local task stub。"
fi
