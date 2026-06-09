from __future__ import annotations

import os
from typing import Any


def build_scheduler() -> dict[str, Any]:
    enabled = os.getenv("COMMAND_CENTER_ENABLE_SCHEDULED_REFRESH") == "1"
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as exc:
        return {
            "available": False,
            "enabled": False,
            "scheduler": None,
            "error_message_safe": str(exc),
            "note": "APScheduler 未安装时只保留配置骨架。",
        }
    scheduler = BackgroundScheduler()
    return {
        "available": True,
        "enabled": enabled,
        "scheduler": scheduler,
        "error_message_safe": "",
        "note": "默认不启用真实收盘后刷新；需设置 COMMAND_CENTER_ENABLE_SCHEDULED_REFRESH=1。",
    }
