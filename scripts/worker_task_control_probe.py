#!/usr/bin/env python3
"""Read a task status from a separate local Python process.

This probe is used by LTG-06 runtime QA. It reads SQLite task metadata only,
prints a redacted verification payload, and never starts Celery, pings Redis,
dispatches tasks, calls providers, or touches trading paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.sqlite_meta import SQLiteMetaStore  # noqa: E402


SENSITIVE_KEYS = {"token", "api_key", "secret", "password", "authorization", "bearer", "cookie"}
PROJECTION_KEYS = (
    "task_id",
    "task_type",
    "status",
    "output_packet_key",
    "current_step",
    "progress",
    "retry_policy",
    "lock_policy",
    "dedupe_policy",
)


def _safe_projection(task: dict[str, Any]) -> dict[str, Any]:
    projection = {key: task.get(key) for key in PROJECTION_KEYS}
    projection["task_log_events"] = [
        {
            "event": row.get("event"),
            "status": row.get("status"),
            "step": row.get("step"),
        }
        for row in task.get("task_log") or []
        if isinstance(row, dict)
    ]
    return projection


def _sha256(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                return True
            if _contains_sensitive_key(item):
                return True
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe local task status from a separate Python process.")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema_version": "worker_task_control_cross_process_probe.v1",
        "status": "cross_process_task_control_blocked",
        "scope": "local_python_process_sqlite_task_status_readback_no_worker_start",
        "task_id": args.task_id,
        "storage_source": "sqlite_meta",
        "readback_found": False,
        "readback_hash_matches": False,
        "task_status": "",
        "task_log_count": 0,
        "retry_metadata_visible": False,
        "lock_metadata_visible": False,
        "dedupe_metadata_visible": False,
        "contains_secret": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "error_message_safe": "",
    }
    try:
        task = SQLiteMetaStore(args.db_path).read_task_status(args.task_id)
    except Exception:
        result["error_message_safe"] = "cross_process_task_status_read_failed"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1
    if not isinstance(task, dict):
        result["error_message_safe"] = "cross_process_task_status_missing"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1

    projection = _safe_projection(task)
    task_hash = _sha256(projection)
    result.update(
        {
            "status": "cross_process_task_control_verified"
            if task_hash == args.expected_sha256
            and task.get("status") == "success"
            and isinstance(task.get("task_log"), list)
            and len(task.get("task_log") or []) > 0
            and isinstance(task.get("retry_policy"), dict)
            and isinstance(task.get("lock_policy"), dict)
            and isinstance(task.get("dedupe_policy"), dict)
            and not _contains_sensitive_key(task.get("payload_safe"))
            else "cross_process_task_control_blocked",
            "readback_found": True,
            "readback_hash_matches": task_hash == args.expected_sha256,
            "task_status": str(task.get("status") or ""),
            "task_log_count": len(task.get("task_log") or []),
            "retry_metadata_visible": isinstance(task.get("retry_policy"), dict),
            "lock_metadata_visible": isinstance(task.get("lock_policy"), dict),
            "dedupe_metadata_visible": isinstance(task.get("dedupe_policy"), dict),
            "contains_secret": _contains_sensitive_key(task.get("payload_safe")),
            "task_identity_sha256": task_hash,
        }
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "cross_process_task_control_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
