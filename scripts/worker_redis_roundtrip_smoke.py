#!/usr/bin/env python3
"""Run a local Redis-backed Celery round-trip smoke.

This is LTG-06 direct evidence for a manually started local Redis broker and
Celery testing worker. It does not call providers/models/GitHub and does not
prove production worker completion.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EVIDENCE_PATH = PROJECT_ROOT / ".stock_ming_3" / "worker_runtime" / "worker_redis_roundtrip_smoke.json"
REDIS_SERVER_CANDIDATES = (
    "/opt/homebrew/bin/redis-server",
    "/usr/local/bin/redis-server",
    "/opt/local/bin/redis-server",
    "/usr/bin/redis-server",
)


def _find_redis_server() -> str:
    found = shutil.which("redis-server")
    if found:
        return found
    for path in REDIS_SERVER_CANDIDATES:
        if Path(path).exists():
            return path
    return ""


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _failure(error_message_safe: str) -> dict[str, Any]:
    return {
        "schema_version": "worker_redis_roundtrip_smoke.v1",
        "status": "redis_roundtrip_failed",
        "direct_evidence_layer": "L3_local_redis_celery_roundtrip_not_production_worker",
        "error_message_safe": error_message_safe,
        "redis_server_binary_available": bool(_find_redis_server()),
        "redis_server_started": False,
        "redis_pinged": False,
        "redis_broker_used": False,
        "redis_url_configured": False,
        "redis_url_exposed": False,
        "redis_url_contains_credentials": False,
        "celery_testing_worker_started": False,
        "task_dispatched": False,
        "task_result_returned": False,
        "production_worker_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _start_redis(redis_server: str, port: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            redis_server,
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
            "--daemonize",
            "no",
            "--protected-mode",
            "yes",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_smoke(timeout: float) -> dict[str, Any]:
    redis_server = _find_redis_server()
    if not redis_server:
        return _failure("redis_server_binary_missing")

    port = _free_local_port()
    redis_url = f"redis://127.0.0.1:{port}/0"
    redis_result_url = f"redis://127.0.0.1:{port}/1"
    process: subprocess.Popen[bytes] | None = None
    try:
        process = _start_redis(redis_server, port)
        import redis

        client = redis.Redis(host="127.0.0.1", port=port, db=0, socket_timeout=0.5)
        deadline = time.time() + timeout
        redis_pinged = False
        while time.time() < deadline:
            if process.poll() is not None:
                return _failure("redis_server_exited_before_ping")
            try:
                redis_pinged = bool(client.ping())
                if redis_pinged:
                    break
            except Exception:
                time.sleep(0.05)
        if not redis_pinged:
            return _failure("redis_ping_timeout")

        os.environ["COMMAND_CENTER_CELERY_BROKER_URL"] = redis_url
        os.environ["COMMAND_CENTER_CELERY_RESULT_BACKEND"] = redis_result_url

        from celery.contrib.testing.worker import start_worker
        from worker.celery_app import CELERY_AVAILABLE, celery_app

        if not CELERY_AVAILABLE or celery_app is None:
            return _failure("celery_unavailable")

        @celery_app.task(name="local_worker_redis_roundtrip_smoke")
        def local_worker_redis_roundtrip_smoke(payload: dict[str, Any]) -> dict[str, Any]:
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

        with start_worker(celery_app, perform_ping_check=False, pool="solo", loglevel="WARNING"):
            result = local_worker_redis_roundtrip_smoke.delay({"mode": "redis_roundtrip"})
            returned = result.get(timeout=timeout)

        passed = (
            isinstance(returned, dict)
            and returned.get("ok") is True
            and returned.get("payload_mode") == "redis_roundtrip"
            and returned.get("external_calls_triggered") is False
            and returned.get("tushare_called") is False
            and returned.get("deepseek_called") is False
            and returned.get("github_called") is False
            and returned.get("does_not_execute_trades") is True
            and returned.get("does_not_modify_strategy_action") is True
            and returned.get("contains_secret") is False
        )
        return {
            "schema_version": "worker_redis_roundtrip_smoke.v1",
            "status": "redis_roundtrip_passed" if passed else "redis_roundtrip_failed",
            "direct_evidence_layer": "L3_local_redis_celery_roundtrip_not_production_worker",
            "redis_server_binary_available": True,
            "redis_server_started": True,
            "redis_pinged": True,
            "redis_broker_used": True,
            "redis_url_configured": True,
            "redis_url_exposed": False,
            "redis_url_contains_credentials": False,
            "broker_url_redacted": "redis://127.0.0.1:<local-port>/0",
            "result_backend_redacted": "redis://127.0.0.1:<local-port>/1",
            "celery_available": CELERY_AVAILABLE,
            "celery_testing_worker_started": True,
            "task_dispatched": True,
            "task_result_returned": passed,
            "production_worker_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "returned_payload": returned if isinstance(returned, dict) else {},
            "note": "This smoke proves local Redis-backed Celery task round-trip only; production worker promotion remains pending.",
        }
    except Exception:
        return _failure("redis_roundtrip_exception")
    finally:
        if process is not None and process.poll() is None:
            try:
                import redis

                redis.Redis(host="127.0.0.1", port=port, db=0, socket_timeout=0.5).shutdown(nosave=True)
            except Exception:
                process.terminate()
            try:
                process.wait(timeout=2)
            except Exception:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Redis-backed Celery round-trip smoke.")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()
    payload = run_smoke(timeout=args.timeout)
    if args.write_evidence:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "redis_roundtrip_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
