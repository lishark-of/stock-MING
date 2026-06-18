#!/usr/bin/env python3
"""Run Candidate Radar through a local Celery filesystem-broker round-trip.

This is LTG-13 direct evidence linked to LTG-06 worker transport mechanics.
It dispatches the existing Candidate Radar worker task through a local
filesystem broker. It does not use Redis, does not call providers/models/GitHub,
and does not prove production worker completion or radar replacement.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_EVIDENCE_PATH = (
    PROJECT_ROOT
    / ".stock_ming_3"
    / "candidate_radar_worker"
    / "candidate_radar_worker_filesystem_roundtrip_smoke.json"
)

os.environ.setdefault("COMMAND_CENTER_CELERY_BROKER_URL", "filesystem://")
os.environ.setdefault("COMMAND_CENTER_CELERY_RESULT_BACKEND", "cache+memory://")

from celery.contrib.testing.worker import start_worker  # noqa: E402

from worker.celery_app import CELERY_AVAILABLE, celery_app  # noqa: E402

if celery_app is not None:
    from server.services import candidate_service  # noqa: E402
    from worker.tasks_candidate import run_candidate_radar_full_pool_local_scan  # noqa: E402
else:
    candidate_service = None
    run_candidate_radar_full_pool_local_scan = None


def _base_payload(status: str, *, error_message_safe: str = "") -> dict[str, Any]:
    return {
        "schema_version": "candidate_radar_worker_filesystem_roundtrip_smoke.v1",
        "status": status,
        "direct_evidence_layer": "L3_local_candidate_radar_worker_filesystem_roundtrip_not_redis",
        "candidate_task_type": "run_candidate_radar_full_pool_local_scan",
        "output_packet_key": "command_center_3_candidate_radar_cache",
        "error_message_safe": error_message_safe,
        "celery_available": CELERY_AVAILABLE,
        "celery_testing_worker_started": False,
        "task_dispatched": False,
        "task_result_returned": False,
        "filesystem_broker_used": True,
        "redis_broker_used": False,
        "redis_pinged": False,
        "production_worker_complete": False,
        "production_radar_replacement_complete": False,
        "worker_backed_execution_done": False,
        "provider_backed_acceptance_done": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
    }


def _failure(error_message_safe: str) -> dict[str, Any]:
    return _base_payload("candidate_radar_worker_filesystem_roundtrip_failed", error_message_safe=error_message_safe)


def _configure_filesystem_broker(root: Path) -> None:
    inbox = root / "in"
    processed = root / "processed"
    control = root / "control"
    for folder in (inbox, processed, control):
        folder.mkdir(parents=True, exist_ok=True)

    assert celery_app is not None
    celery_app.conf.broker_transport_options = {
        "data_folder_in": str(inbox),
        "data_folder_out": str(inbox),
        "data_folder_processed": str(processed),
        "control_folder": str(control),
    }


def _returned_task_passed(returned: Any) -> bool:
    if not isinstance(returned, dict):
        return False
    call_ledger = returned.get("call_ledger")
    call_rows = call_ledger if isinstance(call_ledger, list) else []
    first_call = next((row for row in call_rows if isinstance(row, dict)), {})
    return (
        returned.get("task_type") == "run_candidate_radar_full_pool_local_scan"
        and returned.get("output_packet_key") == "command_center_3_candidate_radar_cache"
        and returned.get("status") == "success"
        and returned.get("current_step") == "candidate_radar_full_pool_local_scan_completed"
        and first_call.get("api") == "local_candidate_radar_full_pool_local_scan"
        and int(first_call.get("row_count") or 0) > 0
        and returned.get("external_calls_triggered") is False
        and returned.get("tushare_called") is False
        and returned.get("deepseek_called") is False
        and returned.get("github_called") is False
        and returned.get("does_not_execute_trades") is True
        and returned.get("does_not_modify_strategy_action") is True
        and all(row.get("external_calls_triggered") is not True for row in call_rows if isinstance(row, dict))
        and all(row.get("tushare_called") is not True for row in call_rows if isinstance(row, dict))
        and all(row.get("deepseek_called") is not True for row in call_rows if isinstance(row, dict))
        and all(row.get("github_called") is not True for row in call_rows if isinstance(row, dict))
    )


def run_smoke(timeout: float) -> dict[str, Any]:
    if not CELERY_AVAILABLE or celery_app is None or run_candidate_radar_full_pool_local_scan is None:
        return _failure("celery_or_candidate_task_unavailable")

    try:
        with tempfile.TemporaryDirectory(prefix="stock_ming_candidate_worker_fs_") as tmp:
            _configure_filesystem_broker(Path(tmp))
            if candidate_service is not None:
                candidate_service.SQLITE_META_PATH = Path(tmp) / "candidate_radar_worker_meta.sqlite"
            with start_worker(celery_app, perform_ping_check=False, pool="solo", loglevel="WARNING"):
                result = run_candidate_radar_full_pool_local_scan.delay(
                    {
                        "scan_mode": "full_pool_local_scan",
                        "requested_by": "candidate_radar_worker_filesystem_roundtrip_smoke",
                        "local_execution_only": True,
                        "local_universe_candidates": [
                            {"ticker": "002008.SZ", "name": "大族激光", "score": 61},
                            {"ticker": "002837.SZ", "name": "英维克", "score": 47},
                            {"ticker": "300750.SZ", "name": "宁德时代", "score": 45},
                        ],
                        "external_calls_triggered": False,
                        "tushare_called": False,
                        "deepseek_called": False,
                        "github_called": False,
                        "does_not_execute_trades": True,
                    }
                )
                returned = result.get(timeout=timeout)
    except Exception:
        return _failure("candidate_radar_worker_filesystem_roundtrip_exception")

    passed = _returned_task_passed(returned)
    call_rows = returned.get("call_ledger") if isinstance(returned, dict) else []
    first_call = next((row for row in call_rows if isinstance(row, dict)), {})
    payload = _base_payload(
        "candidate_radar_worker_filesystem_roundtrip_passed"
        if passed
        else "candidate_radar_worker_filesystem_roundtrip_failed"
    )
    payload.update(
        {
            "broker_url": "filesystem://",
            "result_backend": "cache+memory://",
            "celery_testing_worker_started": True,
            "task_dispatched": True,
            "task_result_returned": passed,
            "worker_backed_execution_done": passed,
            "worker_backed_local_full_pool_scan_done": passed,
            "production_worker_complete": False,
            "production_radar_replacement_complete": False,
            "production_full_pool_scan_done": False,
            "provider_backed_acceptance_done": False,
            "returned_task_id": returned.get("task_id") if isinstance(returned, dict) else "",
            "returned_task_status": returned.get("status") if isinstance(returned, dict) else "",
            "returned_current_step": returned.get("current_step") if isinstance(returned, dict) else "",
            "returned_call_api": first_call.get("api") or "",
            "returned_call_row_count": int(first_call.get("row_count") or 0),
            "note": (
                "This smoke proves the Candidate Radar task can round-trip through a local "
                "Celery filesystem broker and execute the local full-pool scan service. Redis "
                "broker, provider-backed parity, deep-scan worker execution, browser promotion, "
                "and production replacement remain pending."
            ),
        }
    )
    return payload


def _write_evidence(payload: dict[str, Any], evidence_path: Path | None) -> None:
    if evidence_path is None:
        return
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Candidate Radar local worker round-trip smoke.")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--evidence-path",
        type=Path,
        default=DEFAULT_EVIDENCE_PATH,
        help="When --write-evidence is used, write the local runtime evidence JSON to this ignored artifact path.",
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="Write the runtime evidence artifact after the worker round-trip succeeds.",
    )
    parser.add_argument(
        "--no-write-evidence",
        action="store_true",
        help="Print the evidence payload only; overrides --write-evidence.",
    )
    args = parser.parse_args()
    payload = run_smoke(timeout=args.timeout)
    _write_evidence(payload, args.evidence_path if args.write_evidence and not args.no_write_evidence else None)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "candidate_radar_worker_filesystem_roundtrip_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
