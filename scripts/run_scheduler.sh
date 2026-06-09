#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
from worker.scheduler import build_scheduler

info = build_scheduler()
print({k: v for k, v in info.items() if k != "scheduler"})
if info.get("available") and info.get("enabled"):
    scheduler = info["scheduler"]
    scheduler.start()
    print("APScheduler 已启动。按 Ctrl+C 退出。")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()
else:
    print("默认未启用真实定时刷新。设置 COMMAND_CENTER_ENABLE_SCHEDULED_REFRESH=1 后再启动。")
PY
