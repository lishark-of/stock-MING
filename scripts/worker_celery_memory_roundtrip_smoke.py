#!/usr/bin/env python3
"""Run a local Celery memory-broker round-trip smoke.

This is LTG-06 direct evidence for Celery task dispatch mechanics only. It
does not use Redis, does not call providers/models/GitHub, and does not prove
production worker completion.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("COMMAND_CENTER_CELERY_BROKER_URL", "memory://")
os.environ.setdefault("COMMAND_CENTER_CELERY_RESULT_BACKEND", "cache+memory://")

from celery.contrib.testing.worker import start_worker  # noqa: E402

from worker.celery_app import CELERY_AVAILABLE, celery_app  # noqa: E402


def _failure(error_message_safe: str) -> dict[str, Any]:
    return {
        "schema_version": "worker_celery_memory_roundtrip_smoke.v1",
        "status": "celery_memory_roundtrip_failed",
        "direct_evidence_layer": "L3_local_celery_memory_roundtrip_not_redis",
        "error_message_safe": error_message_safe,
        "celery_available": CELERY_AVAILABLE,
        "celery_testing_worker_started": False,
        "task_dispatched": False,
        "task_result_returned": False,
        "redis_broker_used": False,
        "redis_pinged": False,
        "production_worker_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


if celery_app is not None:

    @celery_app.task(name="local_worker_memory_roundtrip_smoke")
    def local_worker_memory_roundtrip_smoke(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "payload_mode": str(payload.get("mode") or ""),
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }


def run_smoke(timeout: float) -> dict[str, Any]:
    if not CELERY_AVAILABLE or celery_app is None:
        return _failure("celery_unavailable")

    try:
        with start_worker(celery_app, perform_ping_check=False, pool="solo", loglevel="WARNING"):
            result = local_worker_memory_roundtrip_smoke.delay({"mode": "memory_roundtrip"})
            returned = result.get(timeout=timeout)
    except Exception:
        return _failure("celery_memory_roundtrip_exception")

    passed = (
        isinstance(returned, dict)
        and returned.get("ok") is True
        and returned.get("payload_mode") == "memory_roundtrip"
        and returned.get("external_calls_triggered") is False
        and returned.get("tushare_called") is False
        and returned.get("deepseek_called") is False
        and returned.get("github_called") is False
        and returned.get("does_not_execute_trades") is True
        and returned.get("does_not_modify_strategy_action") is True
        and returned.get("contains_secret") is False
    )
    return {
        "schema_version": "worker_celery_memory_roundtrip_smoke.v1",
        "status": "celery_memory_roundtrip_passed" if passed else "celery_memory_roundtrip_failed",
        "direct_evidence_layer": "L3_local_celery_memory_roundtrip_not_redis",
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "celery_available": CELERY_AVAILABLE,
        "celery_testing_worker_started": True,
        "task_dispatched": True,
        "task_result_returned": passed,
        "redis_broker_used": False,
        "redis_pinged": False,
        "production_worker_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "returned_payload": returned if isinstance(returned, dict) else {},
        "note": "This smoke proves local Celery memory-broker task round-trip only; Redis broker and production worker evidence remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Celery memory round-trip smoke.")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    payload = run_smoke(timeout=args.timeout)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "celery_memory_roundtrip_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
