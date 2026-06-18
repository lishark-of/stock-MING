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
    from worker.tasks_candidate import run_candidate_radar_deep_scan_worker_fallback  # noqa: E402
    from worker.tasks_candidate import run_candidate_radar_full_pool_local_scan  # noqa: E402
else:
    candidate_service = None
    run_candidate_radar_deep_scan_worker_fallback = None
    run_candidate_radar_full_pool_local_scan = None


def _base_payload(status: str, *, error_message_safe: str = "") -> dict[str, Any]:
    return {
        "schema_version": "candidate_radar_worker_filesystem_roundtrip_smoke.v1",
        "status": status,
        "direct_evidence_layer": "L3_local_candidate_radar_worker_filesystem_roundtrip_not_redis",
        "candidate_task_type": "run_candidate_radar_full_pool_local_scan",
        "candidate_task_types": [
            "run_candidate_radar_full_pool_local_scan",
            "run_candidate_radar_deep_scan_worker_fallback",
        ],
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
        "worker_backed_local_full_pool_scan_done": False,
        "worker_backed_local_deep_scan_fallback_done": False,
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


def _returned_task_passed(returned: Any, *, expected_task_type: str, expected_step: str, expected_api: str) -> bool:
    if not isinstance(returned, dict):
        return False
    call_ledger = returned.get("call_ledger")
    call_rows = call_ledger if isinstance(call_ledger, list) else []
    first_call = next((row for row in call_rows if isinstance(row, dict)), {})
    return (
        returned.get("task_type") == expected_task_type
        and returned.get("output_packet_key") == "command_center_3_candidate_radar_cache"
        and returned.get("status") == "success"
        and returned.get("current_step") == expected_step
        and first_call.get("api") == expected_api
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


def _prepare_deep_scan_worker_request() -> str:
    assert candidate_service is not None
    candidate_service.run_candidate_deep_scan_local_review_task(
        {"scan_mode": "deep_scan_local_review", "local_review_only": True}
    )
    candidate_service.run_candidate_provider_parity_dry_run_task(
        {
            "candidate_symbols": ["002008.SZ", "002837.SZ", "300750.SZ"],
            "selected_signal_groups": ["moneyflow", "dragon_tiger", "hard_risk"],
            "include_tushare": True,
            "include_deepseek": True,
            "user_approved": True,
        }
    )
    candidate_service.run_candidate_quant_projection_acceptance_dry_run_task(
        {
            "symbol": "002008",
            "include_tushare": True,
            "include_deepseek": True,
            "user_approved": True,
            "selected_apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
        }
    )
    cache = candidate_service.read_candidate_radar_cache()
    recipe = cache.get("candidate_radar_worker_execution_recipe") if isinstance(cache, dict) else {}
    scope_hash = str(recipe.get("worker_execution_scope_hash") or "") if isinstance(recipe, dict) else ""
    if len(scope_hash) != 64:
        return ""
    candidate_service.run_candidate_worker_execution_request_task(
        {
            "scan_mode": "worker_execution_request",
            "operator_approved": True,
            "worker_execution_scope_hash": scope_hash,
        }
    )
    return scope_hash


def run_smoke(timeout: float) -> dict[str, Any]:
    if (
        not CELERY_AVAILABLE
        or celery_app is None
        or run_candidate_radar_full_pool_local_scan is None
        or run_candidate_radar_deep_scan_worker_fallback is None
    ):
        return _failure("celery_or_candidate_task_unavailable")

    try:
        with tempfile.TemporaryDirectory(prefix="stock_ming_candidate_worker_fs_") as tmp:
            _configure_filesystem_broker(Path(tmp))
            if candidate_service is not None:
                candidate_service.SQLITE_META_PATH = Path(tmp) / "candidate_radar_worker_meta.sqlite"
            with start_worker(celery_app, perform_ping_check=False, pool="solo", loglevel="WARNING"):
                full_pool_result = run_candidate_radar_full_pool_local_scan.delay(
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
                full_pool_returned = full_pool_result.get(timeout=timeout)
                if not _returned_task_passed(
                    full_pool_returned,
                    expected_task_type="run_candidate_radar_full_pool_local_scan",
                    expected_step="candidate_radar_full_pool_local_scan_completed",
                    expected_api="local_candidate_radar_full_pool_local_scan",
                ):
                    return _failure("candidate_radar_full_pool_worker_roundtrip_failed")

                scope_hash = _prepare_deep_scan_worker_request()
                if not scope_hash:
                    return _failure("candidate_radar_deep_scan_worker_scope_hash_missing")

                deep_scan_result = run_candidate_radar_deep_scan_worker_fallback.delay(
                    {
                        "scan_mode": "deep_scan_worker_fallback",
                        "requested_by": "candidate_radar_worker_filesystem_roundtrip_smoke",
                        "operator_approved": True,
                        "worker_execution_scope_hash": scope_hash,
                        "external_calls_triggered": False,
                        "tushare_called": False,
                        "deepseek_called": False,
                        "github_called": False,
                        "does_not_execute_trades": True,
                    }
                )
                deep_scan_returned = deep_scan_result.get(timeout=timeout)
    except Exception:
        return _failure("candidate_radar_worker_filesystem_roundtrip_exception")

    full_pool_call_rows = full_pool_returned.get("call_ledger") if isinstance(full_pool_returned, dict) else []
    full_pool_first_call = next((row for row in full_pool_call_rows if isinstance(row, dict)), {})
    deep_scan_call_rows = deep_scan_returned.get("call_ledger") if isinstance(deep_scan_returned, dict) else []
    deep_scan_first_call = next((row for row in deep_scan_call_rows if isinstance(row, dict)), {})
    full_pool_passed = _returned_task_passed(
        full_pool_returned,
        expected_task_type="run_candidate_radar_full_pool_local_scan",
        expected_step="candidate_radar_full_pool_local_scan_completed",
        expected_api="local_candidate_radar_full_pool_local_scan",
    )
    deep_scan_passed = _returned_task_passed(
        deep_scan_returned,
        expected_task_type="run_candidate_radar_deep_scan_worker_fallback",
        expected_step="candidate_radar_deep_scan_worker_fallback_ready",
        expected_api="local_candidate_radar_deep_scan_worker_fallback",
    )
    passed = full_pool_passed and deep_scan_passed
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
            "worker_backed_local_full_pool_scan_done": full_pool_passed,
            "worker_backed_local_deep_scan_fallback_done": deep_scan_passed,
            "production_worker_complete": False,
            "production_radar_replacement_complete": False,
            "production_full_pool_scan_done": False,
            "production_deep_scan_done": False,
            "deepseek_model_execution_done": False,
            "model_execution_implemented": False,
            "provider_backed_acceptance_done": False,
            "returned_task_id": full_pool_returned.get("task_id") if isinstance(full_pool_returned, dict) else "",
            "returned_task_status": full_pool_returned.get("status") if isinstance(full_pool_returned, dict) else "",
            "returned_current_step": (
                full_pool_returned.get("current_step") if isinstance(full_pool_returned, dict) else ""
            ),
            "returned_call_api": full_pool_first_call.get("api") or "",
            "returned_call_row_count": int(full_pool_first_call.get("row_count") or 0),
            "deep_scan_returned_task_id": (
                deep_scan_returned.get("task_id") if isinstance(deep_scan_returned, dict) else ""
            ),
            "deep_scan_returned_task_status": (
                deep_scan_returned.get("status") if isinstance(deep_scan_returned, dict) else ""
            ),
            "deep_scan_returned_current_step": (
                deep_scan_returned.get("current_step") if isinstance(deep_scan_returned, dict) else ""
            ),
            "deep_scan_returned_call_api": deep_scan_first_call.get("api") or "",
            "deep_scan_returned_call_row_count": int(deep_scan_first_call.get("row_count") or 0),
            "note": (
                "This smoke proves the Candidate Radar task can round-trip through a local "
                "Celery filesystem broker and execute the local full-pool scan service plus the "
                "local deep-scan worker fallback service. Redis broker, provider-backed parity, "
                "DeepSeek/model execution, browser promotion, and production replacement remain pending."
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
